# Building Proton-GameNative

## Architecture and source selection

The sole build trigger is `workflow_dispatch` in
[build-arm64.yml](.github/workflows/build-arm64.yml). Build and release jobs use
`ubuntu-24.04-arm`. Preflight prints system, CPU, memory, and disk information and
rejects any architecture other than `aarch64` / `arm64`. Configuration separately
requires Linux, checks the SDK image architecture and container `uname -m`, and
uses Docker. There is no QEMU setup or emulated compilation.

Workflow string inputs enter shell scripts through environment variables, never
through shell-code interpolation. Refs use a restricted character set plus Git
ref validation; package versions are bounded filename-safe identifiers beginning
with a digit. Repository URLs are fixed to ValveSoftware/Proton and
GameNative/proton-wine. No user-supplied URL, `eval`, or generated shell metadata
is executed.

`fetch-sources.sh` creates `work/Proton`, fetches the requested Proton ref and tags
with reachable history, resolves a detached commit, and initializes recursive
submodules without shallow submodule restrictions. Inside the Wine submodule it
adds a local GameNative remote, fetches `refs/tags/<gamenative_wine_tag>`, and checks
out that exact detached commit. It never edits `.gitmodules` or pushes upstream.
Do not run Proton's submodule update again afterward: that would restore Valve's
Wine gitlink instead of the selected GameNative source.

For the initial tag only, the Wine commit must begin with `555aa70`. This
assertion is centralized in `fetch-sources.sh`, and does not constrain future tags.
Changing a default is a workflow change; scripts do not embed package versions.

Initial inspection on 2026-10-05 resolved:

| Input | Resolved commit |
| --- | --- |
| Proton `experimental_11.0` | `70b7e109e8fc0783a509805f3d1bc090b55dac3f` |
| Wine `proton-11.0-2-20260928` | `555aa70febb7d36e82d96697b554ff8f4fe0bb1a` |

A branch moves. For repeatable source selection use the recorded full Proton
SHA; retain the Wine source archive, Wine SHA, project commit, submodule list,
patch hashes, and SDK image digest from each run. This pipeline records inputs
for reproduction; it does not claim bit-for-bit reproducibility across changing
SDK tags, downloaded dependencies, runners, timestamps, or toolchains.

## Patch profile and validation

GameNative's [ARM64EC build script](https://github.com/GameNative/proton-wine/blob/proton-11.0-2-20260928/build-scripts/build-step-arm64ec.sh)
applies patches during its Android build. A checkout alone is insufficient.
Our script uses only the ordered 15-file allowlist in
[gamenative-fex-linux.txt](scripts/patch-profiles/gamenative-fex-linux.txt).
The groups cover address-space/FEX support, the ARM64EC loader, unixlib/WOW64
bridging, and thread suspension/exception/process handling.

The transaction requires a clean Wine tree. Every patch is checked with
`git apply --cached --check` against an isolated temporary index; passing patches
are simulated in that index in order. Thus dependent patches can be validated
without changing any source file or the real index. Missing/incompatible patches
are logged individually and collected before failure. The complete staged result
must pass `git diff --cached --check` and marker verification. Only then is the
combined result applied to the real tree with one `git apply`, followed by
`git diff --check`, `git diff --stat`, and source marker checks. There is no
`--reject`, fuzzy conflict repair, silently skipped patch, or automatic reset.

Run validation without applying:

```bash
bash scripts/apply-gamenative-fex-linux.sh --check-only /path/to/wine /tmp/patch-checks
```

The initial 15 complete upstream patches pass validation at the recorded Wine
commit. Selected files contain mixed hunks: Android preprocessor guards are
inactive on glibc; the virtual-memory patch also changes anonymous PE mappings;
the unix loader adds an optional `$PREFIX/lib/wine` fallback. These shared changes
are retained as part of the explicitly selected upstream patches and need runtime
testing. No Android networking, clipboard, URL intents, PulseAudio, X11/UI,
sysvshm, ntsync-android backend, locale, or shell-path patch is selected. The
guarded `ntsync_userspace` declaration in a selected header does not import that
backend. Do not run GameNative's complete Android build script in this pipeline.

