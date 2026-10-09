#!/usr/bin/env bash
# Builds box64-armada.tar.gz for armada-box64.sh: Box64 for ARM64 Linux (with Box32)
# plus the x86_64/i386 GCC runtime libraries that Wine's Unix side needs.
#
#   bash box64/build-bundle.sh [OUTPUT_DIR]        # default OUTPUT_DIR: ./out
#
# BOX64_REF picks the upstream tag (default: the version tested on ArmadaOS).
# Not on ARM64? Set CROSS_PREFIX=aarch64-linux-gnu- to cross-compile.
set -euo pipefail

ref="${BOX64_REF:-v0.4.3-3}"
out="$(realpath -m "${1:-out}")"
cross="${CROSS_PREFIX:-}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

git clone --quiet --depth 1 --branch "$ref" https://github.com/ptitSeb/box64 "$work/src"
commit="$(git -C "$work/src" rev-parse HEAD)"

cmake_args=(-DARM64=1 -DBOX32=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo)
case "$(uname -m)" in
    aarch64|arm64) ;;
    *)
        [[ -n $cross ]] || { echo 'Not on ARM64: set CROSS_PREFIX=aarch64-linux-gnu- to cross-compile.' >&2; exit 1; }
        cmake_args+=(-DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=aarch64 -DCMAKE_C_COMPILER="${cross}gcc")
        ;;
esac
cmake -S "$work/src" -B "$work/build" "${cmake_args[@]}"
cmake --build "$work/build" --target box64 -j "$(nproc)"

pkg="$work/box64-armada"
mkdir -p "$pkg/x64lib" "$pkg/x86lib"
install -m 755 "$work/build/box64" "$pkg/box64"
"${cross}strip" "$pkg/box64"
# The same libraries Box64's own install puts next to it; Wine's ntdll.so needs libgcc_s for unwinding.
for lib in libgcc_s.so.1 libstdc++.so.6; do
    install -m 644 "$work/src/x64lib/$lib" "$pkg/x64lib/$lib"
    install -m 644 "$work/src/x86lib/$lib" "$pkg/x86lib/$lib"
done
install -m 644 "$work/src/LICENSE" "$pkg/box64-LICENSE.txt"
# Per-process sections of the stock box64rc override BOX64_* variables, so none ship here.
printf '# Intentionally empty: settings come from BOX64_* variables (launch options).\n' > "$pkg/box64.box64rc"
cat > "$pkg/NOTICE.txt" <<EOF
Box64 ${ref} (commit ${commit}), https://github.com/ptitSeb/box64
Built with: ${cmake_args[*]}
License: MIT (box64-LICENSE.txt).
x64lib/ and x86lib/ hold the x86_64 and i386 GCC runtime libraries shipped in Box64's
source tree; they are GCC components under the GPL with the GCC Runtime Library Exception.
EOF

mkdir -p "$out"
tar -C "$work" --sort=name --owner=0 --group=0 --numeric-owner -czf "$out/box64-armada.tar.gz" box64-armada
(cd "$out" && sha256sum box64-armada.tar.gz > box64-armada.tar.gz.sha256)
cat "$pkg/NOTICE.txt"
echo "Wrote $out/box64-armada.tar.gz"
