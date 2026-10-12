#!/usr/bin/env python3
"""Build the codmod menu pk3s without shipping id Software's menu files.

Our .menu files are edited versions of RTCW's own menus (game data, not GPL). Git therefore stores only
*deltas*: for every derived file, the lines we wrote plus the line ranges of the original to replace. Passages
that came from an original (moved or reused blocks, even from another menu) are stored as *references* to line
ranges of the user's own RTCW paks, never as text. Only braces/blank lines and one-line property assignments whose
indentation differs from the original (`name back`, `border 0`) stay literal. The originals are read from the
user's paks, verified by SHA-256, and the delta is applied to produce the full file in mod/codmod/ui/ (git-ignored).

  menus.py build            generate missing/outdated ui files from deltas, then pack the pk3s
  menus.py build --export   also refresh deltas from locally edited ui files (developer workflow)
  menus.py export           only refresh deltas

Delta format (mod/codmod/menu-deltas/<name>.delta):
  line 1:  #codmod-delta v2 base=<path inside paks> sha256=<normalised original>
  #src <path inside paks> sha256=<...>     one line per other original that is referenced below
  hunks:   @@ <start> <end>     replace original lines [start, end) (0-based) of the base with what follows:
           +<new line>          a literal line of ours
           =<path> <a> <b>      lines [a, b) (0-based) of that original (base or #src file)
"""
import argparse, difflib, hashlib, json, os, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "mod" / "codmod"
UI = MOD / "ui"
DELTAS = MOD / "menu-deltas"
STATE = UI / ".menus-state.json"
PAKS = ["pak0.pk3", "sp_pak1.pk3", "sp_pak2.pk3", "sp_pak3.pk3", "sp_pak4.pk3"]  # later overrides earlier
MIN_RUN = 3       # a run of only trivial lines (braces, blanks) shorter than this stays literal
MIN_REUSE = 0.15  # share of our non-trivial lines that also exist in a base => treat as derived


def die(msg):
    sys.exit(f"menus: {msg}")


def pak_dirs():
    dirs = []
    if os.environ.get("RTCW_DATA"):
        dirs.append(Path(os.environ["RTCW_DATA"]))
    dirs.append(ROOT / "run" / "main")
    home = Path.home()
    dirs += [home / ".local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main",
             home / ".steam/steam/steamapps/common/Return to Castle Wolfenstein/Main"]
    return dirs


def load_originals():
    """Return {name: normalised text lines} for every ui/* menu text file in the user's paks."""
    found = [d for d in pak_dirs() if (d / "sp_pak1.pk3").exists()]
    if not found:
        die("RTCW paks not found. Run scripts/setup.sh, or set RTCW_DATA to your '.../Return to Castle Wolfenstein/Main'.")
    d = found[0]
    out = {}
    for pak in PAKS:
        f = d / pak
        if not f.exists():
            continue
        with zipfile.ZipFile(f) as z:
            for n in z.namelist():
                if n.startswith("ui/") and n.count("/") == 1 and n.endswith((".menu", ".txt", ".h")):
                    out[n] = z.read(n).decode("latin-1").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return out


def sha(lines):
    return hashlib.sha256("\n".join(lines).encode("latin-1")).hexdigest()


def trivial(l):
    return len(l.strip()) < 8


def line_index(originals):
    """{line: [(name, i), ...]} over every original, for finding reusable runs."""
    idx = {}
    for name, lines in originals.items():
        for i, l in enumerate(lines):
            idx.setdefault(l, []).append((name, i))
    return idx


def split_runs(new, originals, idx, base_name):
    """Greedy: cover `new` with references to original runs (>= MIN_RUN lines) and literal lines."""
    out, i = [], 0
    while i < len(new):
        best = (0, None, 0)
        for name, a in idx.get(new[i], ()):
            src = originals[name]
            n = 0
            while i + n < len(new) and a + n < len(src) and new[i + n] == src[a + n]:
                n += 1
            if n > best[0] or (n == best[0] and name == base_name and best[1] != base_name):
                best = (n, name, a)
        n = best[0]
        if n and (n >= MIN_RUN or not all(trivial(l) for l in new[i:i + n])):
            out.append(f"={best[1]} {best[2]} {best[2] + n}")
            i += n
        else:
            out.append("+" + new[i])
            i += 1
    return out


def make_delta(base_name, base, new, originals=None, idx=None):
    sm = difflib.SequenceMatcher(None, base, new, autojunk=False)
    body, used = [], set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        body.append(f"@@ {i1} {i2}")
        if originals is None:
            body += ["+" + l for l in new[j1:j2]]
            continue
        segs = split_runs(new[j1:j2], originals, idx, base_name)
        used |= {s[1:].split()[0] for s in segs if s[0] == "="}
        body += segs
    out = [f"#codmod-delta v2 base={base_name} sha256={sha(base)}"]
    if originals is not None:
        out += [f"#src {n} sha256={sha(originals[n])}" for n in sorted(used - {base_name})]
    return "\n".join(out + body) + "\n"


