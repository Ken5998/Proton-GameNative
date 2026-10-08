#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$script_dir/common.sh"
[[ $# == 1 ]] || die 'Usage: apply-mono-arm64.sh WINE_DIR'
wine=$(cd "$1" && pwd)
patch="$script_dir/../patches/wine-mono-aarch64.patch"
cd "$wine"
git apply --check "$patch" || die 'Wine Mono ARM64 fix no longer applies; review upstream metahost.c'
git apply "$patch"
git diff --check
grep -Fq "#elif defined(__aarch64__)" dlls/mscoree/metahost.c || die 'ARM64 Mono selector missing'
grep -Fq "'a','r','m','6','4'" dlls/mscoree/metahost.c || die 'ARM64 Mono DLL name missing'
printf '%s\n' 'Applied ARM64 Wine Mono DLL selection fix'
