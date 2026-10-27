"""Collect actual installed dependency notices; never synthesize license text.

Run after npm ci; --rust also requires a generated Cargo.lock and Cargo. Output
is consumed by build-sidecar.py. Metadata-only entries remain explicit review
items, not evidence that a license text or source-code obligation was satisfied.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts/dependency-notices/licenses'
NOTICE_NAME = re.compile(r'^(licen[cs]e|copying|copyright|notice|ofl|unlicense)', re.I)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def run_json(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding='utf-8', check=False)
    if result.returncode:
        raise RuntimeError(f'{command[0]} failed ({result.returncode}): {result.stderr[-6000:]}')
    return json.loads(result.stdout)


def notice_files(package_root, explicit_file=None):
    package_root = package_root.resolve()
    found = set()
    for directory, children, files in os.walk(package_root, followlinks=False):
        children[:] = sorted(name for name in children if name not in {'node_modules', '.git', 'target'})
        for name in sorted(files):
            source = Path(directory) / name
            if NOTICE_NAME.match(name):
                if source.is_symlink() or not source.resolve().is_relative_to(package_root):
                    raise ValueError(f'Notice escapes package directory: {source}')
                found.add(source)
    if explicit_file:
        source = package_root / explicit_file
        if not source.resolve().is_relative_to(package_root) or not source.is_file():
            raise ValueError(f'Declared license file is missing or outside its package: {source}')
        found.add(source)
    return sorted(found, key=lambda path: path.relative_to(package_root).as_posix())


def collect_package(ecosystem, package_root, identity, output):
    name, version = identity['name'], identity['version']
    if not name or not version:
        raise ValueError('Dependency identity has no name or version.')
    key = identity['source_id']
    folder = re.sub(r'[^a-zA-Z0-9._-]', '_', f'{name}-{version}')
    folder += '-' + hashlib.sha256(key.encode('utf-8')).hexdigest()[:10]
    destination = output / ecosystem / folder
    destination.mkdir(parents=True, exist_ok=True)
    manifest_name = 'package.json' if ecosystem == 'npm' else 'Cargo.toml'
    manifest = package_root / manifest_name
    if not manifest.is_file():
        raise ValueError(f'Installed dependency manifest is missing: {manifest}')
    shutil.copyfile(manifest, destination / manifest_name)
    files = []
    for source in notice_files(package_root, identity.get('license_file')):
        relative = source.relative_to(package_root).as_posix()
        target = destination / 'files' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files.append({'path': relative, 'sha256': digest(source), 'bytes': source.stat().st_size})
    declared = identity.get('declared_license')
    meaningful = declared and declared not in ('UNLICENSED', 'NONE', 'NOASSERTION')
    evidence = 'files-copied' if files else 'metadata-only' if meaningful else 'missing'
    record = {**identity, 'ecosystem': ecosystem, 'license_evidence': evidence,
              'manifest_sha256': digest(manifest), 'files': files,
              'notice_directory': f'{ecosystem}/{folder}'}
    write_json(destination / 'provenance.json', record)
    return record


def collect_npm(output):
    frontend = ROOT / 'frontend'
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        raise RuntimeError('npm is required; run npm ci --prefix frontend first.')
    tree = run_json([npm, 'ls', '--omit=dev', '--all', '--long', '--json'], frontend)
    packages = {}

    def visit(node):
        for dependency_name, dependency in sorted(node.get('dependencies', {}).items()):
            if dependency.get('missing') or dependency.get('invalid'):
                raise ValueError(f'Invalid installed npm runtime dependency: {dependency_name}')
            if not dependency.get('path'):
                raise ValueError(f'npm did not report an installed path for {dependency_name}')
            package_root = Path(dependency['path']).resolve()
            if not package_root.is_relative_to((frontend / 'node_modules').resolve()):
                raise ValueError(f'npm dependency is outside installed node_modules: {dependency_name}')
            relative = package_root.relative_to(ROOT).as_posix()
            if relative not in packages:
                manifest = json.loads((package_root / 'package.json').read_text(encoding='utf-8'))
                identity = {
                    'name': manifest['name'], 'version': manifest['version'],
                    'source_id': relative, 'installed_path': relative,
                    'declared_license': manifest.get('license', manifest.get('licenses')),
                    'repository': manifest.get('repository'), 'homepage': manifest.get('homepage'),
                    'resolved': dependency.get('resolved'), 'integrity': dependency.get('integrity'),
                }
                if dependency.get('version') != identity['version']:
                    raise ValueError(f'npm tree and installed version differ for {dependency_name}')
                packages[relative] = collect_package('npm', package_root, identity, output)
            visit(dependency)

    visit(tree)
    if not packages:
        raise ValueError('The installed npm production tree is empty.')
    records = sorted(packages.values(), key=lambda record: record['source_id'])
    write_json(output / 'npm/inventory.json', records)
    return records


def collect_rust(output):
    manifest = ROOT / 'src-tauri/Cargo.toml'
    metadata = run_json(['cargo', 'metadata', '--format-version', '1', '--locked',
                         '--filter-platform', 'x86_64-pc-windows-msvc', '--manifest-path', str(manifest)], ROOT)
    workspace = set(metadata['workspace_members'])
    records = []
    for package in sorted(metadata['packages'], key=lambda item: item['id']):
        if package['id'] in workspace:
            continue
        identity = {
            'name': package['name'], 'version': package['version'], 'source_id': package['id'],
            'declared_license': package.get('license'), 'license_file': package.get('license_file'),
            'source': package.get('source'), 'repository': package.get('repository'),
            'homepage': package.get('homepage'),
            'registry_page': f"https://crates.io/crates/{package['name']}/{package['version']}" if (package.get('source') or '').startswith('registry+') else None,
        }
        package_root = Path(package['manifest_path']).resolve().parent
        # Cargo may return an absolute license_file. Keep provenance portable.
        if identity['license_file']:
            license_path = Path(identity['license_file'])
            if license_path.is_absolute():
                identity['license_file'] = license_path.relative_to(package_root).as_posix()
        records.append(collect_package('rust', package_root, identity, output))
    if not records:
        raise ValueError('Cargo metadata contained no third-party packages.')
    write_json(output / 'rust/inventory.json', records)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rust', action='store_true', help='Include resolved Cargo crates (Cargo.lock required).')
    args = parser.parse_args()
    # Recreate only this generated directory, after checking its resolved boundary.
    resolved = OUTPUT.resolve()
    if not resolved.is_relative_to(ROOT.resolve() / 'artifacts') or resolved.name != 'licenses':
        raise ValueError('Refusing to replace notices outside the workspace artifacts directory.')
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    records = collect_npm(OUTPUT)
    if args.rust:
        records.extend(collect_rust(OUTPUT))
    metadata_only = [f"{record['ecosystem']}:{record['name']}@{record['version']}" for record in records if record['license_evidence'] == 'metadata-only']
    missing = [f"{record['ecosystem']}:{record['name']}@{record['version']}" for record in records if record['license_evidence'] == 'missing']
    inputs = {'frontend/package-lock.json': digest(ROOT / 'frontend/package-lock.json')}
    if args.rust:
        inputs['src-tauri/Cargo.lock'] = digest(ROOT / 'src-tauri/Cargo.lock')
    write_json(OUTPUT / 'collection.json', {
        'format_version': 1, 'inputs_sha256': inputs, 'packages': len(records),
        'npm_scope': 'Installed frontend production dependency tree; may include unused bundled packages.',
        'rust_scope': 'All packages reported by locked Windows-filtered Cargo metadata, excluding workspace members; includes build dependencies.' if args.rust else 'Not collected; rerun with --rust.',
        'metadata_only': metadata_only, 'missing_license_evidence': missing,
        'limitations': 'Actual source notice files and unchanged declared license metadata only. Compound SPDX expressions are preserved, not interpreted. Metadata-only entries need review; this collection does not certify license or corresponding-source compliance.',
    })
    print(f'Collected notices for {len(records)} packages in {OUTPUT.relative_to(ROOT)}')
    if metadata_only:
        print(f'Metadata-only review required ({len(metadata_only)}): ' + ', '.join(metadata_only))
    if missing:
        raise ValueError('No license files or declared license metadata: ' + ', '.join(missing))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f'Notice collection failed: {error}', file=sys.stderr)
        raise SystemExit(1)
