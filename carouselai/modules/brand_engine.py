import json
from pathlib import Path
from typing import Dict
from PIL import ImageFont

from carouselai.core.context import BrandProfile
from carouselai.core.config import BRANDS_DIR, FONTS_DIR
from carouselai.core.exceptions import ResourceNotFoundError

class BrandEngine:
    """
    Manages loading and validation of BrandProfiles, and caches loaded fonts.
    """
    def __init__(self):
        # Cache for Pillow fonts: key is "filename_size"
        self._font_cache: Dict[str, ImageFont.FreeTypeFont] = {}

    def load_profile(self, brand_id: str) -> BrandProfile:
        """
        Loads a brand profile from its directory (BRANDS_DIR / brand_id / profile.json).
        """
        profile_path = BRANDS_DIR / brand_id / "profile.json"
        if not profile_path.exists():
            raise ResourceNotFoundError(f"Brand profile not found at {profile_path}")

        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Ensure assets_dir defaults to the brand directory if not specified
        assets_dir = Path(data.get("assets_dir", BRANDS_DIR / brand_id))
        if not assets_dir.is_absolute():
            assets_dir = (BRANDS_DIR / assets_dir).resolve()

        data["assets_dir"] = str(assets_dir)

        # Enforce the ID matches the requested brand_id
        data["id"] = brand_id

        return BrandProfile.model_validate(data)

    def get_font(self, font_filename: str, size: int, assets_dir: str) -> ImageFont.FreeTypeFont:
        """
        Loads a font, checking the brand's assets_dir first, then the global FONTS_DIR.
        Caches the font object for performance.
        """
        cache_key = f"{font_filename}_{size}"
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        # Check brand specific assets
        brand_font_path = Path(assets_dir) / font_filename
        if brand_font_path.exists():
            font = ImageFont.truetype(str(brand_font_path), size)
            self._font_cache[cache_key] = font
            return font

        # Check global fonts dir
        global_font_path = FONTS_DIR / font_filename
        if global_font_path.exists():
            font = ImageFont.truetype(str(global_font_path), size)
            self._font_cache[cache_key] = font
            return font

        # Fallback to default font to allow testing without TTF files
        print(f"Warning: Font '{font_filename}' not found. Falling back to default font.")
        font = ImageFont.load_default()
        self._font_cache[cache_key] = font
        return font

# Expose a singleton instance
brand_engine = BrandEngine()
