# Woodshed

[![CI](https://github.com/sherwinsanto/woodshed/actions/workflows/ci.yml/badge.svg)](https://github.com/sherwinsanto/woodshed/actions/workflows/ci.yml)

**Split any song into stems and practise along with the band.**

Upload a song and Woodshed uses AI to separate it into vocals, drums, bass and
other instruments. Then practise in a mixer built for musicians: mute your own
part, slow the song down without changing its pitch, loop the tricky bit, and
save practice sections to come back to.

> 🚧 Work in progress. See the [roadmap](#roadmap) and the GitHub Issues.

## Architecture

```
React app ──upload──▶ FastAPI ──▶ object storage (S3-compatible)
    ▲                    │
    │ progress           ├──▶ PostgreSQL (jobs, songs, sections)
    │                    │
    └──── polls ─────────┘──▶ worker: Demucs on a serverless GPU
                                 └──▶ writes 4 stems to storage
```

| Part | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, Web Audio API |
| API | Python, FastAPI |
| Database | PostgreSQL |
| AI worker | Demucs (PyTorch), Modal serverless GPUs |
| Storage | S3-compatible object storage (Cloudflare R2) |
| Tooling | Docker Compose, GitHub Actions, pytest, Vitest, Ruff, oxlint |

## Running locally

Requirements: Docker Desktop, Python 3.12, Node.js 24.

```bash
# Database + API (http://localhost:8000/health)
docker compose up --build

# Frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

Running the API outside Docker:

```bash
cd api
python -m venv .venv
.venv/Scripts/activate        # Windows (macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest
```

## Roadmap

- [ ] **Week 1: pipeline.** Upload → background job → Demucs → 4 stems in storage
- [ ] **Week 2: mixer.** Synced multi-track playback, waveforms, mute/solo/volume
- [ ] **Week 3: practice tools + launch.** Tempo change without pitch shift, A–B loops, downloads, deploy
- [ ] **Week 4: accounts + polish.** Saved songs and sections, speed trainer, tests, limits

## Audio and copyright

Woodshed only processes audio that users upload themselves. It never downloads
audio from YouTube or other streaming services, and uploaded files and stems are
deleted automatically after 24 hours.

## License

[MIT](LICENSE)
