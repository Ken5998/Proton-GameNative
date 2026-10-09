#!/usr/bin/env bash
# Runs an existing x86_64 Proton under Box64 instead of FEX on an ARM64 Linux device
# (tested on ArmadaOS). See box64/README.md.
#
#   bash box64/armada-box64.sh install GE-Proton10-34          # Box64 + "GE-Proton10-34 (Box64 WoW64)"
#   bash box64/armada-box64.sh install GE-Proton9-27 classic   # old 32-bit mode through Box32 (no 32-bit Vulkan)
#   bash box64/armada-box64.sh status
#   bash box64/armada-box64.sh cleanprefix 3066199280          # move ARM64 Proton leftovers out of a prefix
#   bash box64/armada-box64.sh uninstall
#
# Run it on the device, or from another computer with REMOTE=user@host (over ssh).
# install needs box64-armada.tar.gz (from box64/build-bundle.sh or the Box64 workflow)
# next to this script, or at the path given in BUNDLE.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
remote="${REMOTE:-}"
mode="${1:-status}"
arg="${2:-}"
extra="${3:-}"
dest='.local/share/box64-armada'

usage() { sed -n '5,9p' "$0" >&2; exit 2; }
case "$mode" in
    install) [[ $arg =~ ^[A-Za-z0-9._()\ -]+$ && ( -z $extra || $extra == classic ) ]] || usage ;;
    cleanprefix) [[ $arg =~ ^[0-9]+(-[A-Za-z0-9]+)?$ ]] || usage ;;
    status|uninstall) ;;
    *) usage ;;
esac

# Runs a shell command line on the device: locally, or over ssh when REMOTE is set.
on_device() {
    if [[ -n $remote ]]; then
        ssh -o StrictHostKeyChecking=yes "$remote" "$1"
    else
        sh -c "$1"
    fi
}

if [[ $mode == install ]]; then
    bundle="${BUNDLE:-$here/box64-armada.tar.gz}"
    [[ -f $bundle ]] || { echo "Missing $bundle: build it with box64/build-bundle.sh or download it from the Box64 workflow." >&2; exit 1; }
    # Box64 and its x86_64/i386 runtime libraries go to ~/.local/share/box64-armada.
    on_device "mkdir -p ~/$dest && tar xzf - -C ~/$dest --strip-components=1" < "$bundle"
fi

args=("$mode")
[[ -n $arg ]] && args+=("$arg")
[[ -n $extra ]] && args+=("$extra")
# %q keeps names such as "Proton 10.0" in one piece through the remote shell.
on_device "python3 - $(printf '%q ' "${args[@]}")" < "$here/armada_box64.py"
