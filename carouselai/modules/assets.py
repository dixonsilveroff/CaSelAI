import os
import uuid
import time
from pathlib import Path
from typing import Optional

from carouselai.core.context import SlideScript
from carouselai.core.config import OUTPUT_DIR

class AssetGenerationModule:
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_REGION", "global")
        self._client = None

    def _get_client(self):
        if self._client is None and self.project_id:
            try:
                from google import genai
                self._client = genai.Client(vertexai=True, project=self.project_id, location=self.location)
            except ImportError:
                print("Warning: google-genai not installed. Run: pip install google-genai")
                self.project_id = None
        return self._client

    def generate_asset(self, slide: SlideScript, job_id: str) -> Optional[str]:
        """
        Generates an image using Imagen 3 via the unified google-genai SDK.
        Returns the absolute path to the saved image, or None if fallback should be used.
        """
        if not slide.visual_prompt:
            return None

        client = self._get_client()

        if not client:
            print(f"Warning: GCP not configured or google-genai missing. Skipping Imagen generation for slide {slide.index}.")
            return None

        try:
            from google.genai import types
        except ImportError:
            print("Warning: google-genai missing. Skipping image generation.")
            return None

        try:
            prompt = slide.visual_prompt
            if slide.visual_style_note:
                prompt += f". Style: {slide.visual_style_note}"

            # Switched to the 'fast' model which has higher quota limits
            result = client.models.generate_images(
                model='imagen-3.0-fast-generate-001',
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="1:1"
                )
            )

            if result.generated_images:
                job_dir = OUTPUT_DIR / job_id / "assets"
                job_dir.mkdir(parents=True, exist_ok=True)

                filename = f"slide_{slide.index:02d}_{uuid.uuid4().hex[:8]}.png"
                output_path = job_dir / filename

                generated_image = result.generated_images[0]
                generated_image.image.save(str(output_path))

                # Add a brief pause to avoid hitting strict requests-per-minute quotas
                time.sleep(3)

                return str(output_path.resolve())

            return None

        except Exception as e:
            print(f"Imagen generation failed for slide {slide.index}: {e}. Falling back to solid background.")
            return None

asset_module = AssetGenerationModule()
