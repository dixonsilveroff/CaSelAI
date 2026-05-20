import uuid
import json
from pathlib import Path

from carouselai.core.context import PipelineContext
from carouselai.modules.brand_engine import brand_engine
from carouselai.modules.content import content_module
from carouselai.modules.assets import asset_module
from carouselai.modules.composition import composition_engine
from carouselai.core.config import OUTPUT_DIR, DEFAULT_GEMINI_MODEL, DEFAULT_SLIDE_COUNT

class PipelineOrchestrator:

    def run_pipeline(
        self,
        topic: str,
        brand_id: str,
        slide_count: int = DEFAULT_SLIDE_COUNT,
        gemini_model: str = DEFAULT_GEMINI_MODEL,
        use_imagen: bool = True,
        audience: str = "General",
        instructions: str = None
    ) -> PipelineContext:

        job_id = str(uuid.uuid4())
        print(f"Starting pipeline for job {job_id}")
        print(f"Topic: '{topic}'")

        # 1. Load Brand Profile
        print(f"Loading brand profile '{brand_id}'...")
        brand = brand_engine.load_profile(brand_id)

        context = PipelineContext(
            job_id=job_id,
            topic=topic,
            brand=brand,
            slide_count=slide_count,
            gemini_model=gemini_model,
            use_imagen=use_imagen,
            audience=audience,
            instructions=instructions
        )

        # 2. Content Intelligence Module
        print("Generating carousel script via Content Intelligence Module...")
        context.carousel_script = content_module.generate_script(
            topic=context.topic,
            brand=context.brand,
            slide_count=context.slide_count,
            model_name=context.gemini_model,
            audience=context.audience,
            instructions=context.instructions
        )
        print(f"Script generated with {len(context.carousel_script.slides)} slides.")

        # 3. Asset Generation Module
        if context.use_imagen:
            print("Generating visual assets via Asset Generation Module...")
            for slide in context.carousel_script.slides:
                if slide.visual_prompt:
                    print(f"  Generating asset for slide {slide.index}...")
                    asset_path = asset_module.generate_asset(slide, context.job_id)
                    if asset_path:
                        context.generated_assets[slide.index] = asset_path
                    else:
                        context.fallback_indices.append(slide.index)

        # 4. Composition Engine
        print("Rendering slides via Composition Engine...")
        job_output_dir = OUTPUT_DIR / context.job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        for slide in context.carousel_script.slides:
            print(f"  Rendering slide {slide.index} ({slide.slide_type})...")
            asset_path = context.generated_assets.get(slide.index)
            output_filename = f"slide_{slide.index:02d}.png"
            output_path = job_output_dir / output_filename

            rendered_path = composition_engine.render_slide(
                slide=slide,
                brand=context.brand,
                output_path=str(output_path),
                asset_path=asset_path
            )
            context.rendered_slides.append(rendered_path)

        # 5. Output Manager
        print("Packaging output manifest...")
        manifest_path = job_output_dir / "manifest.json"

        manifest_data = {
            "job_id": context.job_id,
            "topic": context.topic,
            "brand": context.brand.name,
            "slide_count": context.slide_count,
            "fallback_count": len(context.fallback_indices),
            "fallback_indices": context.fallback_indices,
            "slides": context.rendered_slides
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        print(f"Pipeline complete! Output saved to: {job_output_dir}")
        return context

orchestrator = PipelineOrchestrator()
