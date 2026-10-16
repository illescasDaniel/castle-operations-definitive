#!/usr/bin/env python3
"""Build the English source catalog that translators work from.

Reads (never writes) the generated menus in mod/codmod/ui, the RTCW paks and the
engine sources in iortcw/SP/code. Writes tools/l10n/build/:

  catalog.json            every unique displayed English string with where/context/maxlen
  en/strings.txt          catalog as an identity strings.txt (docs/languages.md format)
  en/text/<file>.txt      player-readable text/EnglishUSA files (paks, override order applied)
  text_files.json         description + format notes for those files

Usage: python3 tools/l10n/extract.py [--rtcw DIR]   (python3 stdlib only, deterministic)
"""
import argparse
import json
import os
import re
import sys
import zipfile
from collections import OrderedDict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "iortcw", "SP", "code")
UI_DIR = os.path.join(ROOT, "mod", "codmod", "ui")
OUT = os.path.join(ROOT, "tools", "l10n", "build")
DEFAULT_RTCW = os.path.expanduser(
    "~/.steam/steam/steamapps/common/Return to Castle Wolfenstein/Main")
# SP paks only, in override order (later wins). mp_* paks are multiplayer.
PAK_ORDER = ["pak0", "sp_pak1", "sp_pak2", "sp_pak3", "sp_pak4"]

# ---------------------------------------------------------------------------
# catalog
# ---------------------------------------------------------------------------


class Catalog:
    def __init__(self):
        self.entries = OrderedDict()   # key -> dict
        self.groups = OrderedDict()    # group title -> [keys] in first-seen order
        self.counts = OrderedDict()    # source label -> number of (key, where) records

    def add(self, key, where, context, group, maxlen=None, source=None):
        if key is None or key == "" or not key.strip():
            return
        e = self.entries.get(key)
        if e is None:
            e = {"key": key, "where": [], "context": context, "maxlen": maxlen}
            e["_contexts"] = [context]
            self.entries[key] = e
            self.groups.setdefault(group, []).append(key)
        else:
            if context not in e["_contexts"]:
                e["_contexts"].append(context)
            if maxlen is not None and (e["maxlen"] is None or maxlen < e["maxlen"]):
                e["maxlen"] = maxlen
            # keep the first group a key was seen in (so strings.txt has no duplicates)
        if where not in e["where"]:
            e["where"].append(where)
        src = source or group
        self.counts[src] = self.counts.get(src, 0) + 1

    def finish(self):
        out = []
        for key, e in self.entries.items():
            ctxs = e.pop("_contexts")
            e["context"] = ctxs[0] if len(ctxs) == 1 else " / ".join(ctxs[:3])
            out.append(e)
        return out


# ---------------------------------------------------------------------------
# paks
# ---------------------------------------------------------------------------

class Paks:
    def __init__(self, base):
        self.base = base
        self.files = {}      # lowercased name -> (pak, real name)
        self.zips = {}
        for p in PAK_ORDER:
            path = os.path.join(base, p + ".pk3")
            if not os.path.exists(path):
                continue
            z = zipfile.ZipFile(path)
            self.zips[p] = z
            for n in z.namelist():
                if n.endswith("/"):
                    continue
                self.files[n.lower()] = (p, n)

    def read(self, name):
        p, n = self.files[name.lower()]
        return self.zips[p].read(n)

    def pak_of(self, name):
        return self.files[name.lower()][0]

    def listdir(self, prefix, suffix=""):
        prefix = prefix.lower()
        return sorted(v[1] for k, v in self.files.items()
                      if k.startswith(prefix) and k.endswith(suffix))


