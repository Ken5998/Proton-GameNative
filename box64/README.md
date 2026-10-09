# Box64 route: x86_64 Proton under Box64

A second, independent way to run Windows games on ARM64 Linux devices. Instead of
building an ARM64 Proton, it runs an existing, unmodified **x86_64 Proton** (for
example GE-Proton10-34) with [Box64](https://github.com/ptitSeb/box64) instead of
FEX. This is close to how GameNative runs x86_64 Proton on Android.

Nothing in the original Proton is changed. The installer creates a separate Steam
compatibility tool next to it, such as **GE-Proton10-34 (Box64 WoW64)**, which links
to the original files and starts every x86_64 program through Box64.

## Status

Tested on ArmadaOS (AYN Odin 2, Adreno 740, Steam in gamescope) with GE-Proton10-34
in WoW64 mode and Box64 `v0.4.3-3`: a 32-bit Direct3D 9 game reached gameplay with
gamepad input. That is one data point, not a compatibility claim. Whether Box64 or
FEX works better depends on the game.

## Install

1. Get `box64-armada.tar.gz`, either from a run of **Actions → Box64 route bundle**
   (the artifact also contains the installer) or by building it:
   ```bash
   bash box64/build-bundle.sh out          # on ARM64 Linux
   CROSS_PREFIX=aarch64-linux-gnu- bash box64/build-bundle.sh out   # elsewhere
   ```
   The device needs glibc 2.39 or newer when the bundle is built on Ubuntu 24.04.
2. Put `armada-box64.sh`, `armada_box64.py` and `box64-armada.tar.gz` in one folder and
   install for an x86_64 Proton that Steam already has:
   ```bash
   bash armada-box64.sh install GE-Proton10-34                          # on the device
   REMOTE=user@device bash armada-box64.sh install GE-Proton10-34       # from another computer
   ```
3. Restart Steam and pick **GE-Proton10-34 (Box64 WoW64)** in the game's
   Properties → Compatibility.

`status` shows what is installed and `uninstall` removes the tools and Box64.

## How it works

- Every ELF in the Proton's `files/bin*` folders gets a wrapper that runs it with
  Box64. Box64 then runs every x86_64 process Wine starts.
- The tool has no Steam Linux Runtime: that container is x86_64 and would bring FEX
  back.
- **WoW64 mode** (the default when the Proton supports `PROTON_USE_WOW64`) runs 32-bit
  games inside the 64-bit Wine. The `classic` mode runs the 32-bit Wine through Box32.
  Box32 cannot load Vulkan, so 32-bit games using DXVK do not start there.
- The wrapper sets these defaults. A value in the game's launch options wins.

| Variable | Default | Why |
| --- | --- | --- |
| `PROTON_USE_WOW64` | `1` (WoW64 mode) | Avoids Box32, see above |
| `PROTON_NO_NTSYNC` | `1` | NTSync waits fault under Box64 (`inproc_wait` in ntdll). This kills Wine's XInput thread, so gamepads stop working |
| `BOX64_DYNACACHE` | `0` | A stale Box64 code cache made `wineboot` crash at startup |

The bundle's `box64.box64rc` is empty on purpose: per-process sections of the stock
rc file override `BOX64_*` variables.

## Per-game Box64 settings

Box64 settings belong in a game's launch options, not in the defaults. For example,
this is the GameNative "Performance" preset with `SAFEFLAGS=2`, used while testing a
32-bit DirectX 9 game:

```text
BOX64_DYNAREC_SAFEFLAGS=2 BOX64_DYNAREC_FASTNAN=1 BOX64_DYNAREC_FASTROUND=1 BOX64_DYNAREC_X87DOUBLE=0 BOX64_DYNAREC_BIGBLOCK=3 BOX64_DYNAREC_STRONGMEM=0 BOX64_DYNAREC_FORWARD=512 BOX64_DYNAREC_CALLRET=1 BOX64_DYNAREC_WAIT=1 BOX64_AVX=0 BOX64_MMAP32=1 %command%
```

`BOX64_LOG=1` prints Box64's own messages into the Proton log.

## Troubleshooting

- Logs: add `PROTON_LOG=1 %command%`; non-Steam shortcuts write
  `/tmp/steam-<shortcut id>.log`.
- **`c000007b` while starting a game** whose prefix was first created by an ARM64
  Proton: the prefix still points Wine at ARM64 DLLs. Run
  `bash armada-box64.sh cleanprefix <app id>` with the game closed. It moves ARM64 DLLs
  and the `Wow64` registry keys into `pfx/arm64-leftovers-<time>/` instead of deleting
  them.
- **`wineboot` or `explorer` crash right away** with many
  `cannot add DynaCache Block` lines: move `~/.cache/box64` aside and keep
  `BOX64_DYNACACHE=0`.
- **Gamepad listed but dead**: `wait failed in the update thread` in the log means
  NTSync is still on; check that `PROTON_NO_NTSYNC=1` is not overridden.

## Licensing

Box64 is MIT licensed (`box64-LICENSE.txt` in the bundle). The bundle's `x64lib/` and
`x86lib/` hold the x86_64 and i386 GCC runtime libraries from Box64's source tree.
They are GCC components under the GPL with the GCC Runtime Library Exception. The
installer copies and links Proton files only on the device; it redistributes no
Proton or Wine files.
