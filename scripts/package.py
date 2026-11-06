#!/usr/bin/env python3
"""Package the installed Linux runtime and its local game assets for personal use."""
import os
from pathlib import Path
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / 'run'
OUT = ROOT / 'build' / 'castle-operations-definitive-linux-x86_64.zip'
NAME = 'castle-operations-definitive'
VERSION = (ROOT / 'VERSION').read_text().strip()
REQUIRED = [
    'iowolfsp.x86_64', 'renderer_sp_rend2_x86_64.so',
    *(f'main/{name}' for name in ('pak0.pk3', 'sp_pak1.pk3', 'sp_pak2.pk3', 'sp_pak3.pk3', 'sp_pak4.pk3')),
    *(f'codmod/{name}.sp.x86_64.so' for name in ('cgame', 'qagame', 'ui')),
    *(f'codmod/{name}.cfg' for name in ('codmod', 'codmod_defaults', 'codmod_tuning', 'codmod_binds', 'codmod_gfxdefaults')),
    *(f'codmod/{name}.pk3' for name in ('codmod_menus', 'codmod_hud')),
]
LAUNCHER = '''#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/home"
cd "$ROOT"
exec ./iowolfsp.x86_64 +set fs_basepath "$ROOT" +set fs_homepath "$ROOT/home" \\
    +set vm_game 0 +set vm_cgame 0 +set vm_ui 0 +set sv_pure 0 +set logfile 2 \\
    +set fs_game codmod "$@"
'''
README = '''Castle Operations Definitive — Linux x86-64

Extract the entire folder, then run ./play.sh from a terminal. Saves and settings
are stored in the home/ folder alongside the game. Copy that folder separately if
you want to transfer your existing progress. The target needs compatible Linux
x86-64 libraries (including SDL2, OpenAL and OpenGL drivers); it does not need
Steam or the source repository. A newer build system's glibc can prevent the
binaries running on older Linux distributions.

This archive contains your original RTCW data and locally generated derivatives.
It is for your own use; do not distribute it. Optional enhancement packs are
included only when installed in the source runtime.
'''


def runtime_files():
    missing = [p for p in REQUIRED if not (RUN / p).is_file()]
    if missing:
        print('Missing installed runtime files; run scripts/setup.sh and scripts/build.sh --install:', file=sys.stderr)
        print('\n'.join(f'  run/{p}' for p in missing), file=sys.stderr)
        raise FileNotFoundError('Installed runtime is incomplete')
    marker = f'1.51d-SP-codv{VERSION}'.encode()
    if marker not in (RUN / 'iowolfsp.x86_64').read_bytes():
        print('Installed engine version does not match VERSION; run scripts/build.sh --install.', file=sys.stderr)
        raise FileNotFoundError('Installed engine version is stale')
    paths = {RUN / p for p in REQUIRED}
    # Only files the game loads: exclude backups, personal configs, saves and test artifacts.
    for folder in ('main', 'codmod'):
        paths.update(p for p in (RUN / folder).glob('*.pk3') if p.is_file())
    bench_cfg = RUN / 'codmod' / 'codmod_bench.cfg'
    if bench_cfg.is_file():
        paths.add(bench_cfg)
    demos = RUN / 'codmod' / 'demos'
    if demos.is_dir():
        paths.update(p for p in demos.rglob('*') if p.is_file())
    return sorted(paths)


def main():
    if len(sys.argv) != 1:
        print('Usage: scripts/package.py', file=sys.stderr)
        return 2
    try:
        paths = runtime_files()
    except FileNotFoundError:
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.package-', suffix='.zip', dir=OUT.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temp, 'w', allowZip64=True) as archive:
            for path in sorted(paths):
                print(f'Adding {path.relative_to(RUN)}', flush=True)
                # PK3s are already compressed. zipfile follows symlinks and writes their contents.
                compression = zipfile.ZIP_STORED if path.suffix == '.pk3' else zipfile.ZIP_DEFLATED
                archive.write(path, f'{NAME}/{path.relative_to(RUN).as_posix()}', compress_type=compression)
            for filename, content, mode in [('play.sh', LAUNCHER, 0o755), ('README.txt', f'Version: {VERSION}\n\n' + README, 0o644)]:
                info = zipfile.ZipInfo(f'{NAME}/{filename}')
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | mode) << 16
                archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED)
        os.replace(temp, OUT)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print(f'Created {OUT} ({OUT.stat().st_size / 1024**3:.2f} GiB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
