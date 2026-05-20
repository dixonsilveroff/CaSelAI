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
                # Initialize the unified client for the Vertex AI backend using ADC
                self._client = genai.Client(vertexai=True, project=self.project_id, location=self.location)
            except ImportError:
                print("Warning: google-genai not installed. Run: pip install google-genai")
                self.project_id = None
        return self._client

    def generate_asset(self, slide: SlideScript, job_id: str) -> Optional[str]:
        """
        Generates an image using Gemini 3.1 Flash Image Preview (Nano Banana).
        """
        if not slide.visual_prompt:
            return None

        client = self._get_client()

        if not client:
            print(f"Warning: API Key or GCP not configured. Skipping image generation for slide {slide.index}.")
            return None

        try:
            from google.genai import types
        except ImportError:
            print("Warning: google-genai missing. Skipping image generation.")
            return None

        try:
            prompt = f"Generate an image: {slide.visual_prompt}"
            if slide.visual_style_note:
                prompt += f". Style: {slide.visual_style_note}"

            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                )
            ]

            generate_content_config = types.GenerateContentConfig(
                temperature=1.0,
                response_modalities=["IMAGE"],
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
                ],
                image_config=types.ImageConfig(
                    aspect_ratio="1:1",
                    image_size="1K",
                    output_mime_type="image/png",
                ),
                thinking_config=types.ThinkingConfig(
                    thinking_level="MINIMAL",
                )
            )

            max_retries = 3
            response = None

            # Retry loop to handle 429 Quota Exhausted errors
            for attempt in range(max_retries):
                try:
                    # Using Gemini 3.1 Flash Image Preview
                    response = client.models.generate_content(
                        model='gemini-3.1-flash-image-preview',
                        contents=contents,
                        config=generate_content_config,
                    )
                    break # Success, exit retry loop
                except Exception as e:
                    error_str = str(e).lower()
                    if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = 15 * (attempt + 1) # Exponential-ish backoff: 15s, 30s
                            print(f"  [Rate Limit Hit] Waiting {wait_time}s before retrying slide {slide.index} (Attempt {attempt+1}/{max_retries})...")
                            time.sleep(wait_time)
                            continue
                    # If it's not a 429, or we're out of retries, raise the error to be caught by the outer block
                    raise e

            job_dir = OUTPUT_DIR / job_id / "assets"
            job_dir.mkdir(parents=True, exist_ok=True)

            filename = f"slide_{slide.index:02d}_{uuid.uuid4().hex[:8]}.png"
            output_path = job_dir / filename

            image_saved = False
            if response and response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        with open(output_path, "wb") as f:
                            f.write(part.inline_data.data)
                        image_saved = True
                        break

            if image_saved:
                # Base pause between successful generations to prevent hitting the limit in the first place
                print(f"  Asset generated for slide {slide.index}. Cooling down for 10s...")
                time.sleep(10)
                return str(output_path.resolve())

            print(f"Warning: No image data returned from model for slide {slide.index}.")
            return None

        except Exception as e:
            print(f"Image generation failed for slide {slide.index} after all retries: {e}. Falling back to solid background.")
            return None

asset_module = AssetGenerationModule()