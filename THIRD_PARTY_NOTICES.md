# Third-party notices

The MIT [LICENSE](LICENSE) covers original Proton-GameNative scripts, workflows,
and documentation. It does not relicense downloaded sources, imported patches,
or generated binary distributions. Every upstream component retains its original
license and copyright notices.

Generated builds include, but are not limited to:

| Component | Upstream licensing information |
| --- | --- |
| Valve Proton | Top-level code is BSD-3-Clause; see [LICENSE.proton](https://github.com/ValveSoftware/Proton/blob/experimental_11.0/LICENSE.proton), the upstream LICENSE, and distribution notices |
| Wine / GameNative proton-wine | LGPL-2.1, including applicable later-version permissions in individual files; see [COPYING.LIB](https://github.com/GameNative/proton-wine/blob/proton-11.0-2-20260928/COPYING.LIB) and individual source notices |
| DXVK | Its own upstream license and notices, typically zlib; verify the selected submodule revision |
| VKD3D-Proton | Its own LGPL and other applicable source-file licenses; verify the selected revision |
| FEX-related components | FEX and its dependencies have their own upstream licenses; Wine-side FEX patches retain their source licensing |
| Other Proton submodules and bundled dependencies | Their own LICENSE, COPYING, NOTICE, patent, font, and source-file notices |

The optional Box64 route bundle (`box64-armada.tar.gz`, built by
`box64/build-bundle.sh`) contains [Box64](https://github.com/ptitSeb/box64) under
the MIT license and the x86_64/i386 GCC runtime libraries from Box64's source tree
(GPL with the GCC Runtime Library Exception). It contains no Proton or Wine files.

This list is descriptive, not an exhaustive license inventory. The selected
Proton commit determines component versions and may change what is included.
Inspect its submodules, [distribution license](https://github.com/ValveSoftware/Proton/blob/experimental_11.0/dist.LICENSE),
and the actual generated redist for each release.

The packager copies the entire Valve Proton redist without filtering its license,
copying, or patent files. It does not remove or rewrite upstream copyright
notices or replace Valve's distribution LICENSE with this project's MIT LICENSE.

Every distributed binary is accompanied by a corresponding Wine source archive
containing the exact patched Wine input tree, relevant license files, build
recipes, and provenance metadata. Git object databases are excluded. The source
archive is made before compilation and includes the optional WRITECOPY change
when enabled. Public releases must keep the source archive and checksum alongside
the binary assets.

Providing this Wine archive alone does not resolve every possible third-party
license obligation. Distributors must review all included components and fulfill
their applicable source, notice, modification, and redistribution requirements.
Preserve Proton's own included licenses and any additional required corresponding
source when redistributing. This project makes no claim that generated binaries
are licensed entirely under MIT.

Proton-GameNative is an unofficial community project, not affiliated with or
endorsed by Valve, WineHQ, or GameNative.