def decode(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("latin-1")


# ---------------------------------------------------------------------------
# menu parsing
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|(//[^\n]*)|(/\*.*?\*/)|([{}])|([^\s{}"]+)', re.S)


def tokenize(text):
    """Return list of (kind, value, line). kind: 's' string, 'w' word, '{', '}'."""
    toks = []
    line = 1
    pos = 0
    for m in TOKEN_RE.finditer(text):
        line += text.count("\n", pos, m.start())
        pos = m.start()
        if m.group(1) is not None:
            toks.append(("s", m.group(1), line))
        elif m.group(2) is not None or m.group(3) is not None:
            pass
        elif m.group(4):
            toks.append((m.group(4), m.group(4), line))
        else:
            toks.append(("w", m.group(5), line))
    return toks


class Item:
    def __init__(self, menu, line):
        self.menu = menu
        self.line = line
        self.name = ""
        self.text = None
        self.textfile = None
        self.textscale = None
        self.rect = None
        self.ownerdraw = None
        self.type = None
        self.wrap = None
        self.strlist = []      # (label, value)
        self.floatlist = []    # (label, value)
        self.tooltip = []
        self.listbox = False
        self.font = None
        self.cvar = None
        self.align = None


def parse_menu_file(text, fname):
    """Parse one .menu file; return list of Item."""
    toks = tokenize(text)
    items = []
    i = 0
    n = len(toks)
    menu_name = ""
    depth = 0
    # stack of ("menu"|"item"|"block", obj)
    stack = []
    while i < n:
        kind, val, line = toks[i]
        if kind == "{":
            if not stack or stack[-1][0] != "pending":
                stack.append(("block", None))
            i += 1
            continue
        if kind == "}":
            if stack:
                stack.pop()
            i += 1
            continue
        if kind == "w":
            lv = val.lower()
            if lv == "menudef" and i + 1 < n and toks[i + 1][0] == "{":
                stack.append(("menu", None))
                i += 2
                continue
            if lv == "itemdef" and i + 1 < n and toks[i + 1][0] == "{":
                it = Item(menu_name, line)
                items.append(it)
                stack.append(("item", it))
                i += 2
                continue
            top = stack[-1] if stack else (None, None)
            if top[0] == "menu":
                if lv == "name" and i + 1 < n:
                    menu_name = toks[i + 1][1]
                    i += 2
                    continue
            if top[0] == "item":
                it = top[1]
                nxt = toks[i + 1] if i + 1 < n else ("", "", 0)
                if lv == "name":
                    it.name = nxt[1]; i += 2; continue
                if lv == "text" and nxt[0] == "s":
                    it.text = nxt[1]; i += 2; continue
                if lv == "textfile" and nxt[0] == "s":
                    it.textfile = nxt[1]; i += 2; continue
                if lv == "textscale":
                    try:
                        it.textscale = float(nxt[1])
                    except ValueError:
                        pass
                    i += 2; continue
                if lv == "rect":
                    try:
                        it.rect = [float(toks[i + k][1]) for k in range(1, 5)]
                    except (ValueError, IndexError):
                        pass
                    i += 5; continue
                if lv == "ownerdraw":
                    it.ownerdraw = nxt[1]; i += 2; continue
                if lv == "type":
                    it.type = nxt[1]; i += 2; continue
                if lv == "style":
                    i += 2; continue
                if lv == "textfont":
                    it.font = nxt[1]; i += 2; continue
                if lv == "cvar" and nxt[0] == "s":
                    it.cvar = nxt[1]; i += 2; continue
                if lv == "textalign":
                    it.align = nxt[1]; i += 2; continue
                if lv in ("autowrapped", "wrapped"):
                    it.wrap = lv; i += 1; continue
                if lv in ("tooltip", "desctext", "description") and nxt[0] == "s":
                    it.tooltip.append((nxt[1], toks[i][2])); i += 2; continue
                if lv in ("cvarstrlist", "cvarfloatlist") and nxt[0] == "{":
                    j = i + 2
                    vals = []
                    while j < n and toks[j][0] != "}":
                        vals.append(toks[j])
                        j += 1
                    if lv == "cvarstrlist":
                        # "Label", "value", ... ; the commas are tokens of kind w ","
                        strs = [t for t in vals if t[0] == "s"]
                        for k in range(0, len(strs) - 1, 2):
                            it.strlist.append((strs[k][1], strs[k + 1][1], strs[k][2]))
                        if len(strs) % 2:
                            it.strlist.append((strs[-1][1], "", strs[-1][2]))
                    else:
                        for k, t in enumerate(vals):
                            if t[0] == "s":
                                it.floatlist.append((t[1], t[2]))
                    i = j + 1
                    continue
                if lv in ("listbox", "feeder", "elementwidth"):
                    it.listbox = True
        i += 1
    return items


def estimate_maxlen(it, text_is_list=False):
    """Rough number of characters that fit: width / (scale * ~34 px per char at scale 1)."""
    if not it.textscale or not it.rect:
        return None
    w = it.rect[2]
    if w <= 0:
        return None
    cw = it.textscale * 34.0
    return int(w / cw)


# ---------------------------------------------------------------------------
# helpers for text/strings
# ---------------------------------------------------------------------------

def unescape_c(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            d = s[i + 1]
            m = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'", "r": "\r"}
            if d in m:
                out.append(m[d]); i += 2; continue
        out.append(c)
        i += 1
    return "".join(out)


def strip_c_comments(src):
    """Blank out comments but keep line structure and string literals."""
    out = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                if src[j] == "\\":
                    j += 1
                j += 1
            out.append(src[i:j + 1]); i = j + 1
        elif c == "'":
            j = i + 1
            while j < n and src[j] != "'":
                if src[j] == "\\":
                    j += 1
                j += 1
            out.append(src[i:j + 1]); i = j + 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            if j < 0:
                j = n
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join("\n" if ch == "\n" else " " for ch in src[i:j]))
            i = j
        else:
            out.append(c); i += 1
    return "".join(out)


C_STR = r'((?:"(?:[^"\\\n]|\\.)*"\s*)+)'


def c_string_value(lit):
    parts = re.findall(r'"((?:[^"\\\n]|\\.)*)"', lit)
    return unescape_c("".join(parts))


# ---------------------------------------------------------------------------
# C source scanning
# ---------------------------------------------------------------------------

def read_src(rel):
    path = os.path.join(SRC, rel)
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def split_args(s):
    """Split a call argument string at top-level commas."""
    args, depth, cur, i = [], 0, [], 0
    while i < len(s):
        c = s[i]
        if c == '"':
            j = i + 1
            while j < len(s) and s[j] != '"':
                if s[j] == "\\":
                    j += 1
                j += 1
            cur.append(s[i:j + 1]); i = j + 1; continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == "," and depth == 0:
            args.append("".join(cur).strip()); cur = []
        else:
            cur.append(c)
        i += 1
    if cur:
        args.append("".join(cur).strip())
    return args


def find_calls(src, names):
    """Yield (name, pos, args[]) for calls of the given function names in comment-free source."""
    pat = re.compile(r"\b(" + "|".join(map(re.escape, names)) + r")\s*\(")
    for m in pat.finditer(src):
        i = m.end()
        depth = 1
        j = i
        while j < len(src) and depth:
            c = src[j]
            if c == '"':
                j += 1
                while j < len(src) and src[j] != '"':
                    if src[j] == "\\":
                        j += 1
                    j += 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            j += 1
        yield m.group(1), m.start(), split_args(src[i:j - 1])


def literal_of(arg):
    """If arg is a string literal (or va("literal", ...)), return its value, else None."""
    a = arg.strip()
    m = re.fullmatch(C_STR, a)
    if m:
        return c_string_value(a)
    m = re.fullmatch(r"va\s*\(\s*" + C_STR + r"(?:,.*)?\)", a, re.S)
    if m:
        return c_string_value(m.group(1))
    return None


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------

ITEM_TYPES = {
    "0": "TEXT", "1": "BUTTON", "2": "RADIOBUTTON", "3": "CHECKBOX", "4": "EDITFIELD", "5": "COMBO",
    "6": "LISTBOX", "7": "MODEL", "8": "OWNERDRAW", "9": "NUMERICFIELD", "10": "SLIDER", "11": "YESNO",
    "12": "MULTI", "13": "BIND", "14": "MENUMODEL", "15": "VALIDFILEFIELD",
}

CHAR_PX = 34.0   # rough width of one character in 640x480 px at textscale 1.0 (docs/menus.md: ~55 chars at .17 over 320 px)


def item_kind(it):
    t = it.type
    if t is None:
        return "TEXT"
    t = ITEM_TYPES.get(t, t)
    return t.replace("ITEM_TYPE_", "")


def menu_item_context(menu, it):
    kind = item_kind(it)
    if kind == "BIND":
        return "key binding row label"
    if kind in ("MULTI", "YESNO", "SLIDER", "EDITFIELD", "NUMERICFIELD", "VALIDFILEFIELD", "COMBO", "CHECKBOX"):
        return "options row label (%s)" % kind.lower()
    if kind == "LISTBOX":
        return "list header"
    if kind == "BUTTON":
        return "menu button"
    if it.ownerdraw:
        return "menu text (%s)" % it.ownerdraw
    return "menu label"


def text_maxlen(it):
    """Characters that fit in the item's rect on one line. Only for plain labels/buttons."""
    if item_kind(it) not in ("TEXT", "BUTTON"):
        return None
    return estimate_maxlen(it)


def parse_menu_list(name, mod_dir, paks):
    """Return (list of ui/x.menu names, source description) from a menus.txt-style file."""
    path = os.path.join(mod_dir, name)
    if os.path.exists(path):
        txt = open(path, encoding="utf-8", errors="replace").read()
    elif ("ui/" + name).lower() in paks.files:
        txt = decode(paks.read("ui/" + name))
    else:
        return []
    toks = tokenize(txt)
    out = []
    for i, (k, v, _) in enumerate(toks):
        if k == "w" and v.lower() == "loadmenu":
            for j in range(i + 1, min(i + 4, len(toks))):
                if toks[j][0] == "s":
                    out.append(toks[j][1]); break
    return out


def load_menu_text(menu_rel, paks):
    """menu_rel like ui/options.menu. Mod copy wins over the paks."""
    base = os.path.basename(menu_rel)
    path = os.path.join(UI_DIR, base)
    if os.path.exists(path):
        return open(path, encoding="utf-8", errors="replace").read(), "mod"
    if menu_rel.lower() in paks.files:
        return decode(paks.read(menu_rel)), paks.pak_of(menu_rel)
    return None, None


def is_credit_file(path):
    return os.path.basename(path).lower().startswith("credit")


def collect_menus(cat, paks, report):
    """Catalog all menu strings. Returns textfile references {path: [info]}."""
    listed = []
    for lst in ("menus.txt", "ingame.txt", "hud.txt"):
        for m in parse_menu_list(lst, UI_DIR, paks):
            if m not in listed:
                listed.append(m)
    report["menu_lists"] = ["menus.txt", "ingame.txt", "hud.txt"]
    # menus that exist in mod/codmod/ui but are not (yet) listed: still ours, include
    extra = sorted("ui/" + os.path.basename(f) for f in
                   (os.path.join(UI_DIR, n) for n in os.listdir(UI_DIR)) if f.endswith(".menu")
                   and "ui/" + os.path.basename(f) not in listed)
    report["menus_unlisted_but_included"] = extra
    textrefs = {}
    missing = []
    per_menu = OrderedDict()
    for menu_rel in listed + extra:
        text, src = load_menu_text(menu_rel, paks)
        if text is None:
            missing.append(menu_rel)
            continue
        base = os.path.basename(menu_rel)
        group = "menu: " + base
        items = parse_menu_file(text, base)
        n0 = 0
        for it in items:
            where = "%s:%d" % (base, it.line)
            if it.name:
                where += " (" + it.name + ")"
            if it.text and item_kind(it) != "OWNERDRAW" or (it.text and it.ownerdraw):
                if it.text.strip():
                    cat.add(it.text, where, menu_item_context(base, it), group, text_maxlen(it), "menus")
                    n0 += 1
            for label, value, line in it.strlist:
                w = "%s:%d (%s)" % (base, line, it.name or it.cvar or "")
                note = None
                cat.add(label, w, "cvarStrList value", group, None, "menus")
                n0 += 1
            for label, line in it.floatlist:
                w = "%s:%d (%s)" % (base, line, it.name or it.cvar or "")
                cat.add(label, w, "cvarFloatList value", group, None, "menus")
                n0 += 1
            for tip, line in it.tooltip:
                cat.add(tip, "%s:%d (%s)" % (base, line, it.name or ""), "tooltip", group, None, "menus")
                n0 += 1
            if it.textfile and not is_credit_file(it.textfile):
                textrefs.setdefault(it.textfile, []).append({
                    "menu": base, "item": it.name, "line": it.line, "rect": it.rect,
                    "textscale": it.textscale, "font": it.font, "wrap": it.wrap})
            elif it.textfile:
                textrefs.setdefault(it.textfile, [])  # credits: remembered but skipped
        per_menu[base] = (src, len(items), n0)
    report["menus_missing"] = missing
    report["menus_found"] = {k: {"from": v[0], "items": v[1], "strings": v[2]} for k, v in per_menu.items()}
    return textrefs


# --- translateStrings / strings.txt ----------------------------------------

def parse_translate_table():
    src = read_src("ui/ui_shared.c")
    m = re.search(r"translateString_t\s+translateStrings\[\]\s*=\s*\{(.*?)\n\};", src, re.S)
    body = m.group(1)
    return re.findall(r'\{\s*"([^"]+)"\s*\}', strip_c_comments(body)), src[:m.start()] + src[m.end():]


def com_parse_tokens(text):
    """COM_ParseExt(&text, qtrue) equivalent: quoted strings or bare words, // comments."""
    toks = []
    for m in re.finditer(r'"([^"]*)"|//[^\n]*|(\S+)', text):
        if m.group(1) is not None:
            toks.append(m.group(1))
        elif m.group(2) is not None:
            toks.append(m.group(2))
    return toks


def unescape_literal_n(s):
    """pak strings.txt stores a newline as the two characters backslash,n (centerprint code accepts both)."""
    return s.replace("\\n", "\n")


TRANSLATE_CONTEXT = {
    "end_": "mission stats screen label (drawn as \"<text>:\")",
    "missionfail": "centerprint: mission failed",
    "yes": "options yes/no value",
    "no": "options yes/no value",
    "keywait": "key binding status line",
    "keychange": "key binding status line",
    "or": "key binding row (joins two keys: \"A or B\")",
    "pleasewait": "loading text",
    "dynamitetimer": "centerprint (dynamite timer: \"<text> N <seconds>\")",
    "seconds": "centerprint (dynamite timer unit)",
    "second": "time unit",
    "gamesaved": "centerprint",
    "secretarea": "centerprint",
    "objectivesnotcomplete": "centerprint",
    "drankwine": "centerprint",
    "noitem": "centerprint",
}


def collect_strings_txt(cat, paks, report, all_src):
    names, ui_shared_wo_table = parse_translate_table()
    ptxt = decode(paks.read("text/strings.txt"))
    pak = paks.pak_of("text/strings.txt")
    toks = com_parse_tokens(ptxt)
    other_src = ui_shared_wo_table + "\n" + all_src
    used, unused = [], []
    for i, name in enumerate(names):
        if i >= len(toks):
            break
        val = unescape_literal_n(toks[i])
        # is the name referenced anywhere (CG_translateString("x"), "cp x", getTranslatedString)?
        pat = '"' + name + '"'
        pat2 = None
        if name.startswith("missionfail"):
            pat2 = "missionfail%d"
        is_used = pat in other_src or (pat2 and pat2 in other_src) or ("cp " + name) in other_src
        if name.startswith("end_") and pat not in other_src:
            is_used = ('"%s"' % name) in all_src
        if name.startswith("missionfail") and re.fullmatch(r"fail \d+", val):
            is_used = False   # placeholder text "fail 8" ... never meant to be shown
        if not is_used:
            unused.append(name)
            continue
        used.append(name)
        ctx = None
        for pref, c in TRANSLATE_CONTEXT.items():
            if name == pref or (pref.endswith("_") and name.startswith(pref)) or \
               (pref == "missionfail" and name.startswith("missionfail")):
                ctx = c
                break
        cat.add(val, "text/strings.txt:%d (%s, %s)" % (i + 1, name, pak), ctx or "translated string",
                "game strings (text/strings.txt)", None, "strings.txt")
    report["strings_txt"] = {"pak": pak, "entries_in_file": len(toks), "table_entries": len(names),
                             "catalogued": used, "skipped_unused": unused}


# --- pickup names ------------------------------------------------------------

def parse_itemlist():
    src = strip_c_comments(read_src("game/bg_misc.c"))
    m = re.search(r"gitem_t\s+bg_itemlist\[\]\s*=\s*\{", src)
    i = m.end()
    items = []
    depth = 1
    start = None
    j = i
    while j < len(src) and depth:
        c = src[j]
        if c == '"':
            j += 1
            while src[j] != '"':
                if src[j] == "\\":
                    j += 1
                j += 1
        elif c == "{":
            depth += 1
            if depth == 2:
                start = j + 1
        elif c == "}":
            depth -= 1
            if depth == 1:
                items.append(src[start:j])
        j += 1
    out = []
    for body in items:
        fields = split_args(body)
        # fields: classname, sound, {models}, icon, ammoicon, pickup_name, ...
        def lit(k):
            if k >= len(fields):
                return None
            f = fields[k].strip()
            if f == "NULL":
                return None
            m2 = re.fullmatch(C_STR, f)
            return c_string_value(f) if m2 else None
        out.append({"classname": lit(0), "pickup_name": lit(5)})
    return out


def collect_pickups(cat, paks, report):
    items = parse_itemlist()
    ptxt = decode(paks.read("text/pickupnames.txt"))
    pak = paks.pak_of("text/pickupnames.txt")
    toks = com_parse_tokens(ptxt)
    n = 0
    for i, tok in enumerate(toks):
        if i >= len(items):
            break
        name = items[i]["pickup_name"] if tok.strip().lower() == "---" else tok
        if not name:
            continue
        cls = items[i]["classname"] or "item%d" % i
        cat.add(name, "text/pickupnames.txt:%d (%s, %s)" % (i + 1, cls, pak),
                "pickup name (HUD pickup text, holdable/weapon name, \"Use %s\")",
                "pickup names (text/pickupnames.txt + bg_itemlist)", None, "pickups")
        n += 1
    report["pickups"] = {"pak": pak, "tokens": len(toks), "bg_itemlist_entries": len(items), "catalogued": n}


# --- hardcoded literals in C ---------------------------------------------------
# Curated list of literals that reach the screen in single player. Each entry is verified
# against the current source (a warning is printed if it moved or vanished).
# (file, literal, context, group, note, maxlen)

CGAME_G = "HUD / cgame literals"
UI_G = "UI literals (ui_main.c)"
GAME_G = "game literals"

C_LITERALS = [
    ("cgame/cg_draw.c", "Connection Interrupted", "HUD: centred warning when the network stalls (rare in SP)", CGAME_G, None, 26),
    ("cgame/cg_info.c", "please wait", "loading screen status line (small centred text)", CGAME_G, None, 20),
    ("cgame/cg_event.c", "Use %s", "centerprint when a holdable item is used; %s is a pickup name", CGAME_G,
     "format: %s is replaced by the item's pickup name at runtime (the combined string cannot be matched exactly)", 40),
    ("cgame/cg_newdraw.c", "Breakable", "HUD cursor hint above the crosshair (codmod)", CGAME_G, None, 24),
    ("cgame/cg_newdraw.c", "Hold to interact", "HUD cursor hint above the crosshair, gamepad variant (codmod)", CGAME_G, None, 24),
    ("cgame/cg_newdraw.c", "Press F to interact", "HUD cursor hint above the crosshair, keyboard variant (codmod)", CGAME_G,
     "the key letter F is hardcoded (default of +activate), not read from the binding", 24),
    ("ui/ui_main.c", "VENDOR: %s", "GL info panel (UI_GLINFO ownerdraw)", UI_G,
     "format: %s is the driver string; the whole line is drawn as one string so exact matching is impossible", None),
    ("ui/ui_main.c", "VERSION: %s: %s", "GL info panel (UI_GLINFO ownerdraw)", UI_G,
     "format: two driver strings; exact matching impossible", None),
    ("ui/ui_main.c", "PIXELFORMAT: color(%d-bits) Z(%d-bits) stencil(%d-bits)", "GL info panel (UI_GLINFO ownerdraw)", UI_G,
     "format: three numbers; exact matching impossible", None),
    ("ui/ui_main.c", "(no savegames)", "savegame info panel when the list is empty", UI_G, None, 20),
    ("ui/ui_main.c", "Gametime: (unknown)\nHealth: (unknown)\n(old savegame)", "savegame info panel for very old saves", UI_G, None, None),
    ("ui/ui_main.c", "(old savegame)", "savegame list date column for very old saves", UI_G, None, 16),
    ("ui/ui_main.c", "(old savegame ver: %d)", "savegame list date column for old saves", UI_G, "format: %d is the version number", 24),
    ("ui/ui_main.c", "(old save ver: %d)", "savegame list date column for old saves", UI_G, "format: %d is the version number", 24),
    ("game/g_save.c", "Leveltime", "savegame info text, first label (baked into the save file when saving)", GAME_G,
     "written into the .svg file as 'MAP\\nLeveltime: 1h02m03s\\nHealth: 100' at save time and shown unchanged in the load/save screens; "
     "the label is not translated when displaying an older save. Ideally translate when the info string is built or parsed", None),
    ("game/g_save.c", "Health", "savegame info text, second label (baked into the save file when saving)", GAME_G,
     "see Leveltime", None),
]

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# Files that are checked for sink calls whose literal is not curated above (review list for humans).
# Everything listed here is intentionally not catalogued: multiplayer-only, debug, or console output.
SINK_IGNORE_FILES = {
    "cgame/cg_scoreboard.c": "multiplayer scoreboard (not reachable in SP)",
    "cgame/cg_consolecmds.c": "multiplayer team/class messages",
    "cgame/cg_cod_menu.c": "developer tuning menu",
    "cgame/cg_cod.c": "developer debug HUD",
}
SINK_IGNORE_LITERALS = {
    "snc": "debug lagometer", "SPECTATOR": "MP", "waiting to play": "MP", "use the TEAM menu to play": "MP",
    "following": "MP", "Axis: %s": "MP", "Ally: %s": "MP", "MISSION STATS": "unused (CG_DrawStats is dead code in SP)",
    "estimating": "download screen (MP)", "(%s of %s copied)": "download screen (MP)", "(%s copied)": "download screen (MP)",
    "%s/Sec": "download screen (MP)", "Starting up...": "connect screen (MP)",
    "Source: %s": "server browser (MP)", "Filter: %s": "server browser (MP)", "Tier: %s": "MP",
    "Getting info for %d servers (ESC to cancel)": "server browser (MP)", "Refresh Time: %s": "server browser (MP)",
    "%s: %s": "MP team list", "%02i:%02i": "time format", "%d.": "number", "%d/%d": "number", "%d": "number",
    "%2i": "number", "%4i": "number", "%s": "pass-through (already translated)", "%s:": "label suffix, see strings.txt",
    "%s %d %s": "dynamite timer; pieces are strings.txt entries",
    "Ten seconds until inactivity drop!\n": "MP", "The Axis has too many players.\n": "MP",
    "The Allies have too many players.\n": "MP", "Axis engineer disarmed a det charge!\n": "MP engineer class",
    "Allied engineer disarmed a det charge!\n": "MP engineer class", "You have repaired the MG42!\n": "MP engineer class",
    "%s": "pass-through (script / entity text)",
    "cp missionfail%d": "strings.txt key", "cp objectivesnotcomplete": "strings.txt key", "cp secretarea": "strings.txt key",
    "cp missionfail0": "strings.txt key", "cp gamesaved": "strings.txt key", "noitem": "strings.txt key",
    "drankwine": "strings.txt key",
}


def find_literal_lines(src_text, value):
    """Line numbers where the C string literal (possibly spliced) whose value == value occurs."""
    hits = []
    for m in re.finditer(C_STR, src_text):
        if c_string_value(m.group(1)) == value:
            hits.append(line_of(src_text, m.start()))
    return hits


def collect_c_literals(cat, report):
    cache = {}
    missing = []
    curated_values = set()
    for rel, lit, ctx, group, note, maxlen in C_LITERALS:
        if rel not in cache:
            cache[rel] = strip_c_comments(read_src(rel))
        lines = find_literal_lines(cache[rel], lit)
        if not lines:
            missing.append((rel, lit))
            continue
        curated_values.add(lit)
        where = ["%s:%d" % (rel, ln) for ln in lines[:3]]
        for w in where:
            cat.add(lit, w, ctx, group, maxlen, "C literals")
        if note:
            cat.entries[lit].setdefault("note", note)
    # month names used to build the savegame date column ("%s %i, %i   %02i:%02i")
    ui_main = strip_c_comments(read_src("ui/ui_main.c"))
    if re.search(r'monthStr\[12\]\s*=\s*\{[^}]*"JAN"', ui_main):
        m = re.search(r'monthStr\[12\]', ui_main)
        for k, mon in enumerate(MONTHS):
            cat.add(mon, "ui/ui_main.c:%d (monthStr[%d])" % (line_of(ui_main, m.start()), k),
                    "savegame list date column: month abbreviation", UI_G, 4, "C literals")
            cat.entries[mon].setdefault(
                "note", "inserted into 'MON D, YYYY   HH:MM' by va(); only translatable if the code translates each month name "
                        "before formatting (the combined date string cannot be matched)")
    else:
        missing.append(("ui/ui_main.c", "monthStr[]"))
    report["c_literals_missing"] = missing
    return curated_values


def scan_uncurated(curated_values):
    """Report string literals passed to draw/print sinks that are neither curated nor on the ignore list."""
    SINKS = ["CG_Text_Paint", "CG_DrawBigString", "CG_DrawBigStringColor", "CG_DrawBigString2", "CG_DrawSmallString",
             "CG_DrawSmallStringColor", "CG_DrawStringExt", "CG_DrawStringExt2", "CG_DrawStringExt3", "CG_CenterPrint",
             "CG_PriorityCenterPrint", "CG_ObjectivePrint", "UI_DrawProportionalString", "UI_DrawString", "Text_Paint",
             "Text_PaintCenter", "Text_PaintWithCursor", "trap_SendServerCommand", "CG_DrawCodString"]
    out = []
    for d in ("cgame", "ui", "game"):
        folder = os.path.join(SRC, d)
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith(".c"):
                continue
            rel = "%s/%s" % (d, fn)
            if rel in SINK_IGNORE_FILES:
                continue
            src = strip_c_comments(read_src(rel))
            for name, pos, args in find_calls(src, SINKS):
                if name == "trap_SendServerCommand":
                    lits = [literal_of(a) for a in args]
                    lits = [l for l in lits if l is not None]
                    if not lits or not lits[0].startswith("cp"):
                        continue
                    val = lits[0]
                    m = re.fullmatch(r'cp\s+"(.*)"', val, re.S)
                    v2 = m.group(1) if m else val
                    val = v2 if v2 in SINK_IGNORE_LITERALS else val
                else:
                    lits = [literal_of(a) for a in args]
                    lits = [l for l in lits if l]
                    if not lits:
                        continue
                    val = lits[0]
                if val in curated_values or val in SINK_IGNORE_LITERALS:
                    continue
                out.append("%s:%d %s(%r)" % (rel, line_of(src, pos), name, val))
    # hint text assignments in cg_newdraw.c
    return out


# --- text files ----------------------------------------------------------------

TEXT_PREFIX = "text/englishusa/"
STRING_POOL = 384 * 1024
MENUDEF_BUF = 4096

TEXT_QUIRKS = ("Loaded by the menu 'textfile' keyword (UI_FileText) into one static buffer of %d bytes: a longer file is "
               "truncated or breaks. Plain text, Latin-1 after conversion; the menu word-wraps it at the item width. "
               "A blank line gives a paragraph break; '\\n' is not interpreted. " % MENUDEF_BUF)


def export_text_files(paks, textrefs, report):
    en_dir = os.path.join(OUT, "en", "text")
    os.makedirs(en_dir, exist_ok=True)
    all_files = [n for n in paks.listdir(TEXT_PREFIX, ".txt")]
    referenced = {}
    for ref in textrefs:
        referenced[ref.lower()] = ref
    meta = []
    missing = []
    total = 0
    for low in sorted(referenced):
        ref = referenced[low]
        if is_credit_file(ref):
            continue
        if low not in paks.files:
            missing.append(ref)
            continue
        data = paks.read(low)
        base = os.path.basename(paks.files[low][1])
        with open(os.path.join(en_dir, base), "wb") as f:
            f.write(data)
        total += len(data)
        uses = textrefs[ref]
        shown = []
        for u in uses:
            r = u["rect"]
            d = {"menu": u["menu"], "item": u["item"], "line": u["line"]}
            if r:
                d["rect"] = r
            if u["textscale"]:
                d["textscale"] = u["textscale"]
            if u["font"]:
                d["font"] = u["font"]
            d["wrap"] = u["wrap"] or "none"
            if r and u["textscale"]:
                cpl = int(r[2] / (u["textscale"] * CHAR_PX))
                lines = int(r[3] / (u["textscale"] * 60.0)) if r[3] > 0 else None
                d["approx_chars_per_line"] = cpl
                d["approx_lines"] = lines
            shown.append(d)
        txt = decode(data)
        meta.append({
            "file": base, "path": paks.files[low][1], "pak": paks.pak_of(low), "bytes": len(data),
            "shown_in": ["%s:%s" % (u["menu"], u["item"] or u["line"]) for u in uses],
            "description": "Shown in menu item(s): " + ", ".join(
                "%s/%s" % (u["menu"], u["item"] or "line %d" % u["line"]) for u in uses),
            "items": shown, "lines": txt.count("\n") + 1,
            "non_ascii": any(ord(c) > 127 for c in txt),
            "format": TEXT_QUIRKS + ("File is %d bytes of the %d byte limit." % (len(data), MENUDEF_BUF)),
        })
    unused = [os.path.basename(n) for n in all_files
              if n.lower() not in referenced and not is_credit_file(n)]
    report["text_files"] = {"exported": len(meta), "bytes_total": total, "missing": missing,
                            "englishusa_not_referenced_by_loaded_menus": unused,
                            "over_buffer": [m["file"] for m in meta if m["bytes"] >= MENUDEF_BUF],
                            "pool_fraction": round(total / float(STRING_POOL), 3)}
    return meta


# --- output --------------------------------------------------------------------

def esc_str(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def write_outputs(cat, meta, report):
    os.makedirs(os.path.join(OUT, "en"), exist_ok=True)
    entries = cat.finish()
    with open(os.path.join(OUT, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(OUT, "text_files.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
        f.write("\n")
    lines = ["// English identity catalog generated by tools/l10n/extract.py: copy to lang/<code>/strings.txt and",
             "// replace the right-hand side. Left side is the exact string handed to the draw function.", ""]
    for group, keys in cat.groups.items():
        lines.append("// ---- " + group)
        for k in keys:
            lines.append('"%s" "%s"' % (esc_str(k), esc_str(k)))
        lines.append("")
    with open(os.path.join(OUT, "en", "strings.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtcw", default=DEFAULT_RTCW, help="RTCW Main directory with the pk3 files")
    args = ap.parse_args()
    paks = Paks(args.rtcw)
    if "text/strings.txt" not in paks.files:
        sys.exit("RTCW paks not found in %s (use --rtcw)" % args.rtcw)
    os.makedirs(OUT, exist_ok=True)
    report = {}
    cat = Catalog()
    all_src = ""
    for d in ("cgame", "ui", "game"):
        for fn in sorted(os.listdir(os.path.join(SRC, d))):
            if fn.endswith(".c"):
                all_src += read_src("%s/%s" % (d, fn))
    textrefs = collect_menus(cat, paks, report)
    collect_strings_txt(cat, paks, report, all_src)
    collect_pickups(cat, paks, report)
    curated = collect_c_literals(cat, report)
    uncurated = scan_uncurated(curated)
    with open(os.path.join(OUT, "uncurated.txt"), "w", encoding="utf-8") as f:
        f.write("// sink calls with string literals that are neither catalogued nor on the ignore list; review by hand\n")
        f.write("\n".join(sorted(set(uncurated))) + "\n")
    meta = export_text_files(paks, textrefs, report)
    entries = write_outputs(cat, meta, report)
    words = sum(len(e["key"].split()) for e in entries)
    print("unique strings: %d, words: %d" % (len(entries), words))
    for k, v in cat.counts.items():
        print("  %-14s %d records" % (k, v))
    for g, keys in cat.groups.items():
        print("  group %-48s %d unique" % (g, len(keys)))
    print("uncurated sink literals: %d (build/uncurated.txt)" % len(set(uncurated)))
    print(json.dumps({k: v for k, v in report.items() if k != "menus_found"}, indent=1))


if __name__ == "__main__":
    main()
