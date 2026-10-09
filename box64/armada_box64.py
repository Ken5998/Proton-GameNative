#!/usr/bin/env python3
"""Device-side half of armada-box64.sh: runs on the ARM64 Linux device itself.

Creates Steam compatibility tools that run an existing x86_64 Proton under Box64
instead of FEX, without modifying that Proton:

  armada_box64.py install PROTON [classic]   create "<PROTON> (Box64 WoW64)" (or "(Box64)")
  armada_box64.py status                     show Box64 and the tools created
  armada_box64.py cleanprefix APPID          move ARM64 Proton leftovers out of a prefix
  armada_box64.py uninstall                  remove the tools and Box64

Box64 itself must already be unpacked in ~/.local/share/box64-armada
(armada-box64.sh does that from box64-armada.tar.gz).
"""
import os
import re
import shutil
import subprocess
import sys
import time

DEST = '.local/share/box64-armada'
MARKER = '.box64-shadow'

# Defaults exported by every generated tool. Values already set in the Steam
# launch options win, so per-game Box64 settings need no reinstall.
BASE_ENV = {
    # Box64 0.4.3 caches translated code in ~/.cache/box64; a stale cache made
    # wineboot crash at startup on ArmadaOS.
    'BOX64_DYNACACHE': '0',
    # Wine's NTSync waits fault under Box64 (ntdll inproc_wait), which kills
    # Wine's XInput thread and with it all gamepad input.
    'PROTON_NO_NTSYNC': '1',
}


def paths():
    home = os.path.expanduser('~')
    steam = f'{home}/.local/share/Steam'
    box64_dir = f'{home}/{DEST}'
    return {
        'steam': steam,
        'tools': f'{steam}/compatibilitytools.d',
        'compat': f'{steam}/steamapps/compatdata',
        'box64_dir': box64_dir,
        'box64': f'{box64_dir}/box64',
        'rcfile': f'{box64_dir}/box64.box64rc',
    }


def shadows(p):
    if not os.path.isdir(p['tools']):
        return []
    return sorted(d for d in os.listdir(p['tools']) if os.path.isfile(os.path.join(p['tools'], d, MARKER)))


def box64_version(p):
    if not os.access(p['box64'], os.X_OK):
        return None
    out = subprocess.run([p['box64'], '--version'], capture_output=True, text=True)
    text = (out.stdout or out.stderr).strip()
    return text.splitlines()[0] if out.returncode == 0 and text else None


def wine_running():
    return subprocess.run(['pgrep', '-f', 'wineserver'], stdout=subprocess.DEVNULL).returncode == 0


def is_elf(path):
    try:
        with open(path, 'rb') as f:
            return f.read(4) == b'\x7fELF'
    except OSError:
        return False


def write(path, text, executable=False):
    with open(path, 'w') as f:
        f.write(text)
    if executable:
        os.chmod(path, 0o755)


def sh_quote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def find_proton(p, name):
    for base in (p['tools'], f"{p['steam']}/steamapps/common"):
        path = os.path.join(base, name)
        if os.path.isfile(os.path.join(path, 'proton')) and not os.path.isfile(os.path.join(path, MARKER)):
            return path
    sys.exit(f'Proton "{name}" not found in compatibilitytools.d or steamapps/common')


def status(p):
    print('Box64:', box64_version(p) or 'not installed')
    print('Box64 Proton tools:', ', '.join(shadows(p)) or 'none')


