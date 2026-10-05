#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ $# == 3 ]] || die 'Usage: fetch-sources.sh WORK_DIR PROTON_REF WINE_TAG'
validate_ref "$2"
validate_ref "$3"
mkdir -p "$1"
work=$(cd "$1" && pwd)
[[ ! -e $work/Proton ]] || die 'Use a fresh work directory'
git init "$work/Proton"
cd "$work/Proton"
git remote add origin https://github.com/ValveSoftware/Proton.git
# Full reachable history and tags, including when input is a commit SHA.
git fetch --tags origin "$2"
git checkout --detach FETCH_HEAD
printf 'Requested Proton ref: %s\nResolved Proton commit: %s\n' "$2" "$(git rev-parse HEAD)"
git submodule update --init --recursive --jobs 4
cd wine
git remote add gamenative https://github.com/GameNative/proton-wine.git
git fetch --no-tags gamenative "refs/tags/$3"
git checkout --detach FETCH_HEAD
commit=$(git rev-parse HEAD)
printf 'Requested GameNative Wine tag: %s\nResolved Wine commit: %s\n' "$3" "$commit"
# The initial provenance assertion is deliberately scoped to this single tag.
if [[ $3 == proton-11.0-2-20260928 && $commit != 555aa70* ]]; then
    die 'Default GameNative tag no longer resolves to expected 555aa70 lineage'
fi
git submodule update --init --recursive --jobs 4
# Never run Proton submodule update again: it would reset this Wine selection.
