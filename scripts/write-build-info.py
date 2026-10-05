#!/usr/bin/env python3
"""Record only explicit public provenance fields; never dump the environment."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument('proton', type=Path)
p.add_argument('output', type=Path)
p.add_argument('version')
p.add_argument('profile', choices=['gamenative-fex-linux'])
p.add_argument('writcopy', choices=['true', 'false'])
a = p.parse_args()


def git(tree, *args):
    return subprocess.check_output(['git', '-C', str(tree), *args], text=True).strip()


root = Path(__file__).resolve().parent.parent
patches = (root / 'scripts/patch-profiles' / (a.profile + '.txt')).read_text().splitlines()
patches = [v for v in patches if v and not v.startswith('#')]
info = {
    'Project': 'Proton-GameNative',
    'Project repository': os.environ['GITHUB_SERVER_URL'] + '/' + os.environ['GITHUB_REPOSITORY'],
    'Project commit': os.environ['GITHUB_SHA'],
    'Version': a.version,
    'Package name': f'Proton-GameNative-{a.version}-arm64',
    'Valve Proton repository': 'https://github.com/ValveSoftware/Proton.git',
    'Proton requested ref': os.environ['PROTON_REF'],
    'Proton resolved commit': git(a.proton, 'rev-parse', 'HEAD'),
    'GameNative Wine repository': 'https://github.com/GameNative/proton-wine.git',
    'GameNative Wine requested tag': os.environ['WINE_TAG'],
    'GameNative Wine resolved commit': git(a.proton / 'wine', 'rev-parse', 'HEAD'),
    'Patch profile': a.profile,
    'WRITECOPY enabled': a.writcopy,
    'GitHub run ID': os.environ['GITHUB_RUN_ID'],
    'GitHub run number': os.environ['GITHUB_RUN_NUMBER'],
    'GitHub run attempt': os.environ.get('GITHUB_RUN_ATTEMPT', '1'),
    'GitHub workflow ref': os.environ.get('GITHUB_WORKFLOW_REF', ''),
    'Runner architecture': os.uname().machine,
    'Runner OS': os.environ.get('RUNNER_OS', os.uname().sysname),
    'UTC build date': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'Source date epoch': git(a.proton / 'wine', 'show', '-s', '--format=%ct', 'HEAD'),
    'Full ordered patch list': patches,
    'Patch SHA256': {v: hashlib.sha256((a.proton / 'wine' / v).read_bytes()).hexdigest() for v in patches},
    'Proton submodule commits': git(a.proton, 'submodule', 'status', '--recursive').splitlines(),
}
a.output.mkdir(parents=True, exist_ok=True)
(a.output / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
with (a.output / 'build-info.txt').open('w') as f:
    for key, value in info.items():
        f.write(f'{key}: ')
        if isinstance(value, (dict, list)):
            f.write('\n')
            rows = [f'{k}: {v}' for k, v in value.items()] if isinstance(value, dict) else value
            f.writelines(f'  {row}\n' for row in rows)
        else:
            f.write(str(value) + '\n')
