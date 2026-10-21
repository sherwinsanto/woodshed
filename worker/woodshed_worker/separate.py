"""Split a song into four stems (drums, bass, other, vocals) with Demucs.

Usage:
    python -m woodshed_worker.separate song.mp3 out/
"""

import argparse
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import torch
from demucs.api import Separator
from demucs.audio import save_audio

MODEL_NAME = "htdemucs"
OUTPUT_FORMATS = ("mp3", "wav")


@dataclass
class SeparationResult:
    stems: dict[str, Path]
    device: str
    audio_seconds: float
    processing_seconds: float
    encoding_seconds: float


def pick_device(requested: str = "auto") -> str:
    """Use the GPU when one is available, unless a device is requested explicitly."""
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but no NVIDIA GPU is available")
    return requested


def progress_fraction(info: dict, shifts: int) -> float:
    """Turn a Demucs progress callback into a 0-1 fraction of the whole job.

    Demucs works through the song in segments, once per shift and once per model
    in the bag, so overall progress has to account for all three.
    """
    passes = info["models"] * max(shifts, 1)
    current_pass = info["model_idx_in_bag"] * max(shifts, 1) + info["shift_idx"]
    within_pass = min(info["segment_offset"] / info["audio_length"], 1.0)
    return min((current_pass + within_pass) / passes, 1.0)


def separate(
    input_path: Path,
    output_dir: Path,
    device: str = "auto",
    output_format: str = "mp3",
    shifts: int = 1,
    on_progress: Callable[[float], None] | None = None,
) -> SeparationResult:
    if output_format not in OUTPUT_FORMATS:
        raise ValueError(f"output_format must be one of {OUTPUT_FORMATS}")
    device = pick_device(device)

    def callback(info: dict) -> None:
        if on_progress and info["state"] == "end":
            on_progress(progress_fraction(info, shifts))

    separator = Separator(model=MODEL_NAME, device=device, shifts=shifts, callback=callback)

    start = time.perf_counter()
    original, stems = separator.separate_audio_file(input_path)
    processing_seconds = time.perf_counter() - start

    start = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: output_dir / f"{name}.{output_format}" for name in stems}

    def save(name: str) -> None:
        # "clamp" keeps every stem at its true level so the stems still add up to
        # the original mix; the default "rescale" turns each stem down separately.
        save_audio(stems[name], paths[name], samplerate=separator.samplerate, clip="clamp")

    # The MP3 encoder releases the GIL, so encoding the stems on parallel threads
    # is several times faster than one after another.
    with ThreadPoolExecutor(max_workers=len(stems)) as pool:
        list(pool.map(save, stems))
    encoding_seconds = time.perf_counter() - start

    return SeparationResult(
        stems=paths,
        device=device,
        audio_seconds=original.shape[-1] / separator.samplerate,
        processing_seconds=processing_seconds,
        encoding_seconds=encoding_seconds,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Split a song into stems with Demucs.")
    parser.add_argument("input", type=Path, help="audio file (mp3, wav, flac, ogg, m4a)")
    parser.add_argument("output_dir", type=Path, help="folder to write the stems to")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    parser.add_argument("--format", default="mp3", choices=OUTPUT_FORMATS)
    args = parser.parse_args(argv)

    def show_progress(fraction: float) -> None:
        print(f"\r  separating... {fraction:4.0%}", end="", flush=True)

    result = separate(
        args.input, args.output_dir, args.device, args.format, on_progress=show_progress
    )
    print()
    speed = result.audio_seconds / result.processing_seconds
    print(
        f"Split {result.audio_seconds:.0f}s of audio in {result.processing_seconds:.1f}s "
        f"on {result.device} ({speed:.1f}x real time), "
        f"then saved stems as {args.format} in {result.encoding_seconds:.1f}s"
    )
    for name, path in result.stems.items():
        print(f"  {name:<7} {path}")


if __name__ == "__main__":
    main()
