#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$script_dir/common.sh"
check_only=false
if [[ ${1:-} == --check-only ]]; then check_only=true; shift; fi
[[ $# == 2 ]] || die 'Usage: apply-gamenative-fex-linux.sh [--check-only] WINE_DIR LOG_DIR'
wine=$(cd "$1" && pwd)
mkdir -p "$2"
logs=$(cd "$2" && pwd)
[[ $logs != "$wine" && $logs != "$wine/"* ]] || die 'LOG_DIR must be outside the Wine checkout'
cd "$wine"
[[ -z $(git status --porcelain --untracked-files=all) ]] || die 'Wine checkout must be clean; refusing to overwrite changes'
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
# Simulate the ordered stack in an isolated index: neither the real index nor
# any source file changes until every patch and the complete result validate.
export GIT_INDEX_FILE="$scratch/index"
git read-tree HEAD
failures=()
patches=()
while IFS= read -r patch; do
    [[ -n $patch && $patch != \#* ]] || continue
    patches+=("$patch")
    log="$logs/$(printf '%s' "$patch" | tr / _).log"
    printf 'CHECK %s: ' "$patch"
    if [[ ! -f $patch ]]; then
        printf 'Missing patch: %s\n' "$patch" > "$log"
        failures+=("$patch")
    elif git apply --cached --check "$patch" > "$log" 2>&1 && git apply --cached "$patch" >> "$log" 2>&1; then
        printf 'OK\n'
        continue
    else
        failures+=("$patch")
    fi
    printf 'FAIL\n'
    cat "$log" >&2
done < "$script_dir/patch-profiles/gamenative-fex-linux.txt"
if [[ ${#failures[@]} -ne 0 ]]; then
    printf 'Failed patches (Wine tree unchanged):\n' >&2
    printf '  %s\n' "${failures[@]}" >&2
    exit 1
fi
git diff --cached --check
bash "$script_dir/verify-markers.sh" "$wine" --cached | tee "$logs/staged-markers.log"
git diff --cached --binary > "$scratch/profile.patch"
unset GIT_INDEX_FILE
git apply --check "$scratch/profile.patch"
if [[ $check_only == true ]]; then
    printf 'All %s patches validated; Wine tree unchanged.\n' "${#patches[@]}"
    exit 0
fi
# One git apply is atomic for validation failures; no --reject or conflict repair.
git apply "$scratch/profile.patch"
git diff --check
git diff --stat | tee "$logs/patch-stat.txt"
bash "$script_dir/verify-markers.sh" "$wine" | tee "$logs/applied-markers.log"
printf '%s\n' "${patches[@]}" > "$logs/applied-patches.txt"
