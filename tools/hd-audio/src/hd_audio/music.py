from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal

from .device import DeviceInfo
from .extend import extend_audiosr
from .paths import TARGET_RATE
from .wavio import load_wav, peak, save_wav

# Locked after music A/B (2026-10-11): sr_linked — same-seed L/R AudioSR, low GS.
MUSIC_MODES = ("resample", "sr_mid", "sr_linked")
CURRENT_MUSIC_MODE = "sr_linked"


@dataclass
class MusicResult:
	path: Path
	backend: str
	ms: float
	out_rate: int


def hq_resample(audio: np.ndarray, src_rate: int, dest_rate: int = TARGET_RATE) -> np.ndarray:
	"""Polyphase resample (channels, samples) → dest_rate."""
	arr = np.asarray(audio, dtype=np.float32)
	if arr.ndim == 1:
		arr = arr[np.newaxis, :]
	if src_rate == dest_rate:
		return arr
	# Reduce by gcd for resample_poly
	g = int(np.gcd(src_rate, dest_rate))
	up = dest_rate // g
	down = src_rate // g
	outs = [signal.resample_poly(arr[ch], up, down).astype(np.float32) for ch in range(arr.shape[0])]
	# Match lengths
	n = min(o.shape[-1] for o in outs)
	return np.stack([o[:n] for o in outs], axis=0)


def _to_mid_side(stereo: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
	"""stereo (2, n) → mid, side (each 1, n)."""
	assert stereo.shape[0] == 2
	mid = (0.5 * (stereo[0] + stereo[1]))[np.newaxis, :]
	side = (0.5 * (stereo[0] - stereo[1]))[np.newaxis, :]
	return mid.astype(np.float32), side.astype(np.float32)


def _from_mid_side(mid: np.ndarray, side: np.ndarray) -> np.ndarray:
	m = mid[0] if mid.ndim == 2 else mid
	s = side[0] if side.ndim == 2 else side
	n = min(m.shape[-1], s.shape[-1])
	left = m[:n] + s[:n]
	right = m[:n] - s[:n]
	return np.stack([left, right], axis=0).astype(np.float32)


def peak_match_linear(audio: np.ndarray, reference: np.ndarray) -> np.ndarray:
	"""Peak match without tanh (keeps music dynamics)."""
	out = np.asarray(audio, dtype=np.float32)
	ref_p = peak(reference)
	cur_p = peak(out)
	if cur_p > 1e-8 and ref_p > 0:
		out = out * (ref_p / cur_p)
	p = peak(out)
	if p > 0.99:
		out = out * (0.99 / p)
	return out


def remaster_music(
	src: Path,
	dest: Path,
	*,
	mode: str,
	device: DeviceInfo,
	work_dir: Path,
	ddim_steps: int = 60,
	guidance_scale: float = 2.0,
	seed: int = 42,
) -> MusicResult:
	"""Music-specific remaster. Modes: resample | sr_mid | sr_linked."""
	if mode not in MUSIC_MODES:
		raise SystemExit(f"Unknown music mode {mode!r}; choose from {MUSIC_MODES}")

	t0 = time.perf_counter()
	audio, rate = load_wav(src)
	if audio.shape[0] == 1:
		audio = np.concatenate([audio, audio], axis=0)

	if mode == "resample":
		out = hq_resample(audio, rate, TARGET_RATE)
		out = peak_match_linear(out, audio)
		nbytes = save_wav(dest, out, TARGET_RATE)
		return MusicResult(
			path=dest,
			backend=f"music:resample→{TARGET_RATE} ({nbytes}B)",
			ms=(time.perf_counter() - t0) * 1000,
			out_rate=TARGET_RATE,
		)

	if mode == "sr_mid":
		# AudioSR on mid only (less stereo smear); HQ-resample the side.
		mid, side = _to_mid_side(audio)
		mid_path = work_dir / "mid.wav"
		save_wav(mid_path, mid, rate)
		mid_out_path = work_dir / "mid_sr.wav"
		ext = extend_audiosr(
			mid_path,
			mid_out_path,
			model_name="basic",
			device=device,
			ddim_steps=ddim_steps,
			guidance_scale=guidance_scale,
			seed=seed,
			category="music",
		)
		mid_sr, _ = load_wav(ext.path)
		side_48 = hq_resample(side, rate, TARGET_RATE)
		# Align lengths
		n = min(mid_sr.shape[-1], side_48.shape[-1])
		out = _from_mid_side(mid_sr[:, :n], side_48[:, :n])
		out = peak_match_linear(out, audio)
		save_wav(dest, out, TARGET_RATE)
		return MusicResult(
			path=dest,
			backend=f"music:sr_mid@{ext.backend}",
			ms=(time.perf_counter() - t0) * 1000,
			out_rate=TARGET_RATE,
		)

	# sr_linked: same seed both channels, low guidance, no independent hallucination
	assert mode == "sr_linked"
	channel_outs = []
	for ch in range(audio.shape[0]):
		ch_path = work_dir / f"ch{ch}.wav"
		save_wav(ch_path, audio[ch : ch + 1], rate)
		ch_out = work_dir / f"ch{ch}_sr.wav"
		ext = extend_audiosr(
			ch_path,
			ch_out,
			model_name="basic",
			device=device,
			ddim_steps=ddim_steps,
			guidance_scale=guidance_scale,
			seed=seed,  # same seed → correlated stereo
			category="music",
		)
		ch_audio, _ = load_wav(ext.path)
		channel_outs.append(ch_audio[0])
	n = min(c.shape[-1] for c in channel_outs)
	out = np.stack([c[:n] for c in channel_outs], axis=0)
	out = peak_match_linear(out, audio)
	save_wav(dest, out, TARGET_RATE)
	return MusicResult(
		path=dest,
		backend=f"music:sr_linked@audiosr:basic gs={guidance_scale}",
		ms=(time.perf_counter() - t0) * 1000,
		out_rate=TARGET_RATE,
	)