Marker checks read explicit real `.c`/`.h` build inputs, excluding `.git` and
`android/patches`: `WINEVMEMMAXSIZE`, `MemoryWineLoadUnixLibByName`,
`MemoryWineLoadUnixLibByNameWow64`, `Wow64SuspendLocalThread`, and
`arm64ec_suspend_point`. Checks run before compilation and again on Proton's
`work/build/src-wine` copy afterward. In this tag, `Wow64SuspendLocalThread`
already has an implementation; `arm64ec_suspend_point` is only an upstream-added
header declaration. Marker checks establish source presence, not that every
marker is a new implementation, an exported binary symbol, or exercised at runtime.

WRITECOPY is disabled by default. `apply-writcopy.sh` requires a unique
`map_image_into_view` function, PE-header mapping, and the header-protection call
between the image-protection comment and PE section loop. It changes only that
call from `VPROT_COMMITTED | VPROT_READ` to additionally include
`VPROT_WRITECOPY`. Ambiguous, missing, or already-modified code fails closed.

To add a profile, create a reviewed ordered manifest and application entry point,
then extend the workflow choice/dispatch, metadata choices, verification, and
tests deliberately. Do not broaden the current allowlist automatically.

## Version parsing

`detect-version.sh` recognizes `proton-MAJOR.MINOR-REV-YYYYMMDD`, validates the
calendar date, and extracts the captured version rather than fixed positions.
For example, `proton-11.0-2-20260928` becomes `11.0-2` and
`proton-12.0-1-20270115` becomes `12.0-1`. An explicit `package_version` bypasses
automatic extraction but must still pass filename validation.

## SDK, cache, disk space, and compilation

The out-of-tree build directory is `work/build`. The selected Proton's actual
`configure.sh --help` determines whether `--enable-ccache` or the historical
`--enable-cache` is supported. A valid help response with status 1 is accepted
because the inspected configure script uses that status even for `--help`.
Required flags must be advertised. Configuration uses:

```text
--target-arch=arm64
--build-name="Proton-GameNative <version> ARM64"
--container-engine=docker
<detected ccache flag>
```

The SDK image is selected by upstream Proton, not an outdated image hard-coded
here. Configuration pulls/tests it; its name, ARM64 architecture, and digest are
recorded. Valve's supported build-name substitution sets the Steam display name
and internal tool name. Packaging validates the result without editing VDF files.

GitHub caches only `work/ccache`, limited to 2 GiB through both config and
`CCACHE_MAXSIZE`. Keys contain runner architecture, a hash of the Proton ref,
and the run/attempt. Restore keys allow reuse for small Wine changes on the same
Proton ref; ccache's compiler/content keys determine valid hits. The entire build
tree and Docker layers are never cached.

Disk checks are isolated in workflow steps. `df -h` is retained at preflight,
after source checkout, after SDK preparation, before/after compilation, and after
packaging. The initial 12 GiB free-space floor is only an obvious-shortage guard;
it is **not** a measured estimate of peak build space. A full recursive checkout,
SDK, debug build products, source archive, and temporary copy of redist may need
substantially more space. Packaging also requires room for compressed archives.
No runner files or preinstalled SDKs are removed. If a run exhausts disk, inspect
`disk-space.log`, `du` totals, and `docker system df` first, then revise the guard
or documented storage provisioning. Do not switch architecture or rerun blindly.

The build runs `make redist 2>&1 | tee build.log` with pipefail and explicit
pipeline exit-status capture, including a failed `tee`. On failure it prints the
last 200 lines and the last matching errors in reverse order. Available checkout,
patch, version, configure, source-change, build, and disk diagnostics are always
uploaded. A failed build never reaches binary packaging or release publication.