def install(p, tool, flavor):
    if wine_running():
        sys.exit('Wine is still running: close the game (and wait a few seconds) first.')
    if not os.path.isfile(p['box64']):
        sys.exit(f"Box64 not found at {p['box64']}: unpack box64-armada.tar.gz there first.")
    os.chmod(p['box64'], 0o755)
    version = box64_version(p)
    if not version:
        check = subprocess.run([p['box64'], '--version'], capture_output=True, text=True)
        sys.exit(f'Box64 does not run on this system:\n{check.stdout}{check.stderr}')
    print('Box64:', version)

    src = find_proton(p, tool)
    supports_wow64 = 'PROTON_USE_WOW64' in open(os.path.join(src, 'proton'), errors='replace').read()
    if flavor == 'wow64' and not supports_wow64:
        print(f'{os.path.basename(src)} has no PROTON_USE_WOW64 support: using the classic 32-bit mode.\n'
              'Note: Box32 has no Vulkan, so 32-bit games using DXVK will not start in this mode.')
        flavor = 'classic'
    wow64 = flavor == 'wow64'

    name = re.sub(r'[^A-Za-z0-9._-]+', '-', tool).strip('-') + ('-box64-wow64' if wow64 else '-box64')
    dst = os.path.join(p['tools'], name)
    if os.path.lexists(dst):
        if not os.path.isfile(os.path.join(dst, MARKER)):
            sys.exit(f'{dst} exists and was not created by armada-box64; not touching it')
        shutil.rmtree(dst)
    os.makedirs(dst)
    write(os.path.join(dst, MARKER), f'Created by armada-box64 from {src}\n')

    for entry in os.listdir(src):
        if entry not in ('files', 'proton', 'compatibilitytool.vdf', 'toolmanifest.vdf'):
            os.symlink(os.path.join(src, entry), os.path.join(dst, entry))

    # Proton finds its files next to sys.argv[0], so a copy of the script here uses the wrapped bin/ below.
    shutil.copy2(os.path.join(src, 'proton'), os.path.join(dst, 'proton.py'))
    env = dict(BASE_ENV, **({'PROTON_USE_WOW64': '1'} if wow64 else {}))
    exports = ''.join(f'export {k}="${{{k}:-{v}}}"\n' for k, v in env.items())
    write(os.path.join(dst, 'proton'), f'''#!/bin/sh
# Runs {os.path.basename(src)} with Box64 instead of FEX (created by armada-box64).
here=$(dirname "$(readlink -f "$0")")
# HODLL selects an ARM64 Proton's 32-bit emulator DLL; it must not leak into an x86_64 Wine.
unset HODLL
export BOX64_RCFILE={sh_quote(p['rcfile'])}
export BOX64_LD_LIBRARY_PATH={sh_quote(p['box64_dir'] + '/x64lib:' + p['box64_dir'] + '/x86lib')}
{exports}exec python3 "$here/proton.py" "$@"
''', executable=True)

    # Every bin* folder (bin, and bin-wow64 in newer Protons) gets Box64 wrappers; the rest is linked.
    os.makedirs(os.path.join(dst, 'files'))
    wrapped = []
    for entry in sorted(os.listdir(os.path.join(src, 'files'))):
        real_dir = os.path.join(src, 'files', entry)
        if not (entry.startswith('bin') and os.path.isdir(real_dir) and not os.path.islink(real_dir)):
            os.symlink(real_dir, os.path.join(dst, 'files', entry))
            continue
        os.makedirs(os.path.join(dst, 'files', entry))
        for item in sorted(os.listdir(real_dir)):
            real = os.path.join(real_dir, item)
            link = os.path.join(dst, 'files', entry, item)
            if os.path.isfile(real) and is_elf(real):
                # Box64 then runs every x86 program Wine starts (wineserver, loaders) by itself.
                write(link, f'#!/bin/sh\nexec {sh_quote(p["box64"])} {sh_quote(real)} "$@"\n', executable=True)
                wrapped.append(f'{entry}/{item}')
            else:
                os.symlink(real, link)

    display = f'{os.path.basename(src)} (Box64{" WoW64" if wow64 else ""})'
    write(os.path.join(dst, 'compatibilitytool.vdf'), f'''"compatibilitytools"
{{
  "compat_tools"
  {{
    "{name}"
    {{
      "install_path" "."
      "display_name" "{display}"
      "from_oslist" "windows"
      "to_oslist" "linux"
    }}
  }}
}}
''')
    # No Steam Linux Runtime: that container is x86_64 and would run everything under FEX again.
    manifest = os.path.join(src, 'toolmanifest.vdf')
    lines = open(manifest).read().splitlines() if os.path.isfile(manifest) else \
        ['"manifest"', '{', '  "version" "2"', '  "commandline" "/proton %verb%"', '}']
    lines = [line for line in lines if not re.search(r'"(require_tool_appid|compatmanager_layer_name)"', line)]
    write(os.path.join(dst, 'toolmanifest.vdf'), '\n'.join(lines) + '\n')
    print(f'Created {display} in {dst}')
    print('Wrapped with Box64:', ', '.join(wrapped))
    print(f'\nRestart Steam, then pick "{display}" in a game\'s Properties > Compatibility.')


