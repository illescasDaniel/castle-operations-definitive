#!/usr/bin/env python3
"""Check a memory-1 folder and say what to fix (standard library only, Python 3.9+).

usage: memory_check.py [--memory DIR]      DIR defaults to ./memory
Prints one line per problem, each with the action to take; exits 1 if there is any.
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

NOW_MAX, NEXT_MAX, DONE_MAX, INDEX_MAX, LATER_MAX, LATER_DAYS, LATER_LINE, SUGGEST_MAX = 50, 7, 5, 150, 40, 30, 240, 8


def meta(path):
    m = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="utf-8", errors="replace"), re.S)
    return dict(re.findall(r"(?m)^([\w-]+):[ \t]*(.*)$", m.group(1))) if m else None


def items(text, heading):
    m = re.search(rf"(?ms)^## {heading}[^\n]*\n(.*?)(?=^## |\Z)", text)
    return [l for l in (m.group(1).splitlines() if m else []) if re.match(r"\s*(?:[-*]|\d+[.)])\s", l)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--memory", default="memory")
    mem = Path(ap.parse_args().memory)
    if not mem.is_dir():
        sys.exit(f"no memory folder at {mem}")
    out = []
    now = mem / "NOW.md"
    if now.exists():
        text = now.read_text(encoding="utf-8", errors="replace")
        n = len(text.splitlines())
        if n > NOW_MAX:
            out.append(f"NOW.md has {n} lines (limit {NOW_MAX}): rewrite it from scratch for the current work; move "
                       f"open items that are not next to LATER.md and delete finished ones")
        if len(items(text, "Next")) > NEXT_MAX:
            out.append(f"NOW.md Next has {len(items(text, 'Next'))} items (limit {NEXT_MAX}): keep the next steps, move the rest to LATER.md")
        if len(items(text, "Done recently")) > DONE_MAX:
            out.append(f"NOW.md Done recently has {len(items(text, 'Done recently'))} items (limit {DONE_MAX}): delete the oldest; git log and the notes keep them")
        extra = [h for h in re.findall(r"(?m)^## (.+)$", text)
                 if not re.match(r"(Doing|Done recently|Next|Open questions)", h)]
        if extra:
            out.append(f"NOW.md has extra sections ({', '.join(extra)}): move their open items to LATER.md")
    else:
        out.append("NOW.md is missing: create it from the template")
    later = mem / "LATER.md"
    if later.exists():
        ltext = later.read_text(encoding="utf-8", errors="replace")
        rows = [l for l in ltext.splitlines() if re.match(r"\s*[-*]\s", l)]
        n = len(ltext.splitlines())
        sug = re.split(r"(?mi)^## Suggestions\s*$", ltext, maxsplit=1)
        srows = [l for l in (sug[1].split("\n## ")[0] if len(sug) > 1 else "").splitlines() if re.match(r"\s*[-*]\s", l)]
        if n > LATER_MAX:
            out.append(f"LATER.md has {n} lines (limit {LATER_MAX}; {len(srows)} suggestions, {len(rows) - len(srows)} other): "
                       f"delete done and overtaken lines, merge lines that ask for the same action, then delete "
                       f"suggestions down to the 3 that matter most; ask the user about (User) lines you cannot settle")
        if len(srows) > SUGGEST_MAX:
            out.append(f"LATER.md has {len(srows)} suggestions (limit {SUGGEST_MAX}): delete the ones whose cost of "
                       f"skipping is lowest")
        stray = [l for l in rows if "(Mine)" in l and l not in srows]
        if stray:
            out.append(f"LATER.md has {len(stray)} (Mine) line(s) outside '## Suggestions': move the ones that matter "
                       f"into that section (last in the file) and delete the rest")
        long = [l for l in rows if len(l) > LATER_LINE]
        if long:
            out.append(f"LATER.md has {len(long)} line(s) over {LATER_LINE} characters: say what to do and link the note, "
                       f"move the detail into the note, and split lines that join separate actions "
                       f"(first: {long[0].strip()[:80]})")
        ref = re.search(r"Updated:\s*(\d{4}-\d{2}-\d{2})", now.read_text(encoding="utf-8", errors="replace")) if now.exists() else None
        today = datetime.date.fromisoformat(ref.group(1)) if ref else datetime.date.today()
        old = []
        for l in rows:
            d = re.search(r"\d{4}-\d{2}-\d{2}", l)
            if d and "(User)" in l and (today - datetime.date.fromisoformat(d.group(0))).days > LATER_DAYS:
                old.append(l)
        olds = [l for l in srows if (d := re.search(r"\d{4}-\d{2}-\d{2}", l))
                and (today - datetime.date.fromisoformat(d.group(0))).days > LATER_DAYS]
        if olds:
            out.append(f"LATER.md has {len(olds)} suggestion(s) older than {LATER_DAYS} days: raise each with the user "
                       f"once (or under Open questions in NOW.md if they are not there), then delete it unless accepted "
                       f"(first: {olds[0].strip()[:80]})")
        if old:
            out.append(f"LATER.md has {len(old)} (User) line(s) older than {LATER_DAYS} days: list them to the user and "
                       f"ask which to keep (first: {old[0].strip()[:80]})")
        if rows and not re.search(r"(?m)^## ", ltext) and len(rows) > 10:
            out.append("LATER.md has no subject headings: group its lines under '## <subject>' and merge lines that ask for the same action")
    index = mem / "MEMORY.md"
    itext = index.read_text(encoding="utf-8", errors="replace") if index.exists() else ""
    topics = sorted((mem / "topics").glob("*.md")) if (mem / "topics").is_dir() else []
    ttext = "".join(t.read_text(encoding="utf-8", errors="replace") for t in topics)
    if len(itext.splitlines()) > INDEX_MAX:
        out.append(f"MEMORY.md has {len(itext.splitlines())} lines (limit {INDEX_MAX}): "
                   + ("move more note lines into their topic pages" if topics else
                      "create topic pages now (see 'Growing: topic pages'): group the notes by subject, one page each, "
                      "and replace their index lines with one line per page"))
    notes = sorted(p for p in (mem / "notes").glob("*.md") if not p.name.startswith("_")) if (mem / "notes").is_dir() else []
    names = {p.stem for p in notes}
    for p in notes:
        m = meta(p)
        if m is None:
            out.append(f"notes/{p.name}: no frontmatter: add it (see 'How to write a note')")
            continue
        if f"notes/{p.name}" not in itext and f"notes/{p.name}" not in ttext:
            out.append(f"notes/{p.name}: not listed in MEMORY.md or a topic page: add its line")
        if m.get("status") == "superseded" and not m.get("superseded_by"):
            out.append(f"notes/{p.name}: superseded but superseded_by is empty: name the note that replaced it")
        for k in ("supersedes", "superseded_by"):
            ref = (m.get(k) or "").strip().removesuffix(".md")
            if ref and ref not in names:
                out.append(f"notes/{p.name}: {k} {ref} is not a note: fix the slug")
        by = (m.get("superseded_by") or "").strip().removesuffix(".md")
        if by and m.get("status") != "superseded":
            out.append(f"notes/{p.name}: has superseded_by but status is {m.get('status')}: set status: superseded")
    for src, text, base in [(index.name, itext, mem)] + [(f"topics/{t.name}", t.read_text(encoding="utf-8", errors="replace"), t.parent) for t in topics]:
        for target in set(re.findall(r"\]\(([^)#\s]+\.md)\)", text)):
            if not re.match(r"[a-z]+:", target) and not (base / target).exists():
                out.append(f"{src}: link to {target} is broken: fix or remove the line")
    for line in out:
        print("FIX", line)
    print(f"{len(notes)} notes, {len(topics)} topic pages, MEMORY.md {len(itext.splitlines())} lines, "
          f"NOW.md {len(now.read_text().splitlines()) if now.exists() else 0} lines, "
          f"LATER.md {len(later.read_text().splitlines()) if later.exists() else 0} lines, {len(out)} to fix")
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
