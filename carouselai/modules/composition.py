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
        self.margin = 100
        self.image = Image.new("RGB", (self.width, self.height), self._hex_to_rgb(self.brand.background_color))
        self.draw = ImageDraw.Draw(self.image)

    def _hex_to_rgb(self, hex_color: str):
        """Converts a hex color string to an RGB tuple."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return (0, 0, 0)
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _wrap_text(self, text: str, font, max_width: int):
        """Wraps text accurately using Pillow's getlength."""
        if not text:
            return []

        lines = []
        for paragraph in text.split('\n'):
            words = paragraph.split()
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word]) if current_line else word
                # Check if the line with the new word fits
                if hasattr(font, 'getlength') and font.getlength(test_line) <= max_width:
                    current_line.append(word)
                elif not hasattr(font, 'getlength'):
                    # Fallback for default font
                    current_line.append(word)
                else:
                    # Line is too long, push current_line to lines and start new line
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        # Single word is longer than max_width
                        lines.append(word)
                        current_line = []
            if current_line:
                lines.append(' '.join(current_line))
        return lines

    def _draw_footer(self, is_accent_bg=False):
        """Draws the brand handle at the bottom center of the slide."""
        if not self.brand.handle:
            return

        font = brand_engine.get_font(self.brand.font_body, 30, self.brand.assets_dir)
        text_color = self._hex_to_rgb(self.brand.background_color if is_accent_bg else self.brand.text_color)

        # Determine width of the handle text
        text_width = font.getlength(self.brand.handle) if hasattr(font, 'getlength') else len(self.brand.handle) * 15
        x = (self.width - text_width) / 2
        y = self.height - 80  # 80px from bottom

        self.draw.text((x, y), self.brand.handle, font=font, fill=text_color)

    def render(self) -> Image.Image:
        """Must be implemented by subclasses."""
        raise NotImplementedError()

class HookTemplate(BaseTemplate):
    def render(self) -> Image.Image:
        # Accent background for the hook
        self.image = Image.new("RGB", (self.width, self.height), self._hex_to_rgb(self.brand.primary_color))
        self.draw = ImageDraw.Draw(self.image)

        font = brand_engine.get_font(self.brand.font_heading, 90, self.brand.assets_dir)
        text_color = self._hex_to_rgb(self.brand.background_color) # Use bg color on primary for contrast

        lines = self._wrap_text(self.slide.headline.upper(), font, self.width - (self.margin * 2))

        # Calculate vertical centering
        line_height = font.getbbox("A")[3] if hasattr(font, 'getbbox') else 90
        total_height = len(lines) * (line_height + 20)
        y_text = (self.height - total_height) / 2 - 50 # Slightly above true center

        for line in lines:
            text_width = font.getlength(line) if hasattr(font, 'getlength') else len(line) * 45
            x_text = (self.width - text_width) / 2
            self.draw.text((x_text, y_text), line, font=font, fill=text_color)
            y_text += line_height + 20

        self._draw_footer(is_accent_bg=True)
        return self.image

class ContentTemplate(BaseTemplate):
    def render(self) -> Image.Image:
        heading_font = brand_engine.get_font(self.brand.font_heading, 65, self.brand.assets_dir)
        body_font = brand_engine.get_font(self.brand.font_body, 45, self.brand.assets_dir)
        text_color = self._hex_to_rgb(self.brand.text_color)
        primary_color = self._hex_to_rgb(self.brand.primary_color)

        y_offset = self.margin

        # Draw a small accent bar at the top
        self.draw.rectangle([self.margin, y_offset, self.margin + 150, y_offset + 10], fill=primary_color)
        y_offset += 50

        # Draw Headline
        heading_lines = self._wrap_text(self.slide.headline, heading_font, self.width - (self.margin * 2))
        line_height_h = heading_font.getbbox("A")[3] if hasattr(heading_font, 'getbbox') else 65

        for line in heading_lines:
            self.draw.text((self.margin, y_offset), line, font=heading_font, fill=text_color)
            y_offset += line_height_h + 10

        y_offset += 40 # extra space before image/body

        # Draw Image if provided
        if self.asset_path and Path(self.asset_path).exists():
            try:
                asset_img = Image.open(self.asset_path).convert("RGBA")
                # Resize image to fit width, maintaining aspect ratio
                target_img_width = self.width - (self.margin * 2)
                aspect_ratio = asset_img.height / asset_img.width
                target_img_height = int(target_img_width * aspect_ratio)

                # Cap height so it doesn't push body text off screen
                if target_img_height > 450:
                    target_img_height = 450
                    target_img_width = int(target_img_height / aspect_ratio)

                asset_img = asset_img.resize((target_img_width, target_img_height), Image.Resampling.LANCZOS)

                # Center the image horizontally
                x_img_offset = int((self.width - target_img_width) / 2)

                self.image.paste(asset_img, (x_img_offset, int(y_offset)), asset_img)
                y_offset += target_img_height + 50
            except Exception as e:
                print(f"Failed to load asset {self.asset_path}: {e}")

        # Draw Body
        if self.slide.body_text:
            body_lines = self._wrap_text(self.slide.body_text, body_font, self.width - (self.margin * 2))
            line_height_b = body_font.getbbox("A")[3] if hasattr(body_font, 'getbbox') else 45
            for line in body_lines:
                self.draw.text((self.margin, y_offset), line, font=body_font, fill=text_color)
                y_offset += line_height_b + 15

        self._draw_footer()
        return self.image

class CTATemplate(BaseTemplate):
    def render(self) -> Image.Image:
        # Secondary color background for CTA
        self.image = Image.new("RGB", (self.width, self.height), self._hex_to_rgb(self.brand.secondary_color))
        self.draw = ImageDraw.Draw(self.image)

        font = brand_engine.get_font(self.brand.font_heading, 80, self.brand.assets_dir)
        tagline_font = brand_engine.get_font(self.brand.font_body, 50, self.brand.assets_dir)

        # Use background color for text on secondary color
        text_color = self._hex_to_rgb(self.brand.background_color)

        lines = self._wrap_text(self.slide.headline, font, self.width - (self.margin * 2))

        line_height = font.getbbox("A")[3] if hasattr(font, 'getbbox') else 80
        total_height = len(lines) * (line_height + 20)
        y_text = (self.height - total_height) / 2 - 100

        for line in lines:
            text_width = font.getlength(line) if hasattr(font, 'getlength') else len(line) * 40
            x_text = (self.width - text_width) / 2
            self.draw.text((x_text, y_text), line, font=font, fill=text_color)
            y_text += line_height + 20

        # Draw Tagline or Handle as primary CTA focus
        cta_bottom_text = self.brand.tagline if self.brand.tagline else self.brand.handle
        if cta_bottom_text:
            y_text += 80
            text_width = tagline_font.getlength(cta_bottom_text) if hasattr(tagline_font, 'getlength') else len(cta_bottom_text) * 25
            x_text = (self.width - text_width) / 2

            # Draw a button-like box behind it
            padding = 30
            self.draw.rounded_rectangle(
                [x_text - padding, y_text - padding + 10, x_text + text_width + padding, y_text + 50 + padding],
                radius=15,
                fill=self._hex_to_rgb(self.brand.primary_color)
            )

            self.draw.text((x_text, y_text), cta_bottom_text, font=tagline_font, fill=self._hex_to_rgb(self.brand.background_color))

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
            template = ContentTemplate(brand, slide, asset_path)

        img = template.render()

        path = Path(output_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, format="PNG")

        return str(path)

composition_engine = CompositionEngine()