def apply_delta(text, originals):
    lines = text.split("\n")
    hdr = lines[0].split()
    if hdr[:2] != ["#codmod-delta", "v2"]:
        die("unknown delta format")
    base_name = hdr[2].split("=", 1)[1]
    checks = [(base_name, hdr[3].split("=", 1)[1])]
    hunks, cur = [], None
    for l in lines[1:]:
        if l.startswith("#src "):
            _, n, h = l.split()
            checks.append((n, h.split("=", 1)[1]))
        elif l.startswith("@@ "):
            _, a, b = l.split()
            cur = [int(a), int(b), []]
            hunks.append(cur)
        elif l.startswith("+"):
            cur[2].append(l[1:])
        elif l.startswith("="):
            n, a, b = l[1:].split()
            if n not in dict(checks):
                die(f"delta references {n} without a #src line")
            cur[2] += originals[n][int(a):int(b)]
    for n, want in checks:
        if n not in originals:
            die(f"{n} not found in your RTCW paks")
        if sha(originals[n]) != want:
            die(f"{n} in your paks differs from the version this mod was built against "
                f"(expected the RTCW 1.41 data). Cannot rebuild menus.")
    base = originals[base_name]
    res, pos = [], 0
    for a, b, new in hunks:
        res += base[pos:a] + new
        pos = b
    res += base[pos:]
    return "\n".join(res)


def best_base(new, originals):
    """Pick the original that shares the most non-trivial lines with `new`; None if below threshold."""
    nt = [l for l in new if not trivial(l)]
    if not nt:
        return None, 0.0
    cnt = {}
    best = (None, 0.0)
    for name, base in originals.items():
        if not name.endswith(".menu"):
            continue
        bs = {}
        for l in base:
            if not trivial(l):
                bs[l] = bs.get(l, 0) + 1
        used, hit = {}, 0
        for l in nt:
            if used.get(l, 0) < bs.get(l, 0):
                used[l] = used.get(l, 0) + 1
                hit += 1
        r = hit / len(nt)
        if r > best[1]:
            best = (name, r)
    return best if best[1] >= MIN_REUSE else (None, best[1])


def pick_base(new, originals):
    """Among the originals sharing the most lines with `new`, take the one giving the smallest delta."""
    name, r = best_base(new, originals)
    if name is None:
        return None
    ranked = sorted(((n, 0) for n in originals if n.endswith(".menu")), key=lambda t: t[0])
    nt = {l for l in new if not trivial(l)}
    scored = sorted(ranked, key=lambda t: -len(nt & {l for l in originals[t[0]] if not trivial(l)}))[:5]
    return min((n for n, _ in scored), key=lambda n: make_delta(n, originals[n], new).count("\n+"))


def read_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def fhash(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def derived_files():
    return sorted(DELTAS.glob("*.delta")) if DELTAS.exists() else []


def export(originals):
    DELTAS.mkdir(exist_ok=True)
    state = read_state()
    kept = []
    idx = line_index(originals)
    for f in sorted(UI.glob("*.menu")):
        new = f.read_text(encoding="latin-1").replace("\r\n", "\n").split("\n")
        # prefer the previous base for this file, so the delta stays stable
        prev = DELTAS / (f.name + ".delta")
        base_name = None
        if prev.exists():
            base_name = prev.read_text().split("\n", 1)[0].split()[2].split("=", 1)[1]
        elif "ui/" + f.name in originals:
            base_name = "ui/" + f.name  # edited version of the same-named original
        else:
            base_name = pick_base(new, originals)
        if base_name is None:
            kept.append(f.name)  # entirely our own file: stays in git as is
            if prev.exists():
                prev.unlink()
            continue
        d = make_delta(base_name, originals[base_name], new, originals, idx)
        if not prev.exists() or prev.read_text() != d:
            prev.write_text(d)
            print(f"export: {prev.name} ({base_name})")
        state[f.name] = {"delta": hashlib.sha256(d.encode()).hexdigest(), "file": fhash(f)}
    STATE.write_text(json.dumps(state, indent=1))
    write_gitignore(originals)
    return kept


def write_gitignore(originals=None):
    names = [p.name[:-6] for p in derived_files()]
    (UI / ".gitignore").write_text(
        "# Generated from menu-deltas/ by scripts/menus.py (derived from RTCW's own menus: not redistributed)\n"
        + "".join(f"/{n}\n" for n in names) + "/.menus-state.json\n")


def generate(originals, export_too):
    state = read_state()
    for dp in derived_files():
        name = dp.name[:-6]
        target = UI / name
        dtext = dp.read_text()
        dsha = hashlib.sha256(dtext.encode()).hexdigest()
        st = state.get(name)
        if not target.exists() or (st and st["file"] == fhash(target) and st["delta"] != dsha):
            target.write_text(apply_delta(dtext, originals), encoding="latin-1", newline="\n")
            state[name] = {"delta": dsha, "file": fhash(target)}
            print(f"generate: ui/{name}")
        elif not st:
            state[name] = {"delta": dsha, "file": fhash(target)}
        elif st["file"] != fhash(target) and not export_too:
            print(f"note: ui/{name} has local edits not in its delta (run: scripts/menus.py export)")
    STATE.write_text(json.dumps(state, indent=1))


def pack(out, entries):
    tmp = out.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for arc, path in sorted(entries):
            zi = zipfile.ZipInfo(arc, (2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, path.read_bytes())
    tmp.replace(out)
    print(f"built {out} ({len(entries)} entries)")


def build_paks():
    files = [(f"ui/{p.relative_to(UI).as_posix()}", p) for p in UI.rglob("*")
             if p.is_file() and not p.name.startswith(".")]
    pack(MOD / "codmod_menus.pk3", files)
    hud = [(f"ui/{n}", UI / n) for n in ("hud.menu", "menudef.h")]
    pack(MOD / "codmod_hud.pk3", hud)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "export"])
    ap.add_argument("--export", action="store_true")
    a = ap.parse_args()
    originals = load_originals()
    if a.cmd == "export" or a.export:
        kept = export(originals)
        print("own files kept whole in git:", ", ".join(kept) or "-")
    if a.cmd == "build":
        generate(originals, a.export)
        write_gitignore(originals)
        build_paks()


main()
