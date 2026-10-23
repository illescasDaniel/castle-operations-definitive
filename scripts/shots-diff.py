#!/usr/bin/env python3
"""Compare two scripts/shots.sh or shot-at.sh runs: per shot, the share of differing pixels and the largest
per-channel difference (0-255). Writes an amplified diff image next to the second set."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "benchmarks" / "shots"


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: scripts/shots-diff.py LABEL_A LABEL_B", file=sys.stderr)
        return 2
    a_dir, b_dir = ROOT / sys.argv[1], ROOT / sys.argv[2]
    # shot*.tga = scripts/shots.sh (bench demo), spot*.tga = scripts/shot-at.sh (fixed camera spots)
    shots = sorted(p.name for pat in ("shot*.tga", "spot*.tga") for p in a_dir.glob(pat))
    if not shots:
        print(f"no shots in {a_dir}", file=sys.stderr)
        return 1
    for name in shots:
        b_path = b_dir / name
        if not b_path.exists():
            print(f"{name}: missing in {b_dir.name}")
            continue
        a = np.asarray(Image.open(a_dir / name).convert("RGB"), dtype=np.int16)
        b = np.asarray(Image.open(b_path).convert("RGB"), dtype=np.int16)
        if a.shape != b.shape:
            print(f"{name}: size differs {a.shape} vs {b.shape}")
            continue
        d = np.abs(a - b)
        px = d.max(axis=2)
        print(f"{name}: differing px {100.0 * np.count_nonzero(px) / px.size:6.3f}%  "
              f">2: {100.0 * np.count_nonzero(px > 2) / px.size:6.3f}%  "
              f"max {int(px.max()):3d}  mean {float(d.mean()):.4f}")
        Image.fromarray(np.clip(px * 16, 0, 255).astype(np.uint8)).save(b_dir / f"diff-{sys.argv[1]}-{name[:-4]}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
