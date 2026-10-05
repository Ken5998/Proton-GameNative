#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ $# == 4 ]] || die 'Usage: configure-build.sh PROTON_DIR BUILD_DIR VERSION LOG_DIR'
proton=$(cd "$1" && pwd)
validate_version "$3"
mkdir -p "$2" "$4"
build=$(cd "$2" && pwd)
logs=$(cd "$4" && pwd)
[[ $build != "$proton" && $build != "$proton/"* ]] || die 'Build directory must be outside Proton sources'
case $(uname -m) in aarch64|arm64) ;; *) die 'A native ARM64 host is required';; esac
[[ $(uname -s) == Linux ]] || die 'Build on native ARM64 Linux'
status=0
bash "$proton/configure.sh" --help > "$logs/configure-help.txt" 2>&1 || status=$?
cat "$logs/configure-help.txt"
# This upstream configure prints valid help with status 1.
[[ $status -le 1 ]] || die "configure --help failed ($status)"
for flag in --target-arch --build-name --container-engine; do
    grep -Fq -- "$flag" "$logs/configure-help.txt" || die "Unsupported configure flag: $flag"
done
if grep -Eq -- '--enable-ccache([[:space:]]|$)' "$logs/configure-help.txt"; then
    cache_flag=--enable-ccache
elif grep -Eq -- '--enable-cache([[:space:]]|$)' "$logs/configure-help.txt"; then
    cache_flag=--enable-cache
else
    die 'No supported ccache option advertised by selected Proton configure'
fi
cd "$build"
bash "$proton/configure.sh" --target-arch=arm64 "--build-name=Proton-GameNative $3 ARM64" --container-engine=docker "$cache_flag" 2>&1 | tee "$logs/configure.log"
sdk=$(make --silent get-steamrt-image)
printf '%s\n' "$sdk" > "$logs/sdk-image.txt"
docker image inspect --format '{{.Architecture}} {{json .RepoDigests}}' "$sdk" | tee "$logs/sdk-digest.txt"
[[ $(docker image inspect --format '{{.Architecture}}' "$sdk") == arm64 ]] || die 'SDK image is not native ARM64'
case $(docker run --rm --entrypoint uname "$sdk" -m) in aarch64|arm64) ;; *) die 'SDK is not executing natively on ARM64';; esac
