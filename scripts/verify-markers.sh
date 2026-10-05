#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ $# -ge 1 && $# -le 2 ]] || die 'Usage: verify-markers.sh WINE_DIR [--cached]'
cd "$1"
mode=()
if [[ ${2:-} == --cached ]]; then mode=(--cached); elif [[ -n ${2:-} ]]; then die 'Unknown mode'; fi
# Limit checks to real build inputs, never .git or android/patches.
markers=(WINEVMEMMAXSIZE MemoryWineLoadUnixLibByName MemoryWineLoadUnixLibByNameWow64 Wow64SuspendLocalThread arm64ec_suspend_point)
paths=(dlls/ntdll/unix/virtual.c dlls/ntdll/unix/virtual.c dlls/wow64/virtual.c dlls/wow64/syscall.c dlls/ntdll/ntdll_misc.h)
failed=0
for i in "${!markers[@]}"; do
    if [[ ${#mode[@]} -gt 0 ]]; then
        found=false
        git grep "${mode[@]}" -n -F "${markers[$i]}" -- "${paths[$i]}" && found=true
    else
        found=false
        grep -nH -F "${markers[$i]}" "${paths[$i]}" && found=true
    fi
    if [[ $found == false ]]; then
        printf 'FAIL: %s missing from %s\n' "${markers[$i]}" "${paths[$i]}" >&2
        failed=1
    fi
done
exit "$failed"
