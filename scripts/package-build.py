#!/usr/bin/env python3
"""Snapshot patched source before compilation; package a validated redist after it."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('mode', choices=['source', 'binary'])
p.add_argument('--version', required=True)
p.add_argument('--tree', required=True, type=Path)
p.add_argument('--metadata', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
p.add_argument('--sources', type=Path, help='Source archive directory (binary mode)')
a = p.parse_args()
if not re.fullmatch(r'[0-9][A-Za-z0-9._-]{0,79}', a.version) or '..' in a.version:
    p.error('Unsafe package version')
name = f'Proton-GameNative-{a.version}-arm64'
info = json.loads((a.metadata / 'build-info.json').read_text())
if info['Version'] != a.version or info['Package name'] != name:
    p.error('Metadata does not match package version/name')
epoch = int(info['Source date epoch'])
a.tree = a.tree.resolve(strict=True)
a.output.mkdir(parents=True, exist_ok=True)
a.output = a.output.resolve()
if a.output == a.tree or a.tree in a.output.parents:
    p.error('Output must be outside the source/payload tree')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def archive(path, entries):
    if path.exists() or Path(str(path) + '.sha256').exists():
        raise SystemExit(f'Refusing to overwrite {path}')

    def normalize(member):
        if any(part in {'.git', '__pycache__'} for part in Path(member.name).parts):
            return None
        member.uid = member.gid = 0
        member.uname = member.gname = 'root'
        member.mtime = epoch
        return member

    # Publish only complete archives; preserve file modes and symlinks.
    with tempfile.TemporaryDirectory(dir=a.output) as tmp:
        temp = Path(tmp) / path.name
        with temp.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=epoch) as gz:
            with tarfile.open(fileobj=gz, mode='w|', format=tarfile.PAX_FORMAT) as tar:
                for source, target in entries:
                    tar.add(source, arcname=target, filter=normalize)
        checksum = digest(temp)
        temp.rename(path)
        Path(str(path) + '.sha256').write_text(f'{checksum}  {path.name}\n')


if a.mode == 'source':
    if not (a.tree / 'COPYING.LIB').is_file() or not (a.tree / 'configure.ac').is_file():
        p.error('Not a Wine source tree with its license')
    root = Path(__file__).resolve().parent.parent
    top = name + '-source'
    entries = [(a.tree, top + '/wine'), (a.metadata / 'build-info.txt', top + '/build-info.txt')]
    # Include the build recipe as well as the exact patched source inputs.
    entries += [(root / item, top + '/build-system/' + item) for item in
                ['scripts', 'tests', '.github/workflows/build-arm64.yml', 'README.md', 'BUILDING.md', 'THIRD_PARTY_NOTICES.md', 'LICENSE']]
    archive(a.output / (top + '.tar.gz'), entries)
else:
    required = ['proton', 'compatibilitytool.vdf', 'toolmanifest.vdf', 'version', 'LICENSE',
                'files/bin-arm64/wine', 'files/bin-arm64/wineserver', 'files/share/wine/wine.inf']
    for item in required:
        if not (a.tree / item).is_file():
            p.error(f'Incomplete Proton redist: missing {item}')
    for item in ['files/lib/wine/aarch64-unix', 'files/lib/wine/aarch64-windows']:
        if not (a.tree / item).is_dir() or not any((a.tree / item).iterdir()):
            p.error(f'Missing or empty ARM64 payload: {item}')
    manifest = (a.tree / 'compatibilitytool.vdf').read_text()
    if not re.search(r'"display_name"\s+"' + re.escape(f'Proton-GameNative {a.version} ARM64') + '"', manifest):
        p.error('Unexpected Steam display name; check supported --build-name configuration')
    for item in ['files/bin-arm64/wine', 'files/bin-arm64/wineserver']:
        binary = a.tree / item
        description = subprocess.check_output(['file', '-L', str(binary)], text=True).strip()
        print(description)
        if 'ELF 64-bit' not in description or not re.search(r'ARM aarch64|ARM64', description):
            p.error(f'Expected an ARM64 ELF binary: {item}')
        if not binary.stat().st_mode & 0o111:
            p.error(f'Binary is not executable: {item}')
    if not a.sources:
        p.error('Corresponding source assets are required for every binary')
    source = a.sources / (name + '-source.tar.gz')
    checksum = Path(str(source) + '.sha256')
    if checksum.read_text().strip() != f'{digest(source)}  {source.name}':
        p.error('Source checksum mismatch')
    with tempfile.TemporaryDirectory(dir=a.output) as tmp:
        stage = Path(tmp) / name
        shutil.copytree(a.tree, stage, symlinks=True, copy_function=shutil.copy2)
        shutil.copy2(a.metadata / 'build-info.txt', stage / 'build-info.txt')
        archive(a.output / (name + '.tar.gz'), [(stage, name)])
    for asset in (source, checksum):
        destination = a.output / asset.name
        if destination.exists():
            raise SystemExit(f'Refusing to overwrite {destination}')
        shutil.copy2(asset, destination)
    shutil.copy2(a.metadata / 'build-info.txt', a.output / 'build-info.txt')
    print(f'Packaged {name} with corresponding Wine source and SHA256 checksums')
