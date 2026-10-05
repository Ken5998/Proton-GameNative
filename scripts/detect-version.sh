#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ $# -ge 1 && $# -le 2 ]] || die 'Usage: detect-version.sh WINE_TAG [auto|VERSION]'
validate_ref "$1"
version=${2:-auto}
if [[ $version == auto ]]; then
    [[ $1 =~ ^proton-([0-9]+\.[0-9]+-[0-9]+)-([0-9]{8})$ ]] || die "Cannot derive version from '$1'; expected proton-MAJOR.MINOR-REV-YYYYMMDD or supply package_version"
    version=${BASH_REMATCH[1]}
    python3 - "${BASH_REMATCH[2]}" <<'PY'
import datetime, sys
try:
    datetime.datetime.strptime(sys.argv[1], '%Y%m%d')
except ValueError:
    sys.exit('ERROR: Invalid date in GameNative Wine tag')
PY
fi
validate_version "$version"
printf '%s\n' "$version"
