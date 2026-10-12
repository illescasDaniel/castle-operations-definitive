from __future__ import annotations

import numpy as np

from .wavio import peak, rms


def match_loudness(
	audio: np.ndarray,
	reference: np.ndarray,
	*,
	mode: str = "peak",
) -> np.ndarray:
	"""Scale remaster toward original peak/RMS, then soft-limit."""
	out = np.asarray(audio, dtype=np.float32)
	if mode == "rms":
		ref = rms(reference)
		cur = rms(out)
	else:
		ref = peak(reference)
		cur = peak(out)
	if cur > 1e-8 and ref > 0:
		out = out * (ref / cur)
	# Soft limiter
	out = np.tanh(out * 1.05).astype(np.float32)
	# Final peak guard
	p = peak(out)
	if p > 0.99:
		out = out * (0.99 / p)
	return out
