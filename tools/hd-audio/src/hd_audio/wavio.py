from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def load_wav(path: Path) -> tuple[np.ndarray, int]:
	"""Load audio as float32 array shaped (channels, samples), sample rate."""
	data, rate = sf.read(str(path), always_2d=True, dtype="float32")
	# soundfile returns (samples, channels)
	return data.T, int(rate)


def save_wav(path: Path, audio: np.ndarray, rate: int) -> int:
	"""Write 16-bit PCM WAV. audio is (channels, samples) or (samples,)."""
	path.parent.mkdir(parents=True, exist_ok=True)
	arr = np.asarray(audio, dtype=np.float32)
	if arr.ndim == 1:
		arr = arr[np.newaxis, :]
	# clip then PCM_16
	arr = np.clip(arr, -1.0, 1.0)
	sf.write(str(path), arr.T, rate, subtype="PCM_16")
	return path.stat().st_size


def truncate_seconds(audio: np.ndarray, rate: int, seconds: float) -> np.ndarray:
	n = int(rate * seconds)
	if audio.shape[-1] <= n:
		return audio
	return audio[..., :n]


def peak(audio: np.ndarray) -> float:
	return float(np.max(np.abs(audio))) if audio.size else 0.0


def rms(audio: np.ndarray) -> float:
	return float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