## Packaging and releases

Before compilation, `package-build.sh source` streams the patched Wine input tree
into `Proton-GameNative-<version>-arm64-source.tar.gz`, preserving licensing files
and excluding `.git` entries at every depth. It includes `build-info.txt` and this
project's build recipe. This is the input source tree; Proton's separately copied
and generated build products are not substituted for it. Source checksums are
verified again before binary packaging and publication.

After success, the packager checks the launcher, manifests, version, LICENSE,
Wine data, ARM64 library trees, executable modes, and representative ARM64 ELF
binaries with `file`. The complete redist is copied with symlinks and modes into
one temporary `Proton-GameNative-<version>-arm64/` directory. It adds provenance,
then creates `.tar.gz` and `.tar.gz.sha256`. Tar owner/group and timestamps are
normalized, but upstream build output itself is not promised byte-identical.
All upstream redist license, copying, and patent files remain untouched.

The build job has `contents: read` and does not persist checkout credentials.
Only the conditional release job gets `contents: write`; it executes no upstream
source code. It verifies checksums and rejects existing tags before creating a
prerelease named `Proton-GameNative <version> ARM64`, with tag
`<version>-arm64-r<run_number>-a<attempt>`. The release stays a draft until binary,
binary checksum, source, source checksum, and build-info assets are uploaded.
Notes contain provenance, patch profile, WRITECOPY state, experimental status,
and the non-affiliation statement. Existing tags/releases are never overwritten.

## Updating upstream inputs

Current inputs:

```text
proton_ref=experimental_11.0
gamenative_wine_tag=proton-11.0-2-20260928
package_version=auto
```

Future example (replace the date placeholder with an actual upstream tag):

```text
proton_ref=experimental_12.0
gamenative_wine_tag=proton-12.0-1-YYYYMMDD
package_version=auto
```

A new Proton release should normally require only a new `proton_ref`; a new Wine
release should normally require only a new `gamenative_wine_tag`. Never merge or
sync upstream history into this project. Use `scripts/list-upstream-refs.sh` to
discover refs without starting builds. Inspect the new sources and build help,
review the patch contents, run transactional checks, and confirm marker semantics
and redist layout. Future upstream versions may change those contracts.

If a patch disappears or conflicts, the profile fails visibly. Read all patch
logs, compare upstream changes, and update the profile deliberately in a reviewed
commit. Do not silently drop an obsolete-looking patch, apply the entire Android
stack, or assume the old allowlist remains Linux-compatible.

## Checks before an expensive build

```bash
for script in scripts/*.sh; do bash -n "$script"; done
shellcheck -x scripts/*.sh           # when installed
actionlint .github/workflows/build-arm64.yml  # when installed
python3 -m unittest discover -s tests -v
bash scripts/detect-version.sh proton-12.0-1-20270115
git ls-remote https://github.com/ValveSoftware/Proton.git refs/heads/experimental_11.0
git ls-remote https://github.com/GameNative/proton-wine.git refs/tags/proton-11.0-2-20260928
bash scripts/apply-gamenative-fex-linux.sh --check-only /path/to/wine /tmp/patch-checks
bash /path/to/Proton/configure.sh --help # inspected version exits 1 after valid help
uname -m
```

Validate workflow YAML locally with a YAML parser as well. The workflow repeats
shell, helper-test, input, native-architecture, ref resolution, and patch checks
before compilation. Local macOS checks can verify helpers but cannot substitute
for a native ARM64 Linux build and runtime testing on the target platform.

Official action majors were checked against their upstream documentation for this
implementation: [checkout v7](https://github.com/actions/checkout),
[cache v6](https://github.com/actions/cache),
[upload-artifact v7](https://github.com/actions/upload-artifact), and
[download-artifact v8](https://github.com/actions/download-artifact).
