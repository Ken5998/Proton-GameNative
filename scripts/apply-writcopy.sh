#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
[[ $# == 1 ]] || die 'Usage: apply-writcopy.sh WINE_DIR'
cd "$1"
git diff --check
python3 - <<'PY'
from pathlib import Path
import re
p = Path('dlls/ntdll/unix/virtual.c')
original = p.read_text()
# Anchor to the PE image-mapping function, its header_size protection call,
# and the following PE section loop. Fail closed if upstream restructures it.
functions = list(re.finditer(r'^static NTSTATUS map_image_into_view\(', original, re.M))
if len(functions) != 1:
    raise SystemExit('ERROR: Cannot uniquely identify map_image_into_view')
start = functions[0].start()
end = original.find('\n}\n', start)
if end == -1:
    raise SystemExit('ERROR: Cannot identify end of PE mapping function')
body = original[start:end]
pattern = re.compile(
    r'(/\* set the image protections \*/\s*'
    r'set_vprot\( view, ptr, ROUND_SIZE\( 0, header_size, align_mask \), )'
    r'VPROT_COMMITTED \| VPROT_READ'
    r'( \);\s*for \(i = 0; i < nt->FileHeader.NumberOfSections; i\+\+\))')
if len(list(pattern.finditer(body))) != 1 or 'map_pe_header(' not in body:
    raise SystemExit('ERROR: PE header protection is missing, ambiguous, or already changed')
body = pattern.sub(r'\g<1>VPROT_COMMITTED | VPROT_READ | VPROT_WRITECOPY\g<2>', body)
p.write_text(original[:start] + body + original[end:])
print('Enabled experimental WRITECOPY for PE headers in map_image_into_view only')
PY
git diff --check
