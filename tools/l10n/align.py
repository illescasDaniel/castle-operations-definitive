#!/usr/bin/env python3
"""Fuzzy-align wiki cutscene quotes (build/wiki_quotes.txt) with English subtitles in
tools/subtitles/build/cache.json. Report only; nothing is applied.

  python3 tools/l10n/align.py [--min 0.6] [--all]

For each quote the best candidate is one of: a window of 1..6 consecutive clips (same folder,
sorted by path) matching the quote, or a single clip holding 2..4 consecutive quotes.
Candidates are restricted to the cutscene-character clips (cs*_dir/jac/dh, boss2/dh_*, ...)
unless --all is given.
"""
import argparse, difflib, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / "subtitles" / "build" / "cache.json"
WIKI = HERE / "build" / "wiki_quotes.txt"
CHAR = re.compile(r"cs\d+_(dir|jac|dh)|/dh_|_dh_|deathshead|xlabs/death_", re.I)


def norm_words(s):
    s = s.lower().replace("ü", "u").replace("Ü", "u")
    return re.findall(r"[a-z0-9']+", s.replace("-", " "))


def load_quotes():
    who, out = None, []
    for line in WIKI.read_text().splitlines():
        line = line.strip()
        if line.startswith("//") or not line:
            continue
        m = re.match(r"-\s*(.*?)\s+Quotes:", line)
        if m:
            who = m.group(1)
            continue
        q = line.strip("'\" ")
        out.append((who, len(out), q))
    return out


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def diff_words(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    parts = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "equal":
            parts.append(f"[{' '.join(a[i1:i2]) or '-'} -> {' '.join(b[j1:j2]) or '-'}]")
    return " ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=0.6)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    cache = json.loads(CACHE.read_text())
    keys = sorted(k for k, v in cache.items() if v["text"] and (a.all or CHAR.search(k)))
    quotes = load_quotes()
    qw = [norm_words(q[2]) for q in quotes]
    used, clip_used = {}, {}
    print(f"{len(quotes)} wiki quotes, {len(keys)} candidate clips\n")
    for qi, (who, _, q) in enumerate(quotes):
        best = (0, None, None, None)
        # window of clips vs one quote
        for i, k in enumerate(keys):
            d = k.rsplit("/", 1)[0]
            txt = []
            for j in range(i, min(i + 6, len(keys))):
                if keys[j].rsplit("/", 1)[0] != d:
                    break
                txt += norm_words(cache[keys[j]]["text"])
                r = ratio(qw[qi], txt)
                if r > best[0]:
                    best = (r, keys[i:j + 1], list(txt), (qi, qi))
        # several quotes vs one clip
        for k in keys:
            cw = norm_words(cache[k]["text"])
            for n in (2, 3, 4):
                if qi + n > len(quotes):
                    continue
                w = sum(qw[qi:qi + n], [])
                r = ratio(w, cw)
                if r > best[0] + 0.01:
                    best = (r, [k], cw, (qi, qi + n - 1))
                    best_w = w
        r, ks, txt, span = best
        tag = "OK " if r >= 0.9 else "?? " if r >= a.min else "-- "
        print(f"{tag}[{who}] #{qi} score={r:.2f}  {q}")
        if ks and r >= a.min:
            lo, hi = span
            w = sum(qw[lo:hi + 1], [])
            print(f"     clips: {', '.join(x.replace('sound/scenaric/', '') for x in ks)}"
                  + (f"  (quotes #{lo}-#{hi} in this clip)" if hi > lo else ""))
            print(f"     ours : {' | '.join(cache[x]['text'] for x in ks)}")
            print(f"     diff (ours -> wiki): {diff_words(txt, w)}")
            for x in ks:
                clip_used.setdefault(x, []).append(qi)
        else:
            print("     NO MATCH")
        print()
    print("== clips of characters with no wiki quote ==")
    for k in keys:
        if CHAR.search(k) and k not in clip_used and cache[k]["text"]:
            print(f"  {k.replace('sound/scenaric/', '')} | {cache[k]['text']}")


main()
