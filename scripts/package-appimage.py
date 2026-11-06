#!/usr/bin/env python3
"""Build a private AppImage from the installed runtime using appimagetool."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from package import ROOT, RUN, VERSION, runtime_files

OUT = ROOT / 'build' / 'Castle-Operations-Definitive-x86_64.AppImage'
LAUNCHER = '''#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HOME_PATH="${RTCW_HOMEPATH:-${XDG_DATA_HOME:-$HOME/.local/share}/castle-operations-definitive}"
mkdir -p "$HOME_PATH"
cd "$ROOT/game"
exec ./iowolfsp.x86_64 +set fs_basepath "$ROOT/game" +set fs_homepath "$HOME_PATH" \\
    +set vm_game 0 +set vm_cgame 0 +set vm_ui 0 +set sv_pure 0 +set logfile 2 \\
    +set fs_game codmod "$@"
'''
DESKTOP = '''[Desktop Entry]
Type=Application
Name=Castle Operations Definitive
Exec=AppRun
Icon=castle-operations-definitive
Categories=Game;ActionGame;
Terminal=false
X-AppImage-Name=Castle Operations Definitive
X-AppImage-Version={version}
X-AppImage-Arch=x86_64
'''



def main():
    if len(sys.argv) != 1:
        print('Usage: scripts/package-appimage.py', file=sys.stderr)
        return 2
    tool = os.environ.get('APPIMAGETOOL') or shutil.which('appimagetool')
    if not tool:
        print('Install appimagetool or set APPIMAGETOOL to its executable path.', file=sys.stderr)
        return 1
    try:
        files = runtime_files()
    except FileNotFoundError:
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='appimage-', dir=OUT.parent))
    appdir = stage / 'game.AppDir'
    appdir.mkdir()
    try:
        for source in files:
            target = appdir / 'game' / source.relative_to(RUN)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Hard links save staging space; copying also supports data on another filesystem.
            try:
                os.link(source.resolve(strict=True), target)
            except OSError:
                shutil.copy2(source, target, follow_symlinks=True)
        (appdir / 'AppRun').write_text(LAUNCHER)
        (appdir / 'AppRun').chmod(0o755)
        (appdir / 'castle-operations-definitive.desktop').write_text(DESKTOP.format(version=VERSION))
        shutil.copy2(ROOT / 'iortcw' / 'SP' / 'misc' / 'wolf512.png',
                     appdir / 'castle-operations-definitive.png')
        env = os.environ.copy()
        env['ARCH'] = 'x86_64'
        env['VERSION'] = VERSION
        # The builder itself is often an AppImage and may be run without FUSE.
        env.setdefault('APPIMAGE_EXTRACT_AND_RUN', '1')
        temp_output = stage / OUT.name
        command = [tool]
        if os.environ.get('APPIMAGE_RUNTIME'):
            command += ['--runtime-file', os.environ['APPIMAGE_RUNTIME']]
        command += [str(appdir), str(temp_output)]
        subprocess.run(command, check=True, env=env)
        os.replace(temp_output, OUT)
        print(f'Created {OUT}')
    finally:
        # Keep staging recoverable; it is git-ignored and may be moved to trash.
        print(f'Staging files: {stage} (remove with trash when no longer needed)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
