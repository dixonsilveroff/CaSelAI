import textwrap
from pathlib import Path
from PIL import Image, ImageDraw

from carouselai.core.context import BrandProfile, SlideScript
from carouselai.modules.brand_engine import brand_engine

class BaseTemplate:
    """Base class for all slide templates."""
    def __init__(self, brand: BrandProfile, slide: SlideScript, asset_path: str = None):
        self.brand = brand
        self.slide = slide
        self.asset_path = asset_path
        self.width = 1080
        self.height = 1080
        self.image = Image.new("RGB", (self.width, self.height), self._hex_to_rgb(self.brand.background_color))
        self.draw = ImageDraw.Draw(self.image)

    def _hex_to_rgb(self, hex_color: str):
        """Converts a hex color string to an RGB tuple."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return (0, 0, 0) # Fallback to black if invalid
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _wrap_text(self, text: str, font, max_width: int):
        """Wraps text to fit within a given width using basic estimation."""
        lines = []
        for line in text.split('\n'):
            # Simple wrap approximation for MVP
            if hasattr(font, 'size'):
                est_char_width = font.size * 0.5
                chars_per_line = max(1, int(max_width / est_char_width))
            else:
                chars_per_line = 40 # fallback for default font

            wrapped = textwrap.wrap(line, width=chars_per_line)
            lines.extend(wrapped if wrapped else [''])
        return lines

    def render(self) -> Image.Image:
        """Must be implemented by subclasses."""
        raise NotImplementedError()

class HookTemplate(BaseTemplate):
    def render(self) -> Image.Image:
        # High contrast, large bold text centered
        font = brand_engine.get_font(self.brand.font_heading, 80, self.brand.assets_dir)
        text_color = self._hex_to_rgb(self.brand.text_color)

        lines = self._wrap_text(self.slide.headline, font, self.width - 200)

        # Calculate total text height
        line_heights = [font.getbbox(line)[3] - font.getbbox(line)[1] if hasattr(font, 'getbbox') else 20 for line in lines]
        total_height = sum(line_heights) + (len(lines) - 1) * 20 # 20px line spacing

        y_text = (self.height - total_height) / 2

        for i, line in enumerate(lines):
            # Calculate width to center it
            bbox = font.getbbox(line) if hasattr(font, 'getbbox') else (0, 0, len(line)*10, 20)
            line_width = bbox[2] - bbox[0]
            x_text = (self.width - line_width) / 2

            self.draw.text((x_text, y_text), line, font=font, fill=text_color)
            y_text += line_heights[i] + 20

        return self.image

class ContentTemplate(BaseTemplate):
    def render(self) -> Image.Image:
        # Heading top left, body below
        heading_font = brand_engine.get_font(self.brand.font_heading, 60, self.brand.assets_dir)
        body_font = brand_engine.get_font(self.brand.font_body, 40, self.brand.assets_dir)
        text_color = self._hex_to_rgb(self.brand.text_color)

        y_offset = 100

        # Draw Image if provided
        if self.asset_path and Path(self.asset_path).exists():
            try:
                asset_img = Image.open(self.asset_path)
                asset_img = asset_img.resize((880, 500), Image.Resampling.LANCZOS)
                self.image.paste(asset_img, (100, y_offset))
                y_offset += 550
            except Exception as e:
                print(f"Failed to load asset {self.asset_path}: {e}")

        # Draw Headline
        heading_lines = self._wrap_text(self.slide.headline, heading_font, self.width - 200)
        for line in heading_lines:
            self.draw.text((100, y_offset), line, font=heading_font, fill=text_color)
            bbox = heading_font.getbbox(line) if hasattr(heading_font, 'getbbox') else (0,0,0,30)
            y_offset += (bbox[3] - bbox[1]) + 10

        y_offset += 40 # extra space before body

        # Draw Body
        if self.slide.body_text:
            body_lines = self._wrap_text(self.slide.body_text, body_font, self.width - 200)
            for line in body_lines:
                self.draw.text((100, y_offset), line, font=body_font, fill=text_color)
                bbox = body_font.getbbox(line) if hasattr(body_font, 'getbbox') else (0,0,0,20)
                y_offset += (bbox[3] - bbox[1]) + 15

        return self.image

class CTATemplate(BaseTemplate):
    def render(self) -> Image.Image:
        # Accent background, large headline, handle
        self.image = Image.new("RGB", (self.width, self.height), self._hex_to_rgb(self.brand.primary_color))
        self.draw = ImageDraw.Draw(self.image)

        font = brand_engine.get_font(self.brand.font_heading, 70, self.brand.assets_dir)
        handle_font = brand_engine.get_font(self.brand.font_body, 50, self.brand.assets_dir)
        text_color = self._hex_to_rgb(self.brand.background_color) # use bg color for contrast on primary color

        lines = self._wrap_text(self.slide.headline, font, self.width - 200)

        y_text = 300
        for line in lines:
            bbox = font.getbbox(line) if hasattr(font, 'getbbox') else (0,0,len(line)*10,30)
            x_text = (self.width - (bbox[2] - bbox[0])) / 2
            self.draw.text((x_text, y_text), line, font=font, fill=text_color)
            y_text += (bbox[3] - bbox[1]) + 20

        if self.brand.handle:
            y_text += 100
            bbox = handle_font.getbbox(self.brand.handle) if hasattr(handle_font, 'getbbox') else (0,0,len(self.brand.handle)*10,20)
            x_text = (self.width - (bbox[2] - bbox[0])) / 2
            self.draw.text((x_text, y_text), self.brand.handle, font=handle_font, fill=text_color)

        return self.image

class CompositionEngine:
    def render_slide(self, slide: SlideScript, brand: BrandProfile, output_path: str, asset_path: str = None) -> str:
        """
        Renders a single slide to the output_path.
        Returns the absolute path to the saved PNG.
        """
        if slide.slide_type == "hook":
            template = HookTemplate(brand, slide, asset_path)
        elif slide.slide_type == "cta":
            template = CTATemplate(brand, slide, asset_path)
        else:
            # content, stat, quote default to ContentTemplate for MVP
            template = ContentTemplate(brand, slide, asset_path)

        img = template.render()

        path = Path(output_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, format="PNG")

        return str(path)

composition_engine = CompositionEngine()
