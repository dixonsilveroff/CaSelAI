import os
import uuid
from pathlib import Path
from typing import Optional

from carouselai.core.context import SlideScript
from carouselai.core.config import OUTPUT_DIR

class AssetGenerationModule:
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
        self._initialized = False

    def _init_vertex(self):
        if not self._initialized and self.project_id:
            try:
                import vertexai
                vertexai.init(project=self.project_id, location=self.location)
                self._initialized = True
            except ImportError:
                print("Warning: google-cloud-aiplatform not installed.")
                self.project_id = None

    def generate_asset(self, slide: SlideScript, job_id: str) -> Optional[str]:
        """
        Generates an image using Imagen 3 based on the visual_prompt.
        Returns the absolute path to the saved image, or None if fallback should be used.
        """
        if not slide.visual_prompt:
            return None

        self._init_vertex()

        if not self.project_id:
            print(f"Warning: GCP not configured. Skipping Imagen generation for slide {slide.index}.")
            return None

        try:
            from vertexai.preview.vision_models import ImageGenerationModel
        except ImportError:
            print("Warning: google-cloud-aiplatform missing. Skipping image generation.")
            return None

        try:
            # Note: "imagen-3.0-generate-001" is a placeholder for the latest available model
            model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")

            prompt = slide.visual_prompt
            if slide.visual_style_note:
                prompt += f". Style: {slide.visual_style_note}"

            response = model.generate_images(
                prompt=prompt,
                number_of_images=1,
                aspect_ratio="1:1"
            )

            if response.images:
                job_dir = OUTPUT_DIR / job_id / "assets"
                job_dir.mkdir(parents=True, exist_ok=True)

                filename = f"slide_{slide.index:02d}_{uuid.uuid4().hex[:8]}.png"
                output_path = job_dir / filename

                response.images[0].save(location=str(output_path))
                return str(output_path.resolve())

            return None

        except Exception as e:
            print(f"Imagen generation failed for slide {slide.index}: {e}. Falling back to solid background.")
            return None

asset_module = AssetGenerationModule()
