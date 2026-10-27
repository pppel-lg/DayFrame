"""Build a self-contained Windows x64 backend; all data stays outside this bundle."""
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != 'win32' or sys.maxsize <= 2**32:
        raise SystemExit('Build the Windows x64 sidecar on 64-bit Windows/Python.')
    import imageio_ffmpeg
    import PyInstaller
    frontend = ROOT / 'frontend' / 'dist'
    if not (frontend / 'index.html').is_file():
        raise SystemExit('Build the React frontend before the sidecar.')
    work = ROOT / 'artifacts' / 'sidecar-build'
    notices = work / 'licenses'
    notices.mkdir(parents=True, exist_ok=True)
    ffmpeg = Path(imageio_ffmpeg.get_ffmpeg_exe())
    ffmpeg_dir = work / 'bin'
    ffmpeg_dir.mkdir(exist_ok=True)
    shutil.copy2(ffmpeg, ffmpeg_dir / 'ffmpeg.exe')
    result = subprocess.run([str(ffmpeg), '-version'], capture_output=True, text=True, check=True)
    (notices / 'FFmpeg-build.txt').write_text(result.stdout + result.stderr, encoding='utf8')
    license_result = subprocess.run([str(ffmpeg), '-L'], capture_output=True, text=True, check=True)
    (notices / 'FFmpeg-license.txt').write_text(license_result.stdout + license_result.stderr, encoding='utf8')
    (notices / 'FFmpeg-source.txt').write_text(
        'Bundled from imageio-ffmpeg 0.6.0 wheel (imageio-binaries).\n'
        'Distribution and build recipes: https://github.com/imageio/imageio-binaries\n'
        'FFmpeg source releases: https://ffmpeg.org/releases/\n'
        'Exact compiled configuration: FFmpeg-build.txt. License: FFmpeg-license.txt.\n'
        'This build enables GPL components including libx264; it is not an LGPL-only binary.\n', encoding='utf8')
    inventory = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get('Name', 'unknown')
        if name.lower() in {'pip', 'setuptools', 'wheel', 'pytest', 'playwright', 'httpx'}:
            continue
        inventory.append({'name': name, 'version': distribution.version})
        for entry in distribution.files or []:
            if entry.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    destination = notices / name / str(entry).split('.dist-info/')[-1]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    (notices / 'python-packages.json').write_text(json.dumps(inventory, indent=2), encoding='utf8')
    shutil.copy2(ROOT / 'docs' / 'THIRD_PARTY.md', notices / 'THIRD_PARTY.md')
    dependency_notices = ROOT / 'artifacts/dependency-notices/licenses'
    if dependency_notices.exists():
        shutil.copytree(dependency_notices, notices, dirs_exist_ok=True)
    font_notice = ROOT / 'frontend/public/fonts/OFL.txt'
    if font_notice.exists():
        shutil.copy2(font_notice, notices / 'Noto-fonts-OFL.txt')
    for package in ['react', 'react-dom', 'scheduler', 'lucide-react', 'qrcode', '@fontsource/noto-sans-sc', '@fontsource/noto-serif-sc']:
        package_root = ROOT / 'frontend/node_modules' / package
        for source in package_root.rglob('*'):
            if source.is_file() and source.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE', 'OFL')):
                destination = notices / 'npm' / package / source.relative_to(package_root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    output = ROOT / 'src-tauri' / 'binaries'
    output.mkdir(parents=True, exist_ok=True)
    name = 'dayframe-server-x86_64-pc-windows-msvc'
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--console',
        '--name', name, '--distpath', str(output), '--workpath', str(work / 'work'), '--specpath', str(work),
        '--paths', str(ROOT), '--add-data', f'{frontend}{os.pathsep}frontend',
        '--add-data', f'{notices}{os.pathsep}licenses', '--add-binary', f'{ffmpeg_dir / "ffmpeg.exe"}{os.pathsep}bin',
        '--collect-all', 'pillow_heif', '--collect-submodules', 'uvicorn', '--collect-all', 'PIL',
        str(ROOT / 'scripts' / 'desktop-sidecar-entry.py')]
    subprocess.run(command, cwd=ROOT, check=True)
    binary = output / (name + '.exe')
    if not binary.is_file() or binary.stat().st_size == 0:
        raise SystemExit('Sidecar build produced no executable.')
    print(f'Packaged sidecar: {binary.name} ({binary.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
