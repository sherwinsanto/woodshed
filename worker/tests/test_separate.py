import math
from pathlib import Path

import pytest
import torch

from woodshed_worker.separate import pick_device, progress_fraction, separate


def progress_info(model=0, models=1, shift=0, offset=0, length=100) -> dict:
    return {
        "model_idx_in_bag": model,
        "models": models,
        "shift_idx": shift,
        "segment_offset": offset,
        "audio_length": length,
        "state": "end",
    }


def test_progress_single_model_single_shift() -> None:
    assert progress_fraction(progress_info(offset=0), shifts=1) == 0
    assert progress_fraction(progress_info(offset=50), shifts=1) == 0.5


def test_progress_accounts_for_shifts() -> None:
    # Halfway through the second of two shifts is 75% of the job.
    assert progress_fraction(progress_info(shift=1, offset=50), shifts=2) == 0.75


def test_progress_accounts_for_bag_of_models() -> None:
    # Start of the third of four models is 50% of the job.
    assert progress_fraction(progress_info(model=2, models=4), shifts=1) == 0.5


def test_progress_never_exceeds_one() -> None:
    # Demucs pads the audio, so the last segment offset can pass the track length.
    assert progress_fraction(progress_info(offset=120), shifts=1) == 1.0


def test_pick_device_cpu_is_always_allowed() -> None:
    assert pick_device("cpu") == "cpu"


def test_pick_device_auto_matches_hardware() -> None:
    expected = "cuda" if torch.cuda.is_available() else "cpu"
    assert pick_device("auto") == expected


def test_separate_rejects_unknown_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="output_format"):
        separate(tmp_path / "song.mp3", tmp_path, output_format="aac")


@pytest.mark.slow
def test_separate_writes_four_stems(tmp_path: Path) -> None:
    """Runs the real model on 3 seconds of tones. Run with: pytest -m slow"""
    from demucs.audio import save_audio

    sample_rate = 44100
    t = torch.arange(3 * sample_rate) / sample_rate
    tone = 0.3 * torch.sin(2 * math.pi * 220 * t)
    song = tmp_path / "tones.wav"
    save_audio(torch.stack([tone, tone]), song, samplerate=sample_rate)

    result = separate(song, tmp_path / "stems", output_format="wav")

    assert set(result.stems) == {"drums", "bass", "other", "vocals"}
    assert all(path.stat().st_size > 0 for path in result.stems.values())
    assert result.audio_seconds == pytest.approx(3, abs=0.1)
