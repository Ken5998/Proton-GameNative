# Proton-GameNative

An experimental ARM64 Steam compatibility-tool build combining Valve Proton's
Linux runtime and build infrastructure with GameNative's ARM64EC/FEX-oriented
Wine work. This is a standalone build project: upstream repositories are fetched
as build inputs, never vendored or merged into this repository's history.

GameNative maintains Wine changes that may be useful on ARM64 Linux devices.
This project tests a selected Linux/glibc-compatible patch profile while keeping
Valve's standard Proton compatibility-tool format. Test Drive Unlimited 2 was
an early compatibility case that motivated the experiment; this project is
generic and contains no game-specific patches or DRM bypasses.

## Status and target

The initial target is ARM64 Linux, with ArmadaOS as the primary intended test
platform, and Steam ARM64 environments compatible with Valve's produced format.
Successful compilation is not evidence that a particular game or platform works.
Runtime compatibility remains experimental until tested.

This is **not** an official Valve Proton build, an official GameNative release,
or an Android `.wcp`. It is not affiliated with or endorsed by Valve, WineHQ or
GameNative, and is not tied to one game.

Valve's [ARM64 build instructions](https://github.com/ValveSoftware/Proton/blob/experimental_11.0/README.md#arm64-builds)
require a native ARM64 build machine and state that the resulting builds cannot
be used with x86 Steam running through FEX. ARM64 hardware alone does not establish
a supported Steam/runtime environment.

## Install

Download the binary archive and checksum from a successful Actions run or a
published prerelease. Keep the corresponding source archive when redistributing.

```bash
sha256sum -c Proton-GameNative-11.0-2-arm64.tar.gz.sha256
mkdir -p ~/.local/share/Steam/compatibilitytools.d
tar -xzf Proton-GameNative-11.0-2-arm64.tar.gz -C ~/.local/share/Steam/compatibilitytools.d/
```

Restart Steam and select **Proton-GameNative 11.0-2 ARM64** in the game's
compatibility settings. Use the version shown in your downloaded filenames.
The archive contains exactly one compatibility-tool directory and includes
`build-info.txt` with source provenance and the ordered patch list.

## Build manually with GitHub Actions

Open **Actions → Build Proton-GameNative ARM64 → Run workflow**. Builds run on
native `ubuntu-24.04-arm` runners using Docker and Valve's ARM64 SDK. No QEMU is
used. There are no push triggers, scheduled builds, or automatic update builds.

| Input | Default | Purpose |
| --- | --- | --- |
| `proton_ref` | `experimental_11.0` | Valve Proton branch, tag, or commit |
| `gamenative_wine_tag` | `proton-11.0-2-20260928` | Exact GameNative Wine tag |
| `package_version` | `auto` | Derive `11.0-2` from the tag, or provide a safe explicit version |
| `patch_profile` | `gamenative-fex-linux` | Reviewed FEX/ARM64EC patch list |
| `enable_writcopy` | `false` | Experimental PE-header WRITECOPY protection |
| `publish_release` | `false` | Publish a unique experimental prerelease with binary and source assets |

Every successful run uploads the binary and patched Wine source archives, both
SHA256 files, `build-info.txt`, and `build.log`. Artifact display names include
version, run number, WRITECOPY state, and attempt; distributable filenames omit
run numbers. Failed runs retain available diagnostics without publishing binaries.

See [BUILDING.md](BUILDING.md) for the architecture, patch policy, storage
requirements, local checks, and upstream upgrade process.

## Licensing

Original scripts, workflows, and documentation in this repository use the
[MIT license](LICENSE). Generated Proton distributions contain third-party
software under multiple upstream licenses; **the distributions are not wholly
MIT licensed**. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Packaging
preserves Valve's complete redist and its license, copying, and patent files.
