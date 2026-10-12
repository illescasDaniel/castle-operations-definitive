from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import noisereduce as nr
from scipy import signal

from .device import DeviceInfo
from .wavio import load_wav, save_wav


@dataclass
class EnhanceResult:
	path: Path
	backend: str
	ms: float


_resemble_ready: bool | None = None


def _try_import_resemble() -> bool:
	global _resemble_ready
	if _resemble_ready is not None:
		return _resemble_ready
	try:
		import resemble_enhance  # noqa: F401

		_resemble_ready = True
	except Exception:
		_resemble_ready = False
	return _resemble_ready


def spectral_denoise(
	audio: np.ndarray, rate: int, *, prop_decrease: float
) -> np.ndarray:
	"""Light spectral gate; preserves transients better at low prop_decrease."""
	channels = []
	for ch in range(audio.shape[0]):
		channels.append(
			nr.reduce_noise(
				y=audio[ch],
				sr=rate,
				prop_decrease=prop_decrease,
				stationary=True,
			).astype(np.float32)
		)
	return np.stack(channels, axis=0)


def gentle_restore(audio: np.ndarray, rate: int) -> np.ndarray:
	"""Mild high-shelf + soft harmonic excitement for SFX/music clarity."""
	# 3 dB shelf around 4 kHz (relative to Nyquist of source, typically 11 kHz).
	nyq = rate / 2.0
	if nyq < 6000:
		return audio
	b, a = signal.butter(2, min(4000.0 / nyq, 0.95), btype="high")
	high = signal.lfilter(b, a, audio, axis=-1).astype(np.float32)
	# Soft tanh harmonics on the highs only.
	excited = np.tanh(high * 1.35).astype(np.float32) * 0.12
	out = audio + excited
	peak = float(np.max(np.abs(out))) or 1.0
	if peak > 0.99:
		out = out * (0.99 / peak)
	return out.astype(np.float32)


def enhance_speech_resemble(
	src: Path, dest: Path, device: DeviceInfo
) -> EnhanceResult:
	import time

	from resemble_enhance.enhancer.inference import denoise, enhance

	t0 = time.perf_counter()
	audio, rate = load_wav(src)
	# resemble expects torch tensors; process mono mix then restore channels.
	import torch

	dev = device.torch_device
	# Work channel-wise; enhancer is speech-oriented.
	outs = []
	for ch in range(audio.shape[0]):
		dwav = torch.from_numpy(audio[ch]).float().to(dev)
		wav_d, new_sr = denoise(dwav, rate, device=dev)
		wav_e, new_sr = enhance(
			wav_d, new_sr, device=dev, nfe=64, solver="midpoint", lambd=0.9, tau=0.5
		)
		outs.append(wav_e.detach().cpu().numpy().astype(np.float32))
		rate = int(new_sr)
	stacked = np.stack(outs, axis=0)
	save_wav(dest, stacked, rate)
	return EnhanceResult(path=dest, backend="resemble_enhance", ms=(time.perf_counter() - t0) * 1000)


def enhance_light(
	src: Path, dest: Path, *, category: str, mode: str = "denoise"
) -> EnhanceResult:
	import time

	t0 = time.perf_counter()
	audio, rate = load_wav(src)
	if category == "music":
		prop = 0.15
	elif category == "speech":
		prop = 0.55 if mode == "enhance" else 0.4
	else:
		prop = 0.4 if mode == "enhance" else 0.35
	denoised = spectral_denoise(audio, rate, prop_decrease=prop)
	# Speech stays denoise-only here (AudioSR speech does the bandwidth restore).
	# SFX/music get a gentle high-shelf / harmonic restore when enhancing.
	if category == "speech":
		restored = denoised
		backend = f"noisereduce({category},{mode})"
	elif mode == "enhance":
		restored = gentle_restore(denoised, rate)
		backend = f"noisereduce+restore({category})"
	else:
		restored = denoised
		backend = f"noisereduce({category})"
	save_wav(dest, restored, rate)
	return EnhanceResult(path=dest, backend=backend, ms=(time.perf_counter() - t0) * 1000)


def enhance_file(
	src: Path,
	dest: Path,
	*,
	category: str,
	device: DeviceInfo,
	mode: str,
) -> EnhanceResult:
	"""mode: none | denoise | enhance (full speech enhance when available)."""
	if mode == "none":
		import shutil
		import time

		t0 = time.perf_counter()
		dest.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(src, dest)
		return EnhanceResult(path=dest, backend="copy", ms=(time.perf_counter() - t0) * 1000)

	if mode == "denoise":
		return enhance_light(src, dest, category=category, mode="denoise")

	# mode == enhance
	if category == "speech" and _try_import_resemble():
		try:
			return enhance_speech_resemble(src, dest, device)
		except Exception as exc:
			from rich.console import Console

			Console(stderr=True).print(
				f"[yellow]Resemble Enhance failed ({exc}); "
				f"using spectral enhance fallback.[/yellow]"
			)
	return enhance_light(src, dest, category=category, mode="enhance")
