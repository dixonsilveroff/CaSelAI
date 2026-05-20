import argparse
import sys
from pathlib import Path

# Add the project root to sys.path so we can import carouselai cleanly
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from carouselai.modules.orchestrator import orchestrator
from carouselai.core.config import DEFAULT_SLIDE_COUNT, DEFAULT_GEMINI_MODEL

def main():
    parser = argparse.ArgumentParser(description="CarouselAI - Generate AI Carousels")
    parser.add_argument("command", choices=["generate"], help="Command to run")
    parser.add_argument("--topic", help="Topic for the carousel (required unless --script is used)")
    parser.add_argument("--brand", default="default", help="Brand profile ID (folder name in data/brands)")
    parser.add_argument("--slides", type=int, default=DEFAULT_SLIDE_COUNT, help="Number of slides to generate")
    parser.add_argument("--model", default=DEFAULT_GEMINI_MODEL, help="Gemini model to use")
    parser.add_argument("--no-imagen", action="store_true", help="Disable AI image generation (use solid colors instead)")
    parser.add_argument("--audience", default="General", help="Target audience for the copy (e.g., 'beginners', 'tech founders')")
    parser.add_argument("--instructions", help="Specific instructions for the AI copywriter (e.g., 'Make it funny and use emojis')")
    parser.add_argument("--script", help="Filename of the custom JSON script in data/scripts/ (e.g., 'my_script') or a full path. Bypasses AI text generation.")

    args = parser.parse_args()

    if args.command == "generate":
        if not args.topic and not args.script:
            parser.error("You must provide either a --topic or a --script")

        try:
            orchestrator.run_pipeline(
                topic=args.topic,
                brand_id=args.brand,
                slide_count=args.slides,
                gemini_model=args.model,
                use_imagen=not args.no_imagen,
                audience=args.audience,
                instructions=args.instructions,
                script_path=args.script
            )
        except Exception as e:
            print(f"\nError during generation: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