ARM_MACHINES = {0xaa64: 'ARM64', 0xa641: 'ARM64EC', 0x01c4: 'ARMNT', 0xa64e: 'ARM64X'}


def pe_machine(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(4096)
        off = int.from_bytes(head[0x3c:0x40], 'little')
        if head[:2] != b'MZ' or head[off:off + 4] != b'PE\0\0':
            return None
        return int.from_bytes(head[off + 4:off + 6], 'little')
    except (OSError, ValueError):
        return None


def cleanprefix(p, appid):
    """A prefix first created by an ARM64 Proton keeps ARM64 DLLs and Wow64 registry keys
    that make x86_64 Wine fail with c000007b. Moves them aside; nothing is deleted."""
    if not re.fullmatch(r'[0-9]+(-[A-Za-z0-9]+)?', appid):
        sys.exit(f'Invalid app id: {appid}')
    pfx = f"{p['compat']}/{appid}/pfx"
    if not os.path.isdir(pfx):
        sys.exit(f'No prefix at {pfx}')
    if wine_running():
        sys.exit('Wine is still running: close the game (and wait a few seconds) first.')
    keep = os.path.join(pfx, f'arm64-leftovers-{time.strftime("%Y%m%d-%H%M%S")}')
    moved = 0
    for sub in ('system32', 'syswow64'):
        base = os.path.join(pfx, 'drive_c', 'windows', sub)
        if not os.path.isdir(base):
            continue
        for entry in sorted(os.listdir(base)):
            path = os.path.join(base, entry)
            why = None
            if os.path.islink(path) and re.search(r'aarch64|arm64', os.readlink(path)):
                why = 'link to ' + os.readlink(path)
            elif os.path.isfile(path) and not os.path.islink(path) and pe_machine(path) in ARM_MACHINES:
                why = ARM_MACHINES[pe_machine(path)]
            if why:
                os.makedirs(os.path.join(keep, sub), exist_ok=True)
                os.replace(path, os.path.join(keep, sub, entry))
                print(f'Moved {sub}/{entry} ({why})')
                moved += 1
    reg = os.path.join(pfx, 'system.reg')
    removed = []
    if os.path.isfile(reg):
        out, skip = [], False
        for line in open(reg, encoding='utf-8', errors='surrogateescape').read().split('\n'):
            if line.startswith('['):
                skip = bool(re.match(r'^\[Software\\\\(Wow6432Node\\\\)?Microsoft\\\\Wow64(\\\\|\])', line, re.I))
                if skip:
                    removed.append(line.split(']')[0] + ']')
            if not skip:
                out.append(line)
        if removed:
            os.makedirs(keep, exist_ok=True)
            shutil.copy2(reg, os.path.join(keep, 'system.reg'))
            with open(reg + '.tmp', 'w', encoding='utf-8', errors='surrogateescape') as f:
                f.write('\n'.join(out))
            os.replace(reg + '.tmp', reg)
            for key in removed:
                print(f'Removed registry key {key}')
    print(f'Originals kept in {keep}' if moved or removed else 'Nothing ARM64-specific found in the prefix.')


def uninstall(p):
    for d in shadows(p):
        shutil.rmtree(os.path.join(p['tools'], d))
        print(f'Removed {d}')
    if os.path.isdir(p['box64_dir']):
        shutil.rmtree(p['box64_dir'])
        print(f"Removed {p['box64_dir']}")


def main(argv):
    # ssh drops empty arguments, so optional ones may simply be missing.
    mode, arg, extra = (argv + ['', ''])[:3]
    p = paths()
    if mode == 'install' and arg:
        install(p, arg, 'classic' if extra == 'classic' else 'wow64')
    elif mode == 'status':
        status(p)
    elif mode == 'cleanprefix' and arg:
        cleanprefix(p, arg)
    elif mode == 'uninstall':
        uninstall(p)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
