#!/usr/bin/env bash
set -euo pipefail
printf 'Valve Proton branches and tags:\n'
git ls-remote --heads --tags https://github.com/ValveSoftware/Proton.git
printf '\nGameNative Wine tags:\n'
git ls-remote --tags https://github.com/GameNative/proton-wine.git
