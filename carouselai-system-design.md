# CarouselAI — System Design Document
**Version:** 1.0 | **Author:** System Design Agent | **Date:** May 2026
**System Type:** Modular Monolith (Python) | **Deployment:** Local / Single Cloud VM

---

## Table of Contents
1. [System Architecture — High-Level Design (HLD)](#phase-1)
2. [Database Schema & Models — Low-Level Design (LLD)](#phase-2)
3. [Interface Design — APIs & Interaction Contracts](#phase-3)
4. [Technical Specifications](#phase-4)
5. [Non-Functional Requirements (NFR) Plan](#phase-5)
6. [Implementation Roadmap](#roadmap)

---

## Phase 1: System Architecture — High-Level Design (HLD) {#phase-1}

### 1.1 Architecture Overview

**Architecture Style:** Modular Monolith with a Pipeline execution model.

CarouselAI is a single deployable Python application divided into well-bounded internal modules. Each module owns a specific layer of the carousel generation process — content intelligence, asset generation, brand rendering, and composition. These modules communicate through a defined internal `PipelineContext` object rather than through HTTP or message queues.

**Why not microservices?** This is a solo-built, MVP-stage tool with a single user (or small team). Microservices would introduce distributed systems complexity — network calls between services, independent deployments, inter-service auth — none of which you need at this stage. A modular monolith gives you clean separation of concerns and the ability to extract a service later if load demands it, without paying the operational tax upfront.

**Why not serverless?** The Imagen 3 generation step can take 8–20 seconds per image. Serverless function timeouts and cold starts make this architecture hostile for long-running inference pipelines.

**Key design principles followed:**
- **Single Responsibility per Module**: the Brand Engine knows nothing about AI; the Composition Engine knows nothing about Gemini prompts.
- **Dependency Injection for AI Clients**: Vertex AI clients are injected at app startup from a single factory, making them easy to swap or mock in tests.
- **Immutable Pipeline Context**: the `PipelineContext` object passed through the pipeline is append-only — each stage adds its outputs without mutating upstream results, giving you a full audit trail of every generation run.
- **Brand Profile as First-Class Config**: brand identity is a schema-validated configuration object, not scattered constants, so multi-brand support is possible from day one.

---

### 1.2 Component Diagram

```
Component: Streamlit UI (Frontend)
Type: Web UI
Responsibility: Accepts user topic input, brand profile selection, carousel format
                preference, and trigger. Displays generated slides for preview and download.
Technology: Streamlit 1.35+
Owns: Nothing — stateless presentation layer

Component: FastAPI Application (API Layer)
Type: HTTP Service
Responsibility: Receives generation requests from the UI or CLI, orchestrates the
                pipeline, returns generation status and output file paths.
Technology: FastAPI 0.111+, Uvicorn
Owns: Job state (in-memory or SQLite for local runs)

Component: Pipeline Orchestrator
Type: Internal Module (Python class)
Responsibility: Sequences the four pipeline stages in order, passes PipelineContext
                between them, handles per-stage error recovery and retries.
Technology: Pure Python — no framework dependency
Owns: PipelineContext lifecycle

Component: Content Intelligence Module (CIM)
Type: Internal Module — AI Client
Responsibility: Calls Gemini 1.5 Pro/Flash via Vertex AI to generate a structured
                carousel script: hook, slide-by-slide copy, CTA, suggested visual
                direction per slide.
Technology: google-cloud-aiplatform SDK, Gemini 1.5 Flash (fast) or Pro (quality)
Owns: CarouselScript schema

Component: Asset Generation Module (AGM)
Type: Internal Module — AI Client
Responsibility: Calls Imagen 3 via Vertex AI to generate background/hero images
                for slides that require AI visuals. Falls back to brand-defined solid
                colour backgrounds when image generation is not needed.
Technology: google-cloud-aiplatform SDK, Imagen 3
Owns: Generated image files in the working temp directory

Component: Brand Engine
Type: Internal Module
Responsibility: Loads and validates a brand profile JSON file. Exposes typed brand
                parameters (colours, fonts, logo path, tone keywords, handle) to all
                downstream modules. Handles font loading from local TTF files.
Technology: Pydantic v2 (schema validation), Pillow for font loading
Owns: BrandProfile schema and validated brand assets

Component: Composition Engine
Type: Internal Module — Rendering
Responsibility: Takes the CarouselScript + generated assets + BrandProfile and renders
                each slide as a 1080×1080px PNG using Pillow. Applies layout templates
                per slide type (Hook, Content, Stat, Quote, CTA).
Technology: Pillow 10+, optionally CairoSVG for vector logo handling
Owns: Final rendered slide PNGs

Component: Output Manager
Type: Internal Module
Responsibility: Packages rendered slides into a numbered, named output folder.
                Generates a job manifest JSON summarising the run (topic, brand used,
                Gemini model, timestamp, file paths).
Technology: Python stdlib (pathlib, shutil, json)
Owns: Output directory structure and job manifest files

Component: SQLite Job Store
Type: Database (local file)
Responsibility: Persists job history (topic, brand profile, timestamp, status,
                output path) for the history view in the UI. Not used for any
                transactional workload.
Technology: SQLite via Python sqlite3 or SQLAlchemy Core
Owns: jobs table, brand_profiles table

Component: Brand Profile Store
Type: Filesystem (structured directory)
Responsibility: Stores brand profile JSON files and referenced font/logo assets.
                One subdirectory per brand profile.
Technology: Local filesystem, structured by convention
Owns: Brand profile configs and static brand assets
```

---

### 1.3 System Interaction Map

| From | To | Protocol | Direction | Notes |
|------|----|----------|-----------|-------|
| Streamlit UI | FastAPI | HTTP/REST | Sync | POST /v1/generate triggers a pipeline run |
| FastAPI | Pipeline Orchestrator | In-process function call | Sync | Direct Python call, no network hop |
| Pipeline Orchestrator | Content Intelligence Module | In-process | Sync | Passes PipelineContext, receives CarouselScript |
| Pipeline Orchestrator | Asset Generation Module | In-process | Sync | One Imagen call per slide requiring AI visuals |
| Pipeline Orchestrator | Brand Engine | In-process | Sync | Brand Engine is initialised once per request |
| Pipeline Orchestrator | Composition Engine | In-process | Sync | Called once per slide |
| Pipeline Orchestrator | Output Manager | In-process | Sync | Called at pipeline end |
| Content Intelligence Module | Vertex AI (Gemini) | HTTPS | Sync | google-cloud-aiplatform SDK, authenticated via ADC |
| Asset Generation Module | Vertex AI (Imagen 3) | HTTPS | Sync | google-cloud-aiplatform SDK, authenticated via ADC |
| FastAPI | SQLite Job Store | In-process (SQLAlchemy) | Sync | Job status reads/writes |
| Brand Engine | Brand Profile Store | Filesystem read | Sync | Reads JSON + asset files at request time |
| Output Manager | Filesystem | Filesystem write | Sync | Writes PNG files + manifest to output directory |
| Streamlit UI | Filesystem | Filesystem read | Sync | Reads output PNGs for preview/download |

---

### 1.4 Data Flow Narratives

**Flow 1 — Carousel Generation (Happy Path)**

1. User enters a topic (e.g., "5 mistakes contractors make with BOQ") and selects a brand profile in the Streamlit UI.
2. UI sends `POST /v1/generate` to FastAPI with `{topic, brand_profile_id, slide_count, format}`.
3. FastAPI creates a job record in SQLite with status `pending`, then calls the Pipeline Orchestrator.
4. Orchestrator instantiates a `PipelineContext` with the job parameters and calls the Brand Engine, which loads and validates the BrandProfile from the filesystem.
5. Orchestrator calls the Content Intelligence Module. CIM constructs a system-prompt-enriched Gemini request specifying the carousel structure rules (hook, progressive value slides, CTA) and the brand's tone keywords. Gemini returns a structured JSON carousel script.
6. Orchestrator iterates over the carousel script slides. For each slide flagged as needing an AI visual, it calls the Asset Generation Module, which calls Imagen 3 with a slide-specific prompt. Images are written to a temp directory.
7. For each slide, the Orchestrator calls the Composition Engine with the slide copy, asset path (if any), and BrandProfile. The engine selects the correct layout template class, renders the slide, and writes a 1080×1080px PNG to the temp output directory.
8. After all slides are rendered, the Output Manager packages them into a named output folder, writes the job manifest, and returns the output path.
9. FastAPI updates the job record to `completed`, returns the output path to the UI.
10. Streamlit reads the PNG files from the output path and renders them as a preview carousel with a download button.

**Flow 2 — Brand Profile Creation**

1. User fills out the Brand Profile form in the Streamlit UI: name, primary colour, secondary colour, font name (from a curated dropdown of downloaded Google Fonts), logo upload, handle, tone keywords.
2. UI sends `POST /v1/brands` to FastAPI.
3. FastAPI validates the payload via Pydantic, writes the brand profile JSON to the Brand Profile Store directory, saves the uploaded logo to the brand subdirectory, and creates a record in the `brand_profiles` SQLite table.
4. Brand profile is immediately available for generation requests.

**Flow 3 — Job History & Replay**

1. User navigates to the History tab in the Streamlit UI.
2. UI sends `GET /v1/jobs` to FastAPI.
3. FastAPI queries the SQLite `jobs` table, returns a list of past jobs with status, topic, timestamp, and output path.
4. User selects a past job; UI displays the rendered slides from the saved output directory.
5. User can click "Regenerate" — UI pre-fills the generation form with the same topic and brand profile, allowing a one-click rerun with a fresh generation.

**Flow 4 — Partial Pipeline Failure (Imagen Timeout)**

1. During generation, Imagen 3 fails or times out on a specific slide.
2. Asset Generation Module catches the exception and returns a `FallbackAsset` signal to the Orchestrator.
3. Orchestrator passes the `FallbackAsset` signal to the Composition Engine, which renders that slide using the brand's solid background colour instead of the AI image.
4. The pipeline continues without aborting. The job manifest flags which slides used fallback rendering.
5. The completed job is returned to the user with a warning indicator on affected slides in the UI.

**Flow 5 — CLI Generation (Headless Mode)**

1. User runs `python -m carouselai generate --topic "..." --brand default --slides 6 --output ./output`.
2. CLI bypasses FastAPI entirely and calls the Pipeline Orchestrator directly, using the same internal modules.
3. Output PNGs are written to the specified directory. No UI interaction required.

---

### 1.5 External Integrations

| Service | Provider | Data Crossing Boundary | Auth Method | Notes |
|---------|----------|----------------------|-------------|-------|
| Gemini 1.5 Flash/Pro | Google Vertex AI | Carousel topic, brand tone keywords, system prompt → returns carousel script JSON | Application Default Credentials (ADC) via gcloud auth | No PII crosses this boundary |
| Imagen 3 | Google Vertex AI | Slide-level visual description prompt → returns generated image bytes | ADC | Prompts should not include any personal data |
| Google Fonts (setup time only) | fonts.google.com | Font TTF file download during environment setup | None (public) | Fonts stored locally after download; no runtime dependency |

---

### 1.6 Deployment Topology

**MVP (Local):** Single developer machine running all components as one Python process. Streamlit UI on `localhost:8501`, FastAPI on `localhost:8000`. SQLite DB and filesystem storage are local directories. Vertex AI calls go out over the internet via ADC.

**V2 (Single Cloud VM):** One `e2-standard-2` (2 vCPU, 8GB RAM) Google Cloud VM in `africa-south1` (Johannesburg) or `us-central1` depending on latency preference. FastAPI served via Uvicorn behind Nginx. Streamlit served on the same VM. All storage remains local (no object storage needed at this scale). Cloud Run is explicitly **not** recommended here because Imagen generation duration can exceed Cloud Run's default timeout without configuration changes and because persistent local filesystem state for jobs/brands is simpler than managing GCS mounts.

---

⚠️ **Open Questions / Assumptions — Phase 1**
- Assumed single-user for MVP. If multiple users are needed concurrently, the Pipeline Orchestrator must be made async (FastAPI BackgroundTasks or Celery) so long Imagen calls don't block the HTTP worker.
- Assumed Vertex AI Imagen 3 is accessible on your Google Cloud project. Imagen 3 access may require allowlisting — verify in the Google Cloud Console before implementation.
- Assumed brand profiles are managed manually for MVP. A full brand editor UI is Phase 2 scope.
- App name is placeholder "CarouselAI" — rename as you see fit.

---

## Phase 2: Database Schema & Models — Low-Level Design (LLD) {#phase-2}

### 2.1 Database Technology Choices

**Primary store — SQLite (local file):** This is a personal productivity tool at MVP stage. SQLite is perfectly appropriate — zero infrastructure, ACID-compliant, and queried via standard SQL. The data volume will never stress it: hundreds of jobs and a dozen brand profiles.

**Filesystem as secondary store:** Generated PNG files, brand logos, and brand profile JSON configs live on the filesystem under a structured directory tree. This is preferable to storing binary blobs in SQLite, which degrades performance.

**No cache layer:** No Redis or in-memory cache is warranted. The only "hot data" is the BrandProfile, which is a small JSON read at request time — fast enough without caching at this scale.

**No object storage:** GCS or S3 would add complexity and egress cost with no benefit for a local or single-VM deployment.

---

### 2.2 Entity Relationship Overview

```
Entity: brand_profiles
Relationships:
  - has many: jobs (one-to-many, via brand_profile_id)

Entity: jobs
Relationships:
  - belongs to: brand_profiles (many-to-one)
  - has many: job_slides (one-to-many)

Entity: job_slides
Relationships:
  - belongs to: jobs (many-to-one)
```

---

### 2.3 Schema Definitions

**Table: `brand_profiles`**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | TEXT (UUID) | PK, NOT NULL | Unique brand profile identifier |
| name | TEXT | UNIQUE, NOT NULL | Human-readable brand name (e.g., "ConSync") |
| primary_color | TEXT | NOT NULL | Hex colour code, e.g., "#1A1A2E" |
| secondary_color | TEXT | NOT NULL | Hex colour code for accents |
| background_color | TEXT | NOT NULL | Default slide background hex |
| text_color | TEXT | NOT NULL | Primary text hex |
| font_heading | TEXT | NOT NULL | Filename of heading TTF in brand assets dir |
| font_body | TEXT | NOT NULL | Filename of body TTF in brand assets dir |
| logo_filename | TEXT | NULLABLE | Filename of logo PNG/SVG in brand assets dir |
| handle | TEXT | NULLABLE | Instagram handle, e.g., "@consync_ng" |
| tone_keywords | TEXT | NOT NULL | Comma-separated tone adjectives, e.g., "professional, direct, Nigeria-aware" |
| tagline | TEXT | NULLABLE | Short brand tagline shown in CTA slides |
| assets_dir | TEXT | NOT NULL | Absolute filesystem path to brand assets directory |
| created_at | TEXT | DEFAULT (datetime('now')) | ISO 8601 timestamp |
| updated_at | TEXT | DEFAULT (datetime('now')) | ISO 8601 timestamp |

**Table: `jobs`**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | TEXT (UUID) | PK, NOT NULL | Unique job identifier |
| brand_profile_id | TEXT | FK → brand_profiles.id, NOT NULL | Brand used for this job |
| topic | TEXT | NOT NULL | User-provided carousel topic |
| slide_count | INTEGER | NOT NULL, DEFAULT 6 | Number of slides requested |
| gemini_model | TEXT | NOT NULL | e.g., "gemini-1.5-flash" |
| status | TEXT | NOT NULL, DEFAULT 'pending' | Enum: pending, running, completed, failed |
| output_dir | TEXT | NULLABLE | Absolute path to output folder once complete |
| error_message | TEXT | NULLABLE | Error detail if status = failed |
| fallback_slide_indices | TEXT | NULLABLE | Comma-separated slide indices that used fallback rendering |
| created_at | TEXT | DEFAULT (datetime('now')) | ISO 8601 timestamp |
| completed_at | TEXT | NULLABLE | ISO 8601 timestamp when pipeline finished |

**Table: `job_slides`**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | TEXT (UUID) | PK, NOT NULL | Unique slide record identifier |
| job_id | TEXT | FK → jobs.id, NOT NULL | Parent job |
| slide_index | INTEGER | NOT NULL | 0-based position in carousel |
| slide_type | TEXT | NOT NULL | Enum: hook, content, stat, quote, cta |
| headline | TEXT | NOT NULL | Generated headline copy |
| body_text | TEXT | NULLABLE | Generated body copy |
| visual_prompt | TEXT | NULLABLE | Imagen prompt used for this slide |
| asset_path | TEXT | NULLABLE | Filesystem path to generated/selected image |
| output_png_path | TEXT | NULLABLE | Filesystem path to final rendered slide PNG |
| used_fallback | INTEGER | NOT NULL, DEFAULT 0 | Boolean: 1 if Imagen failed and solid BG used |

---

### 2.4 Indexes & Query Optimization

**`brand_profiles`**
- Primary key: `id` (UUID TEXT)
- Unique index on `name` — profile lookup by name from UI dropdown

**`jobs`**
- Primary key: `id` (UUID TEXT)
- Index on `brand_profile_id` — for filtering history by brand
- Index on `created_at DESC` — history view always ordered by recency
- Index on `status` — for filtering running jobs on app startup (to detect interrupted jobs)

**`job_slides`**
- Primary key: `id` (UUID TEXT)
- Composite index on `(job_id, slide_index)` — the primary access pattern: fetch all slides for a job in order
- Index on `job_id` — foreign key lookups

---

### 2.5 Caching Strategy

No distributed cache is warranted. The Brand Engine applies a simple in-process Python dict cache for the duration of a single request:

| Data | Cache Scope | TTL | Invalidation |
|------|-------------|-----|--------------|
| BrandProfile object | Per-request in-memory (dict keyed by `brand_profile_id`) | Duration of one pipeline run | Not needed — profile is re-read on next request |
| Font objects (Pillow ImageFont) | Module-level Python dict (persists across requests) | Process lifetime | Restart the app process |
| Vertex AI client handles | Module-level singleton | Process lifetime | Restart the app process |

---

### 2.6 Data Migration & Versioning Strategy

**Tooling:** Alembic (with SQLAlchemy Core) for schema migrations, even for SQLite. This gives you a version-tracked migration history that can be replayed on a new machine or upgraded deployment without manual SQL.

**Migration convention:** Each migration file is named `YYYYMMDD_HHMMSS_description.py`. Running `alembic upgrade head` on startup ensures the schema is always current.

**Seed data:** A `seed_brands.py` script creates a default `"default"` brand profile with sensible neutral colours on first run, so the app is usable immediately after install.

---

⚠️ **Open Questions / Assumptions — Phase 2**
- SQLite is sufficient for solo or small team use. If CarouselAI ever becomes a multi-user SaaS, migrate to PostgreSQL — the SQLAlchemy abstraction makes this a configuration change, not a rewrite.
- `tone_keywords` stored as comma-separated text for simplicity. If tone becomes more complex (per-audience profiles, tone matrices), normalise into a separate table.

---

## Phase 3: Interface Design — APIs & Interaction Contracts {#phase-3}

### 3.1 API Style & Standards

**Style:** REST. Simple, stateless, and trivially consumable by Streamlit's `requests` calls or a CLI script.

**Versioning:** URL prefix `/v1/` — enables a non-breaking `/v2/` when the output format or generation contract changes.

**Authentication:** None for local deployment (loopback only). If deployed to a cloud VM exposed over the internet, add a single static API key passed in the `X-API-Key` header, validated at the FastAPI middleware layer.

**Standard Response Envelope:**
```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {}
}
```

---

### 3.2 API Endpoint Catalogue

```
POST /v1/generate
Description: Trigger a full carousel generation pipeline run
Auth: None (local) / X-API-Key (VM deployment)
Rate Limit: 5 concurrent jobs max (enforced by in-process semaphore)

Request Body:
{
  "topic": "string, required — the carousel subject",
  "brand_profile_id": "string (UUID), required",
  "slide_count": "integer, optional, default 6, min 3, max 10",
  "gemini_model": "string, optional, default 'gemini-1.5-flash'",
                   // Options: gemini-1.5-flash | gemini-1.5-pro
  "use_imagen": "boolean, optional, default true — set false to use solid BG only"
}

Response 200:
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "completed",
    "output_dir": "/path/to/output/job_uuid/",
    "slide_count": 6,
    "slides": [
      {
        "index": 0,
        "type": "hook",
        "output_png_path": "/path/to/slide_00.png",
        "used_fallback": false
      }
    ],
    "fallback_count": 0,
    "completed_at": "2026-05-19T14:32:00Z"
  },
  "error": null
}

Errors:
  400 — Validation error (missing required fields, slide_count out of range)
  404 — brand_profile_id not found
  500 — Pipeline failure (Vertex AI error, Pillow render error)
  503 — Max concurrent jobs reached
```

```
GET /v1/generate/{job_id}/status
Description: Poll the status of an in-progress or completed job
Auth: None (local)

Response 200:
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "running | completed | failed",
    "progress": {
      "current_slide": 3,
      "total_slides": 6,
      "current_stage": "asset_generation | composition | complete"
    },
    "error_message": null
  }
}

Errors:
  404 — job_id not found
```

```
GET /v1/jobs
Description: List all past generation jobs, ordered by recency
Auth: None (local)
Query Params:
  limit (integer, default 20, max 100)
  brand_profile_id (string, optional filter)
  status (string, optional filter: completed | failed)

Response 200:
{
  "success": true,
  "data": [
    {
      "job_id": "uuid",
      "topic": "string",
      "brand_name": "string",
      "slide_count": 6,
      "status": "completed",
      "created_at": "ISO8601",
      "completed_at": "ISO8601"
    }
  ],
  "meta": { "total": 42 }
}
```

```
GET /v1/jobs/{job_id}
Description: Get full detail for a single job, including all slide metadata
Auth: None (local)

Response 200: Full job object with slides array (same shape as POST /v1/generate response)

Errors:
  404 — job not found
```

```
POST /v1/brands
Description: Create a new brand profile
Auth: None (local)
Content-Type: multipart/form-data (to support logo file upload)

Form Fields:
  name             — string, required, unique
  primary_color    — string, required (#RRGGBB)
  secondary_color  — string, required (#RRGGBB)
  background_color — string, required (#RRGGBB)
  text_color       — string, required (#RRGGBB)
  font_heading     — string, required (must match a filename in /fonts dir)
  font_body        — string, required (must match a filename in /fonts dir)
  handle           — string, optional
  tone_keywords    — string, required (comma-separated)
  tagline          — string, optional
  logo             — file, optional (PNG or SVG, max 2MB)

Response 201:
{
  "success": true,
  "data": { "brand_profile_id": "uuid", "name": "string" }
}

Errors:
  400 — Validation error, duplicate name, unsupported logo format
  413 — Logo file too large
```

```
GET /v1/brands
Description: List all saved brand profiles
Response 200: Array of brand_profile objects (id, name, primary_color, handle, created_at)
```

```
PUT /v1/brands/{brand_id}
Description: Update a brand profile (same field set as POST /v1/brands)
Response 200: Updated brand_profile object
Errors: 404 — brand not found, 400 — validation error
```

```
DELETE /v1/brands/{brand_id}
Description: Delete a brand profile. Jobs that used this profile retain their output.
Response 204: No content
Errors: 404 — brand not found, 409 — cannot delete brand with active/running jobs
```

```
GET /v1/slides/{job_id}/{slide_index}/image
Description: Serve a rendered slide PNG directly for Streamlit preview
Auth: None (local)
Response: image/png binary stream
Errors: 404 — job or slide index not found
```

---

### 3.3 Internal Module Contracts (Python Dataclasses)

The internal pipeline communicates via typed Python dataclasses, not HTTP. These are the key contracts:

```python
# PipelineContext — passed through all pipeline stages
@dataclass
class PipelineContext:
    job_id: str
    topic: str
    brand: BrandProfile
    slide_count: int
    gemini_model: str
    use_imagen: bool
    carousel_script: Optional[CarouselScript] = None   # filled by CIM
    generated_assets: Dict[int, str] = field(default_factory=dict)  # filled by AGM
    rendered_slides: List[str] = field(default_factory=list)  # filled by Composition Engine
    fallback_indices: List[int] = field(default_factory=list)

# CarouselScript — output of Content Intelligence Module
@dataclass
class CarouselScript:
    title: str
    target_audience: str
    slides: List[SlideScript]

@dataclass
class SlideScript:
    index: int
    slide_type: str  # hook | content | stat | quote | cta
    headline: str
    body_text: Optional[str]
    visual_prompt: Optional[str]  # None if no AI image needed for this slide
    visual_style_note: Optional[str]  # e.g. "dark, moody, construction site"
```

---

### 3.4 UX-to-API Mapping

**User flow: Generate a carousel from scratch**

1. User opens Streamlit at `localhost:8501` → UI calls `GET /v1/brands` to populate the brand dropdown.
2. User types a topic, selects brand, sets slide count → clicks "Generate".
3. UI calls `POST /v1/generate` → stores returned `job_id`.
4. UI enters a polling loop: calls `GET /v1/generate/{job_id}/status` every 2 seconds.
5. UI renders a progress bar from `progress.current_slide / progress.total_slides`.
6. When `status == "completed"`, UI calls `GET /v1/jobs/{job_id}` to get slide paths.
7. UI renders each slide using `GET /v1/slides/{job_id}/{index}/image` inline.
8. User clicks "Download All" → UI zips the output directory and offers a browser download.

---

### 3.5 Error Handling Standards

| HTTP Code | Trigger | Response Shape |
|-----------|---------|----------------|
| 400 | Missing required field, type mismatch, value out of range | `{success: false, error: {code: "VALIDATION_ERROR", fields: {...}}}` |
| 404 | Resource (job, brand, slide) not found | `{success: false, error: {code: "NOT_FOUND", message: "..."}}` |
| 409 | Conflict (e.g., duplicate brand name, delete active brand) | `{success: false, error: {code: "CONFLICT", message: "..."}}` |
| 413 | Uploaded file exceeds size limit | `{success: false, error: {code: "FILE_TOO_LARGE"}}` |
| 500 | Unhandled pipeline exception (Vertex AI SDK error, Pillow error) | `{success: false, error: {code: "PIPELINE_ERROR", message: "...", stage: "asset_generation"}}` |
| 503 | Max concurrent pipeline jobs reached | `{success: false, error: {code: "CAPACITY_EXCEEDED", retry_after: 30}}` |

---

⚠️ **Open Questions / Assumptions — Phase 3**
- The status polling approach (client polls every 2s) is appropriate for local use. For a networked deployment with multiple users, upgrade to Server-Sent Events (SSE) or WebSocket for real-time progress push.
- Streaming the generated slides to the UI as each one finishes (rather than waiting for all slides) is a UX improvement for Phase 2.

---

## Phase 4: Technical Specifications {#phase-4}

### 4.1 Infrastructure Requirements

| Component | Technology | Spec (MVP Local) | Spec (V2 Cloud VM) | Notes |
|-----------|------------|-----------------|-------------------|-------|
| App Server | Python 3.11 + FastAPI + Uvicorn | Developer laptop (any modern CPU, 8GB RAM minimum) | e2-standard-2 (2 vCPU, 8GB RAM) on GCP | Imagen calls are I/O-bound, not CPU-bound |
| UI Server | Streamlit | Same process/machine as app server | Same VM | Runs on port 8501 |
| Database | SQLite 3 | Local file | Local file on VM persistent disk | Upgrade to PostgreSQL only if multi-user |
| Object Storage | Local filesystem | Local SSD/HDD | 50GB persistent disk (pd-ssd) | Output PNGs accumulate; budget 500KB per slide |
| Reverse Proxy (V2) | Nginx | N/A | 1 vCPU included in VM cost | SSL termination, port forwarding to Uvicorn |
| AI Inference | Google Vertex AI (external) | ADC from laptop | ADC from VM service account | No GPU required locally; inference is remote |

---

### 4.2 Software Stack

```
Runtime:          Python 3.11+
API Framework:    FastAPI 0.111+
ASGI Server:      Uvicorn 0.29+
UI Framework:     Streamlit 1.35+
AI SDK:           google-cloud-aiplatform 1.55+  (Gemini + Imagen via Vertex)
Data Validation:  Pydantic v2
Image Rendering:  Pillow 10.3+
Vector Logos:     CairoSVG 2.7+ (optional, for SVG logo support)
ORM/DB:           SQLAlchemy 2.0 (Core, not ORM) + aiosqlite
Migrations:       Alembic 1.13+
HTTP Client:      httpx (for internal async calls if needed)
Config:           python-dotenv
Testing:          pytest 8+, pytest-asyncio, Pillow comparison utils
Linting:          ruff (replaces flake8 + isort + black)
Type checking:    mypy
Package manager:  uv (faster than pip, lockfile support)
Containerisation: Docker + docker-compose (for V2 deployment)
```

---

### 4.3 Environment Configuration

```
# Google Cloud / Vertex AI
GOOGLE_CLOUD_PROJECT        — GCP project ID for Vertex AI billing
GOOGLE_CLOUD_REGION         — Vertex AI region (e.g., us-central1, europe-west4)
GOOGLE_APPLICATION_CREDENTIALS — Path to service account JSON (V2 VM only; ADC handles local)

# Application paths
CAROUSELAI_DATA_DIR         — Root directory for all app data (brands, jobs, output)
CAROUSELAI_FONTS_DIR        — Directory containing downloaded TTF font files
CAROUSELAI_OUTPUT_DIR       — Root directory for generated carousel output folders
CAROUSELAI_DB_PATH          — Absolute path to the SQLite database file

# Pipeline defaults
DEFAULT_GEMINI_MODEL         — Default model: gemini-1.5-flash or gemini-1.5-pro
DEFAULT_SLIDE_COUNT          — Default number of slides if not specified (recommend: 6)
MAX_CONCURRENT_JOBS          — Max simultaneous pipeline runs (recommend: 3 for local, 5 for VM)
IMAGEN_TIMEOUT_SECONDS       — Per-image generation timeout before fallback (recommend: 30)

# API (V2 cloud deployment only)
API_KEY                      — Static API key for endpoint protection
ALLOWED_ORIGINS              — CORS allowed origins for Streamlit UI domain

# Logging
LOG_LEVEL                    — DEBUG | INFO | WARNING | ERROR
LOG_FORMAT                   — json | text (use json for VM/cloud deployments)
```

---

### 4.4 Network & Connectivity

**Local (MVP):**
- FastAPI on `127.0.0.1:8000`
- Streamlit on `127.0.0.1:8501`
- All outbound HTTPS to `*.googleapis.com` for Vertex AI calls
- No inbound ports exposed beyond loopback

**V2 (Cloud VM on GCP):**
- VM in a VPC with a single subnet; no public IP on the VM itself
- Cloud Load Balancer (or Nginx on VM) handles HTTPS termination on port 443
- Firewall rule: allow inbound TCP 443 from `0.0.0.0/0`; deny all other inbound
- Firewall rule: allow outbound TCP 443 to `*.googleapis.com` (Vertex AI)
- Internal: FastAPI on `127.0.0.1:8000`, Streamlit on `127.0.0.1:8501`; Nginx proxies both
- Service account attached to VM with the `Vertex AI User` IAM role (no JSON key file needed)
- DNS: single A record pointing to the VM's external IP or Load Balancer IP

---

### 4.5 Security Implementation

| Layer | Control | Implementation |
|-------|---------|----------------|
| Transport | TLS 1.2+ | Enforced at Nginx; HSTS header set (`max-age=31536000`) |
| Auth (V2) | Static API Key | `X-API-Key` header; validated in FastAPI middleware; key stored in env var, not code |
| AI credentials | ADC / Service Account | No credential files in the codebase; ADC resolves automatically from environment |
| Input validation | Pydantic v2 strict models | All API request bodies validated at the FastAPI layer before reaching pipeline |
| File upload | Type + size validation | Logo uploads validated for MIME type (PNG/SVG only) and max 2MB before write |
| Output path safety | Pathlib strict resolution | All filesystem writes use `pathlib.Path.resolve()` to prevent path traversal |
| Secrets | Environment variables | No secrets in code or config files committed to version control; `.env` in `.gitignore` |
| Prompt injection | Structured output + schema validation | Gemini is prompted to return JSON; response is validated against `CarouselScript` Pydantic schema — free-text injection cannot affect pipeline behaviour |
| Data at rest | No encryption (local) | For V2 VM, enable GCP disk encryption (enabled by default on GCE persistent disks) |
| Dependencies | Vulnerability scanning | `uv audit` or `pip-audit` in CI; Dependabot enabled on GitHub repo |

---

### 4.6 Deployment Pipeline

**Local (MVP):**
```
1. Clone repo
2. uv sync  (installs all deps from lockfile)
3. cp .env.example .env && fill in GOOGLE_CLOUD_PROJECT and paths
4. gcloud auth application-default login
5. alembic upgrade head  (creates SQLite schema)
6. python -m carouselai.seed  (creates default brand profile)
7. uvicorn carouselai.api.main:app --reload --port 8000  (API)
8. streamlit run carouselai/ui/app.py --server.port 8501  (UI)
```

**V2 (Cloud VM — Docker Compose):**
```
1. Push code to GitHub main branch
2. GitHub Actions CI:
   a. ruff check + mypy type check
   b. pytest (unit + integration with mocked Vertex AI)
   c. docker build → push to Google Artifact Registry
3. SSH to VM (or use Cloud Run Jobs for deploy step):
   a. docker-compose pull
   b. docker-compose up -d --no-deps app
   c. Run DB migration: docker-compose exec app alembic upgrade head
4. Nginx reload (if config changed)
5. Rollback: docker-compose up -d --no-deps --scale app=0 app_prev
```

---

⚠️ **Open Questions / Assumptions — Phase 4**
- Assumed `us-central1` as the default Vertex AI region. If you're primarily generating carousels for a Nigerian audience and latency matters, test `europe-west1` as it may have lower round-trip time from Lagos than `us-central1`.
- Assumed Docker is available for V2 deployment. If not, a plain `systemd` service unit for Uvicorn is a valid simpler alternative.
- CairoSVG has native library dependencies (libcairo) that require `apt-get install` on the VM. Mark this as a setup step in the Dockerfile.

---

## Phase 5: Non-Functional Requirements (NFR) Plan {#phase-5}

### 5.1 Performance Targets

| Metric | Target | Constraint | Measurement Method |
|--------|--------|-----------|-------------------|
| API endpoint response (non-generate) | p95 < 100ms | N/A | Uvicorn access log timing |
| Full carousel generation (6 slides, Imagen on) | < 90 seconds end-to-end | Imagen 3 latency is the bottleneck (~10–15s/image) | Job `created_at` → `completed_at` delta |
| Full carousel generation (6 slides, Imagen off) | < 15 seconds end-to-end | Gemini call + Pillow render | Same |
| Slide PNG render time (Pillow, per slide) | < 500ms per slide | CPU-bound | Per-slide timer in Composition Engine |
| UI page load (Streamlit) | < 2 seconds initial load | Network dependent | Browser DevTools |
| SQLite query (job history, 100 records) | < 10ms | N/A | SQLAlchemy query timing |

**Note on Imagen latency:** The 90-second target assumes 6 slides × 15s/image = 90s worst case. In practice, many slides (e.g., text-dominant stat slides) will not require Imagen calls, dropping total time significantly. A v2 optimisation is parallelising Imagen calls with `asyncio.gather()`.

---

### 5.2 Scalability Plan

**MVP:** Single-threaded pipeline per job. Sufficient for one user generating a few carousels per day.

**V2 (Parallel Imagen calls):** Upgrade the Asset Generation Module to use `asyncio.gather()` to fire all slide-level Imagen requests concurrently. This reduces a 6-image job from ~90s serial to ~15s parallel (limited by Vertex AI's per-project concurrent request quota).

**V3 (Multi-user):** Replace the in-process job semaphore with a Celery task queue (Redis broker). FastAPI enqueues jobs; Celery workers process them. Add a worker replica for each additional concurrent user. SQLite → PostgreSQL at this point.

**Scale ceiling of current design:** The SQLite + single-VM architecture comfortably handles 1 user generating 20–50 carousels per day. Beyond that, or with multiple simultaneous users, the V3 architecture applies.

---

### 5.3 Reliability & Availability

| Requirement | Target | Strategy |
|-------------|--------|----------|
| Local uptime | Best effort (dev tool) | N/A — restart is trivial |
| V2 VM uptime | 99.5% | GCE VM auto-restart on failure; Nginx + Uvicorn as systemd services that restart on crash |
| Pipeline failure recovery | Partial output preserved | Fallback rendering on Imagen failure; job marked `failed` with error stage logged |
| Data durability (SQLite) | No data loss on VM restart | SQLite WAL mode enabled; GCE persistent disk survives VM restarts |
| Vertex AI quota exhaustion | Graceful degradation | `use_imagen=false` fallback mode available; surfaces clear error message to user |

---

### 5.4 Observability Stack

**Logging:**
- Structured JSON logs via Python `logging` + `python-json-logger`
- Log levels: `DEBUG` in development, `INFO` in production
- Every pipeline stage logs: stage name, job_id, slide_index, duration_ms, success/failure
- Vertex AI API calls log: model used, prompt token count, response token count, latency_ms
- Retention: local log file with `logrotate`, 30-day retention, 100MB max per file

**Metrics (lightweight, no external tool needed for MVP):**
- Each completed job writes timing metrics to the job manifest JSON
- A `GET /v1/metrics` endpoint returns aggregate stats: total jobs, avg generation time, failure rate, Imagen fallback rate

**Critical Alerts (V2 cloud deployment — via GCP Cloud Monitoring):**
1. VM CPU > 90% for 5 minutes → alert: possible runaway pipeline job
2. VM disk usage > 80% → alert: output directory accumulating too many PNGs
3. FastAPI process not responding (Nginx 502 rate > 10%) → alert: app crashed
4. Vertex AI quota error rate > 5% in 10 minutes → alert: approaching API quota
5. SQLite file size > 500MB → alert: consider pruning old job records

**Distributed tracing:** Not warranted for a monolith. A `job_id` is propagated through all log lines for a given run, which gives you full pipeline trace reconstruction from logs alone.

---

### 5.5 Disaster Recovery Plan

**MVP (local):** Back up the `CAROUSELAI_DATA_DIR` to Google Drive or an external disk weekly. The SQLite file and brand assets directory together are typically < 100MB.

**V2 (GCP VM):**
- GCP persistent disk snapshots scheduled daily (via GCP Snapshot Schedules)
- Snapshot retention: 7 daily, 4 weekly
- Recovery: create new VM from snapshot, re-attach disk, restart services — RTO < 30 minutes
- The Docker image is in Artifact Registry; code is in GitHub — the VM disk is the only stateful component

**Runbook locations:** A `docs/runbooks/` directory in the repo with one markdown file per failure scenario: Vertex AI quota exhausted, SQLite corruption, Nginx 502, disk full.

---

### 5.6 Maintainability & Tech Debt Plan

**Code quality gates (enforced in CI):**
- `ruff` linting and formatting — zero warnings gate
- `mypy --strict` type checking — no untyped functions in core pipeline modules
- Test coverage threshold: 70% minimum on pipeline modules (CIM, AGM, Composition Engine, Brand Engine)

**Documentation requirements:**
- Every public Python function has a docstring with parameter types and return description
- `docs/architecture-decisions/` directory — one ADR per major design decision (e.g., "ADR-001: SQLite over PostgreSQL for MVP", "ADR-002: Pillow over CairoSVG as primary renderer")
- OpenAPI spec auto-generated by FastAPI at `/docs` — keep it accurate

**Dependency update policy:** Monthly `uv lock --upgrade` run; security patches applied within 48 hours of CVE disclosure.

**Tech debt sprint:** After every 10 production carousels generated, review what's been hacked together. Scheduled quarterly refactor focus areas: prompt engineering improvements, new slide template types, Imagen prompt quality.

---

⚠️ **Open Questions / Assumptions — Phase 5**
- Imagen 3 latency figures (10–15s/image) are estimates based on observed Vertex AI performance as of mid-2025. Verify against your specific GCP project and region — quota tier and region significantly affect inference latency.
- GCP Cloud Monitoring is free up to the included tier for VM metrics. Verify current free tier limits before enabling alerts.

---

## 🗺️ Implementation Roadmap {#roadmap}

### Phase 1 — MVP Core (Weeks 1–2)
The goal is a working end-to-end pipeline you can actually use, even if the UI is minimal.

**Week 1:**
- Project scaffold: `uv init`, directory structure, Pydantic schemas, SQLite setup with Alembic
- Brand Engine: BrandProfile schema, font loading, brand profile JSON for one brand (yours)
- Composition Engine: 3 template classes (Hook, Content, CTA) using Pillow with hardcoded zones
- Manual test: render a slide from hardcoded copy to verify font rendering, colour application, text wrapping

**Week 2:**
- Content Intelligence Module: Gemini 1.5 Flash integration, carousel script prompt, JSON output parsing
- Asset Generation Module: Imagen 3 integration, per-slide call, fallback handling
- Pipeline Orchestrator: wire the four modules together through PipelineContext
- CLI entrypoint: `python -m carouselai generate --topic "..." --brand default`
- End-to-end test: generate a real 6-slide carousel on a topic you care about

**Deliverable:** Working CLI tool. No UI yet. But you have real, usable output.

---

### Phase 2 — UI & Polish (Weeks 3–4)
Make it actually pleasant to use.

**Week 3:**
- FastAPI layer: all endpoints from Phase 3 (generate, jobs, brands, image serving)
- Streamlit UI: generation form, progress polling, slide preview, download button
- Brand profile creation UI: form + logo upload
- Job history view

**Week 4:**
- Add 2 more slide template types (Stat, Quote)
- Prompt engineering iteration: test 10 different topics, refine the Gemini system prompt for Instagram virality patterns
- Error handling polish: surface Imagen fallback warnings in UI, clear error messages
- Font library: download and configure 3–4 Google Font pairs that work well for construction/business content

**Deliverable:** Full working app with UI. Shareable with one other person for feedback.

---

### Phase 3 — Quality & Advanced Features (Weeks 5–8)
Make it genuinely powerful.

- Async Imagen calls with `asyncio.gather()` — cut generation time by ~5×
- Multi-brand support: test with 3+ distinct brand profiles
- Template variety: add animated frame (export frames as GIF for Stories), wide format (1080×566 for feed preview), portrait format (1080×1350)
- Virality scoring: add a Gemini post-generation call that critiques the generated hook slide and suggests a stronger alternative
- Docker Compose packaging for clean one-command startup
- V2 cloud VM deployment with Nginx + HTTPS
- Test suite: 70%+ coverage on pipeline modules

**Deliverable:** Production-quality personal tool. Candidate for sharing as an open-source project or productising for other Nigerian brands.

---

*Document ends. Revision history tracked in version control alongside the codebase.*
