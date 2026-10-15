"""Pack build/text/subtitles.txt into ../../run/codmod/codmod_subtitles.pk3 (private, never commit).

  uv run python pack.py              pack subtitles.txt as it is (you may edit that file by hand)
  uv run python pack.py --from-cache regenerate subtitles.txt from build/cache.json first (after editing it)
"""
import json, sys

from export import BUILD, export, pack

if "--from-cache" in sys.argv:
	export(json.loads((BUILD / "cache.json").read_text()), BUILD)
pack()
