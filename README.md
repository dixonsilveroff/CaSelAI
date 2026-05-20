# CarouselAI

CarouselAI is a modular, AI-powered command-line tool designed to generate professional, multi-slide social media carousels from a single topic prompt. 

It leverages Google's **Gemini** for structured copywriting and the advanced **Gemini 3.1 Flash Image Preview ("Nano Banana")** model for high-quality background asset generation. Slides are automatically composited and rendered locally using Pillow.

## 🚀 Features

* **End-to-End Generation:** Type a topic, get a folder full of fully rendered `.png` slides ready to post.
* **Smart Content Engine:** Uses Gemini to structure carousels with compelling Hooks, educational Content, and strong CTAs based on your target audience.
* **Advanced Visuals:** Uses Gemini's multimodal capabilities to generate unique background images for every slide.
* **Intelligent Compositing:** Automatically resizes generated assets, applies a contrast-enhancing dark wash overlay, and dynamically switches text to white for perfect readability.
* **Robust Rate Limiting:** Built-in exponential backoff and retry logic ensures large carousels generate smoothly without hitting Google Cloud quota limits (`429` errors).
* **Graceful Fallbacks:** If API generation fails or credentials aren't set, the system gracefully falls back to brand-colored solid backgrounds and placeholder text so your pipeline never crashes.
* **Total Brand Control:** Configure colors, custom `.ttf` fonts, handles, and tone-of-voice in simple JSON files.

---

## 🛠️ Setup & Installation

### 1. Prerequisites
* Python 3.11 or higher
* A Google Cloud Project with the **Vertex AI API** enabled.

### 2. Install Dependencies
Initialize your virtual environment and install the required packages:

```bash
python -m venv .venv
source .venv/Scripts/activate  # On Windows
pip install -r requirements.txt
pip install google-genai       # Ensure the new unified SDK is installed
```

### 3. Authentication
CarouselAI uses Google Cloud Application Default Credentials (ADC) to authenticate with Vertex AI. This ensures enterprise-grade security and avoids the need to manage standalone API keys.

1. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
2. Authenticate your local machine:
   ```bash
   gcloud auth application-default login
   ```
3. Create a `.env` file in the root of the project and set your Project ID:
   ```env
   GOOGLE_CLOUD_PROJECT=your-gcp-project-id
   GOOGLE_CLOUD_REGION=us-central1
   ```

---

## 💻 Usage

Run the CLI using the `generate` command.

### Basic Generation
```bash
python carouselai/cli.py generate --topic "5 Tips for Remote Teams"
```

### Advanced Generation (All Flags)
You can heavily steer the AI using the available CLI flags:

```bash
python carouselai/cli.py generate \
  --topic "AI in Real Estate" \
  --brand "default" \
  --slides 8 \
  --audience "Skeptical real estate brokers" \
  --instructions "Make the hook a controversial question. End with a CTA to download a guide."
```

### Custom Scripts (Bypassing AI Copywriting)
If you want total control over the copy and visual prompts, you can provide a custom JSON file instead of a topic. The system will skip text generation and immediately begin rendering your exact script.

```bash
python carouselai/cli.py generate --script scripts/sample_script.json --brand "my_startup"
```
*(Note: If your script is inside a folder, you must include the folder path in the command, as shown above).*

### Available CLI Flags
| Flag | Description | Default |
|------|-------------|---------|
| `--topic` | The core subject of your carousel. (Required unless `--script` is used). | None |
| `--script`| Path to a custom JSON script file. Overrides AI text generation. | None |
| `--brand` | The folder name of the brand profile to use (located in `data/brands/`). | `default` |
| `--slides` | The total number of slides to generate. | `6` |
| `--audience` | Tell the AI exactly who the copy should be written for. | `General` |
| `--instructions` | Specific steering instructions for the copywriter (e.g., tone, structure). | None |
| `--no-imagen` | Disable AI image generation. Slides will render using solid brand colors. | False |
| `--model` | The Gemini model used for *text* generation. | `gemini-1.5-flash` |

---

## 🎨 Brand Management

CarouselAI allows you to manage multiple distinct visual identities. Brands are stored in the `data/brands/` directory.

### Creating a Custom Brand
1. Create a new folder in `data/brands/` (e.g., `data/brands/my_startup/`).
2. Create a `profile.json` file inside that folder.
3. Download your custom `.ttf` fonts and place them in the `data/fonts/` directory (or directly in your brand folder).

**Example `profile.json`:**
```json
{
  "name": "My Startup",
  "primary_color": "#FF5733",
  "secondary_color": "#C70039",
  "background_color": "#1A1A1A",
  "text_color": "#FFFFFF",
  "font_heading": "Montserrat-Bold.ttf",
  "font_body": "OpenSans-Regular.ttf",
  "handle": "@mystartup",
  "tone_keywords": "disruptive, authoritative, tech-forward",
  "tagline": "Build faster."
}
```

### Using Your Brand
When generating, simply pass the name of your folder to the `--brand` flag:
```bash
python carouselai/cli.py generate --topic "Launch Announcement" --brand "my_startup"
```

---

## 📂 Output

Generated carousels are saved to the `data/output/` directory. Each job gets a unique folder containing:
1. `slide_00.png` to `slide_0N.png`: The fully rendered, ready-to-post slides.
2. `manifest.json`: A detailed metadata file containing the prompt, slide copy, fallbacks, and rendering paths.
3. `assets/`: A subfolder containing the raw, un-composited background images generated by the AI (useful if you want to repurpose them later).