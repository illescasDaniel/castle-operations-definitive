"""Build codmod's menu pk3s without shipping id Software's menu files.

The delta machinery and the engine layer live in the engine fork: iortcw/SP/menus/menudelta.py (format and rules in
its docstring). Two layers (docs/menus.md):
  engine  iortcw/SP/menus/deltas/ on RTCW's original menus -> iortcw/SP/menus/ui/
          -> iortcw/SP/menus/sp_zz_engine_menus.pk3 (installed to run/main/; rows for engine features only)
  codmod  mod/codmod/menu-deltas/codmod/ on the engine-layer result -> mod/codmod/ui/
          -> mod/codmod/codmod_menus.pk3 + codmod_hud.pk3 (layout + mod rows). A .menu file that exists in the engine
          layer but has no codmod delta is copied unchanged from the engine layer.

  menus.py build            generate missing/outdated ui files from deltas (engine first), then pack the pk3s
  menus.py build --export   also refresh deltas from locally edited ui files (developer workflow)
  menus.py export           only refresh deltas (engine ui edits -> iortcw/SP/menus/deltas/, codmod ui edits -> codmod/)
"""
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "iortcw" / "SP" / "menus"))
import menudelta as md  # noqa: E402

MOD = ROOT / "mod" / "codmod"
UI = MOD / "ui"                                   # codmod layer output
CODMOD = md.Layer("codmod", UI, MOD / "menu-deltas" / "codmod", base=md.ENGINE)


def load_originals():
    return md.load_originals([ROOT / "run" / "main"])


def export(originals):
    idx = md.line_index(originals)
    kept = md.export_layer(md.ENGINE, originals, idx)
    eng = md.layer_texts(md.ENGINE, originals)
    kept += md.export_layer(CODMOD, originals, idx, eng)
    write_gitignore(originals)
    return kept


def write_gitignore(originals=None):
    hdr = "# Generated from menu-deltas/ by scripts/menus.py (derived from RTCW's own menus: not redistributed)\n"
    eng = {"ui/" + dp.name[:-6] for dp in md.delta_files(md.ENGINE)}
    (UI / ".gitignore").write_text(
        hdr + "".join(f"/{n}\n" for n in sorted({dp.name[:-6] for dp in md.delta_files(CODMOD)}
                                                | {k[3:] for k in eng if k.endswith(".menu")}))
        + "/.menus-state.json\n")
    md.engine_gitignore()


def generate(originals, export_too):
    eng = md.layer_texts(md.ENGINE, originals)
    md.generate_layer(md.ENGINE, originals, export_too=export_too)
    md.generate_layer(CODMOD, originals, eng, export_too)


def build_paks():
    files = [(f"ui/{p.relative_to(UI).as_posix()}", p) for p in UI.rglob("*")
             if p.is_file() and not p.name.startswith(".")]
    md.pack(MOD / "codmod_menus.pk3", files)
    hud = [(f"ui/{n}", UI / n) for n in ("hud.menu", "menudef.h")]
    md.pack(MOD / "codmod_hud.pk3", hud)
    md.build_engine_pk3()


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
