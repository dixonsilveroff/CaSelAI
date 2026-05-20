import json
import os

from carouselai.core.context import CarouselScript, BrandProfile
from carouselai.core.exceptions import PipelineError

# We import vertexai lazily inside the class to avoid crashing on startup
# if the google-cloud-aiplatform package isn't installed during initial testing.

class ContentIntelligenceModule:

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
                self.project_id = None # Force dummy mode

    def generate_script(
        self,
        topic: str,
        brand: BrandProfile,
        slide_count: int,
        model_name: str
    ) -> CarouselScript:

        self._init_vertex()

        if not self.project_id:
            print("Warning: GOOGLE_CLOUD_PROJECT not set (or SDK missing). Using dummy script generator.")
            return self._generate_dummy_script(topic, brand, slide_count)

        try:
            from vertexai.generative_models import GenerativeModel, GenerationConfig
        except ImportError:
            raise PipelineError("google-cloud-aiplatform is required for live generation", stage="content_intelligence")

        model = GenerativeModel(model_name)

        prompt = f"""
        You are an expert social media copywriter. Create a carousel script about "{topic}".
        The carousel must have exactly {slide_count} slides.

        Brand Tone: {brand.tone_keywords}
        Brand Name: {brand.name}

        Output valid JSON exactly matching this schema:
        {{
            "title": "Internal title",
            "target_audience": "Who this is for",
            "slides": [
                {{
                    "index": 0,
                    "slide_type": "hook", // Options: hook, content, stat, quote, cta
                    "headline": "Catchy short headline",
                    "body_text": "Optional body text",
                    "visual_prompt": "Optional visual description for AI image generation, or null if simple design",
                    "visual_style_note": "Optional style note"
                }}
            ]
        }}

        Rules:
        - Slide index must start at 0 and go sequentially up to {slide_count - 1}.
        - Slide 0 must be 'hook'.
        - The last slide must be 'cta'.
        - Keep text concise for a carousel format.
        """

        generation_config = GenerationConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )

        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )

            response_json = json.loads(response.text)

            from carouselai.core.context import SlideScript
            slides = []
            for s in response_json.get("slides", []):
                slides.append(SlideScript(**s))

            return CarouselScript(
                title=response_json.get("title", "Generated Carousel"),
                target_audience=response_json.get("target_audience", "General"),
                slides=slides
            )

        except Exception as e:
            raise PipelineError(f"Failed to generate script via Gemini: {e}", stage="content_intelligence")

    def _generate_dummy_script(self, topic: str, brand: BrandProfile, slide_count: int) -> CarouselScript:
        """Fallback for local testing without GCP configured."""
        from carouselai.core.context import SlideScript
        slides = [
            SlideScript(index=0, slide_type="hook", headline=f"5 Truths About {topic}", body_text=None, visual_prompt=None, visual_style_note=None)
        ]

        for i in range(1, slide_count - 1):
            slides.append(SlideScript(
                index=i,
                slide_type="content",
                headline=f"Point #{i}",
                body_text=f"Here is some highly engaging content about {topic} matching a {brand.tone_keywords} tone.",
                visual_prompt=None,
                visual_style_note=None
            ))

        slides.append(SlideScript(
            index=slide_count-1,
            slide_type="cta",
            headline="Save this post!",
            body_text=None,
            visual_prompt=None,
            visual_style_note=None
        ))

        return CarouselScript(title=topic, target_audience="Everyone", slides=slides)

content_module = ContentIntelligenceModule()
