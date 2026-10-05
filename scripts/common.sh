#!/usr/bin/env bash
# Shared input policy; never source generated metadata or user input.
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
validate_ref() {
    [[ ${#1} -le 200 && $1 =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ ]] || die "Unsafe ref: $1"
    git check-ref-format "refs/proton-gamenative/$1" >/dev/null || die "Invalid ref: $1"
}
validate_version() {
    [[ ${#1} -le 80 && $1 =~ ^[0-9][A-Za-z0-9._-]*$ && $1 != *..* ]] || die "Unsafe package version: $1"
}
validate_bool() { [[ $1 == true || $1 == false ]] || die "Expected true or false: $1"; }
package_name() { validate_version "$1"; printf 'Proton-GameNative-%s-arm64\n' "$1"; }
