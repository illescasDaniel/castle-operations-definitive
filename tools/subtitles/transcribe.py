"""Transcribe all RTCW voice lines into text/subtitles.txt (resumable).

uv run python transcribe.py [pak-dir] [out-dir]   default out-dir: build/
Output: build/cache.json (path -> result), build/review.txt, build/text/subtitles.txt
Pack with pack.py. Generated files are derived from game assets and stay private.
"""
import ctypes, glob, json, site, subprocess, sys, zipfile
from pathlib import Path

for sp in site.getsitepackages():  # CUDA libs shipped as wheels
	for lib in sorted(glob.glob(f"{sp}/nvidia/*/lib/lib*.so*")):
		try: ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
		except OSError: pass

import numpy as np
from faster_whisper import WhisperModel

VOICE = ("sound/scenaric/", "sound/player/infantryss/", "sound/player/heinrich/", "sound/player/eliteguard/",
	"sound/player/loper/", "sound/player/warrior/", "sound/player/supersoldier/")
PROMPT = ("Return to Castle Wolfenstein. B.J. Blazkowicz, Kessler, Himmler, Heinrich Himmler, Deathshead, "
	"Helga von Bulow, Wolfenstein, Nazi, SS, Kreisau Circle, Chrysos, Engel, Tesla, Allied, Gestapo.")
HALLUCINATIONS = ("thank you for watching", "thanks for watching", "subtitles by", "amara.org")

pak_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "build"
(out / "text").mkdir(parents=True, exist_ok=True)
cache_f = out / "cache.json"
cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}

clips = {}  # lowercase path -> (pak, name); later paks override
for pak in sorted(pak_dir.glob("*.pk3")):
	if pak.name.startswith("mp_"): continue
	with zipfile.ZipFile(pak) as z:
		for n in z.namelist():
			if n.lower().endswith(".wav") and n.lower().startswith(VOICE):
				clips[n.lower()] = (pak, n)
print(len(clips), "voice clips,", len(cache), "cached", flush=True)

def load(data):
	raw = subprocess.run(["ffmpeg", "-v", "error", "-i", "-", "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
		input=data, capture_output=True, check=True).stdout
	return np.frombuffer(raw, np.float32)

model = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
for i, (key, (pak, name)) in enumerate(sorted(clips.items())):
	if key in cache: continue
	with zipfile.ZipFile(pak) as z: audio = load(z.read(name))
	def run(**kw):
		try:
			segs, info = model.transcribe(audio, vad_filter=True, **kw)
			return list(segs), info
		except RuntimeError:  # CUDA OOM on noisy clips: retry greedy, no fallback sampling
			segs, info = model.transcribe(audio, vad_filter=True, **{**kw, "beam_size": 1, "best_of": 1, "temperature": 0.0})
			return list(segs), info
	segs, info = run(initial_prompt=PROMPT, beam_size=5)
	segs = [s for s in list(segs) if s.no_speech_prob < 0.5 and s.avg_logprob > -1.0
		and not any(h in s.text.lower() for h in HALLUCINATIONS)]
	text = " ".join(s.text.strip() for s in segs).strip()
	r = dict(dur=round(len(audio) / 16000, 2), lang=info.language, prob=round(info.language_probability, 2), text="", orig="")
	if text and info.language_probability >= 0.5:
		r["orig"] = text
		r["text"] = text
		if info.language != "en":
			segs, _ = run(task="translate", beam_size=5)
			r["text"] = " ".join(s.text.strip() for s in segs).strip()
	cache[key] = r
	print(i, key, r["lang"], r["text"][:80], flush=True)
	if i % 25 == 0: cache_f.write_text(json.dumps(cache, indent=0, ensure_ascii=False))
cache_f.write_text(json.dumps(cache, indent=0, ensure_ascii=False))

# Stage 2: VAD plus the thresholds drop short, distorted or radio-filtered barks. Retry the empty clips (not
# pain/death sounds) without VAD and keep only confident, non-junk text; these are listed as RECOVERED for review.
JUNK = {"thank you", "thanks", "you", "bye", "okay", "ok", "so", "oh", "ah", "uh", "huh", "hmm", "mm", "the", "yeah"}
for key, r in sorted(cache.items()):
	if r["text"] or r.get("retried") or not (0.3 < r["dur"] < 8) or "/pain/" in key or "/death/" in key:
		continue
	pak, name = clips[key]
	with zipfile.ZipFile(pak) as z: audio = load(z.read(name))
	r["retried"] = True
	try:
		segs, info = model.transcribe(audio, beam_size=5, vad_filter=False, no_speech_threshold=0.8, log_prob_threshold=-1.5)
		segs = list(segs)
	except RuntimeError:
		continue
	text = " ".join(s.text.strip() for s in segs).strip()
	words = [w.strip(".,!?-'\"").lower() for w in text.split()]
	good = (text and segs and all(s.no_speech_prob < 0.4 and s.avg_logprob > -0.7 for s in segs) and info.language_probability >= 0.7
		and not any(h in text.lower() for h in HALLUCINATIONS) and " ".join(words) not in JUNK and len(text) > 4)
	if good:
		r.update(lang=info.language, prob=round(info.language_probability, 2), orig=text, text=text, recovered=True)
		if info.language != "en":
			try:
				segs, _ = model.transcribe(audio, task="translate", beam_size=5, vad_filter=False)
				r["text"] = " ".join(s.text.strip() for s in segs).strip()
			except RuntimeError: pass
		print("recovered", key, r["text"], flush=True)
cache_f.write_text(json.dumps(cache, indent=0, ensure_ascii=False))

from export import export
export(cache, out)
