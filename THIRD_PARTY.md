# Third-party research and redistribution policy

Visual Foundation 0.2 bundles original project source, shaders, presets and docs.
Native Foundation 0.3 additionally vendors the unmodified official ReShade SDK
headers and its BSD-3-Clause license in `third_party/reshade`. Snapshot metadata
records exact upstream commit, byte counts, SHA256 and Git blob hashes. Its header
implementation is compiled into our add-on; include its license in binary packages.
It does **not** bundle ReShade, FusionFix, ASI loaders, texture tools, proprietary
SDK binaries, game executables, game textures, geometry, LUTs or third-party mods.
The project's MIT license applies only to original work in this repository.

Research snapshot: 2026-11-02. Exact references and compatibility limits are in
[docs/TOOLS.md](docs/TOOLS.md) and [docs/FUSIONFIX.md](docs/FUSIONFIX.md).
A license that permits redistribution does not establish runtime compatibility.

| Dependency / reference | License evidence | Distribution in 0.2 |
|---|---|---|
| ReShade, Patrick Mours | [BSD-3-Clause](https://github.com/crosire/reshade/blob/7bf9de8b33bcc76c3177007e65d73c72dd0f34c0/LICENSE.md) | User installs official setup from reshade.me |
| ReShadeFX reference / shader collection | Per-file; [ReShade.fxh](https://github.com/crosire/reshade-shaders/blob/master/Shaders/ReShade.fxh) declares CC0-1.0 | No external shader collection bundled; do not assume every FX has same license |
| ThirteenAG WidescreenFixesPack / FusionFix | See source/license audit in FUSIONFIX.md | Existing user installation retained |
| NI240SX UCGT | [README](https://github.com/NI240SX/UCGT/blob/5233fc9369744a4c6b90c942171a2eb93a8f1192/README.md) grants credit-based reuse; mixed dependency origins listed; no standard top-level LICENSE found | External tool only, no source or DLL copied |
| R-033 Texture Wizard | [GPL v3](https://github.com/R-033/texwizard/blob/51e7d29c070aa8f9b7c3b44b78fadfda299777a3/LICENSE) | No ASI/source bundled |
| SpeedReflect Binary / NI240SX Binercover | [GPL v3](https://github.com/NI240SX/Binercover/blob/e609593ed8cfbf7fa85eda6774064482f4d4a7f5/LICENSE) | External tools only |
| SpeedReflect Nikki | [MIT](https://github.com/SpeedReflect/Nikki/blob/b2468b7e4f1ac1efdb29a0c57380dbc90ed1afe7/LICENSE) | Inspection only in this iteration |
| NFS-TexEd / NFS-VltEd / CarToolkit, nfsu360 | [Official downloads](https://nfs-tools.blogspot.com/p/downloads.html); permissive redistribution license/source not established | User downloads; never mirror binaries under our MIT license |
| Microsoft DirectXTex | [MIT](https://github.com/microsoft/DirectXTex/blob/46d1cbea413b316f5e84352a0de8df227f945616/LICENSE) | External optional DDS tools |
| apitrace | [MIT](https://github.com/apitrace/apitrace/blob/c3829c8fc94332f46f7616d9c9ee995b63d9bfc1/LICENSE) | External research tool; no DLL bundled |
| RenderDoc | [MIT](https://github.com/baldurk/renderdoc/blob/1d83c25876b315c0a13bc6906c7dd82667b09892/LICENSE.md) | Not used for native DX9; no binary bundled |
| Need for Speed Undercover / EA Black Box assets | Proprietary; no redistribution permission established | Never bundled, no exe replacement or DRM bypass |
| Natural Lighting / Undercover Exposed and other mods | Author pages describe capabilities; asset permissions not established | Research links only, no resource/LUT/script copied |

Future releases adding a dependency must record version, upstream URL, SHA256,
license text, notices and actual packaging decision. Custom asset submissions need
creator, source, license, target resource ID and a reproducible build. Public
availability and inclusion in another mod do not grant permission to repackage.
Modified copyleft sources must retain their license and corresponding-source
obligations; do not paste them into an MIT file. Resolve uncertain rights before
including a resource; external user installation remains the default.

## Native DX9 research update — 2026-11-05

The references below were inspected before considering native integration. They
are not bundled dependencies merely by appearing in this table. No Modern Fix
runtime, DXVK binary, original game code or lookup textures were copied as part of
this research. See [docs/MODERN_FIX.md](docs/MODERN_FIX.md) for code architecture,
build restrictions and separation between source evidence and game verification.

| Reference | Pinned license | Decision |
|---|---|---|
| Brdjx Modern PC Fix | [MIT, Bradley Jackson, 2026](https://github.com/Brdjx/nfs-undercover-modern-fix/blob/b57ffcaf480ab08bf0ddda93c3a2a4ea057b166d/LICENSE) | Source study only. Its measured target is 1.1.2.1; do not transplant fixed addresses to Steam 1.0.0.1 |
| Dear ImGui | [MIT, Omar Cornut](https://github.com/ocornut/imgui/blob/8c8b8fc266e8cd7fac09340c0373abc28732adb0/LICENSE.txt) | Candidate for native debug UI; preserve notices if actually integrated |
| MinHook | [BSD-2-Clause and HDE notices](https://github.com/TsudaKageyu/minhook/blob/8af6b4acae5a9388fd742b56fa79ece89d96f823/LICENSE.txt) | Hook-library reference; no source copied by this research |
| SafetyHook | [BSL-1.0](https://github.com/cursey/safetyhook/blob/f44cc070a8340f2f26649553c49533475417304d/LICENSE) | Alternative hook-library reference; transitive dependencies require their own review |
| SMAA | [MIT-style with explicit binary-distribution clarification](https://github.com/iryoku/smaa/blob/71c806a838bdd7d517df19192a20f0c61b3ca29d/LICENSE.txt) | HLSL3 implementation verified in source; no code/lookup textures bundled |

Windows SDK interfaces, system D3D9 and D3DCompiler are platform dependencies;
Microsoft documentation is evidence about their behavior, not a license to mirror
arbitrary SDK redistributables. Load the correct x86 system component or use an
official installation mechanism where required. Keep the native module's own
original source license distinct from any later third-party additions.
