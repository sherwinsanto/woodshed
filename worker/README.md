# Worker

Splits a song into four stems (vocals, drums, bass, other) with
[Demucs](https://github.com/adefossez/demucs) (`htdemucs`, Hybrid Transformer Demucs).

Locally it runs on your own NVIDIA GPU (CUDA) or the CPU; in production it will run
on Modal's serverless GPUs.

## Setup

PyTorch is installed first, from PyTorch's own package index, because the default
`pip install torch` on Windows is CPU-only.

```bash
cd worker
python -m venv .venv
.venv/Scripts/activate              # macOS/Linux: source .venv/bin/activate

# NVIDIA GPU (CUDA 13):
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130
# ...or CPU only:
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

pip install -e ".[dev]"
```

## Usage

```bash
python -m woodshed_worker.separate song.mp3 out/            # MP3 stems, GPU if available
python -m woodshed_worker.separate song.mp3 out/ --format wav --device cpu
```

The model weights (~80MB) download automatically on first run.

## Performance

A 4-minute song on a laptop (RTX 5070 Laptop GPU):

| | Separation (AI) | Saving 4 MP3 stems | End to end |
|---|---|---|---|
| GPU (CUDA) | 6.8s (35x real time) | 6.9s | 17.4s |
| CPU | 93.8s (2.6x real time) | | |

Profiling showed MP3 encoding took 19.3s, three times longer than the AI itself.
The encoder releases Python's GIL, so the four stems are now encoded on parallel
threads, which cut encoding to 6.9s and the end-to-end time by 38%.

## Tests

```bash
pytest            # fast unit tests
pytest -m slow    # also runs the real model on a short clip
```
