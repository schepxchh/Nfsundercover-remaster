# ReShade bridge — experimental, default disabled

The original native renderer runs through the **official ReShade add-on API**.
It is not a ReShadeFX shader and does not replace the game executable, FusionFix,
an ASI loader or a proxy DLL. ReShade remains the externally installed event host.
Use the official build with full add-on support for an unsigned `.addon32`.
No ReShade injector binary is distributed here.

Build the Win32 target from the repository CMake project. The bridge statically
asserts 32-bit pointers and rejects a process whose filename is not `nfs.exe`.
That filename check is a scope guard, **not a verified Steam 1.0.0.1 fingerprint**.
Only D3D9 effect runtimes are accepted.

Manual local test only: preserve existing loader/DLL configuration, place the
compiled `.addon32` in an add-on search directory explicitly configured in your
official ReShade installation, and place `NFSUCNative.ini` beside the add-on.
The config is read once in `AddonInit`, before event observation. Restart the game to
change it predictably. Missing, oversized (>64 KiB), unreadable or invalid config
leaves rendering disabled. No config, injector or game file is created/changed.

The strict configuration keys and ranges live in `nfsuc/core.hpp` and its tests.
The native grade is opt-in with `Enabled=1`. Keep it `Enabled=0` for the initial
bridge check and confirm the observe-only message in ReShade.log. Disable the
FX grade and other color effects before comparing a native grade: stacking both
grades invalidates a before/after comparison. Removing the add-on and its own INI
reverses this module; separately preserve any manual changes to ReShade search
paths so they can be reverted.

## Lifecycle and limitations

- `AddonInit(HMODULE, HMODULE)` registers the SDK before any SDK event operation.
  `AddonUninit` unregisters callbacks, releases resources, unregisters the SDK.
  There is no custom DllMain, hook library, executable patch, shader replacement,
  engine memory address or proxy export.
- `init_effect_runtime(effect_runtime*)` copies the startup config and creates state only.
  Disabled mode performs no native GPU calls in the present callback.
- `reshade_present(effect_runtime*)` is **after ReShade overlay rendering and app
  state restoration**. Enabled mode therefore also grades the game HUD, menus
  and ReShade overlay. ReShade's own screenshot capture can occur earlier and
  need not include this native pass; use external captures for native A/B.
  The callback is still inside the ReShade DX9 swapchain's BeginScene/EndScene;
  the bridge passes `scene_already_active=true` to avoid nested scene calls.
- The native device is borrowed from `runtime->get_device()->get_native()` after
  checking `get_api()==d3d9`. The current backbuffer resource is queried for
  `IDirect3DSurface9`; its transient COM reference is released in the callback.
  The renderer owns only its own resources and restores modified D3D9 state.
- `destroy_effect_runtime`, `destroy_swapchain(swapchain*, bool)` and
  `destroy_device(device*)` release native resources before Reset/destruction.
  The swapchain callback conservatively discards all states on its device.
  Device-lost status also releases owned resources and skips rendering.
- There is no ImGui dependency or overlay registration. The official overlay
  header is retained intact because `reshade.hpp` includes it; its contents are
  inactive when `IMGUI_VERSION_NUM` is not defined.
- `ObserveShaders=1` enables passive `init_pipeline` metadata collection for DX9
  vertex/pixel shader bytecode. The bounded registry retains only stage, FNV1a64,
  byte size, version token and observation count. No bytecode, shader handle,
  texture or executable dump is retained or exported. Metadata is written into
  ReShade.log on clean add-on unload. A `destroy_pipeline` counter is metadata
  only. Identical hashes are grouping hints, not cryptographic fingerprints or
  evidence that a shader controls roads, shadows or any other engine feature.
  DX9/ReShade/other add-on shaders may appear together; origin is not inferred.

The official SDK snapshot is in `third_party/reshade/`, pinned to commit
`7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`, API 20, with unmodified BSD-3-Clause
licensed headers, full license and SHA256 manifest. SDK API registration fails
when the installed ReShade does not support that ABI; do not infer support merely
from a generic ReShade major version number.

Source verification at that pin:

- `include/reshade_events.hpp`: callback signatures/reset semantics;
- `include/reshade_api_device.hpp`: `device::get_native` native-device mapping;
- `source/d3d9/d3d9_impl_swapchain.cpp`: native surface resource handle;
- `source/d3d9/d3d9_swapchain.cpp`: `on_present` owns BeginScene/EndScene around
  `present_effect_runtime` and its `reshade_present` callback;
- `source/runtime.cpp`: present callback ordering after overlay/state restoration;
- `include/reshade.hpp`: registration and lifecycle conventions.

**Requires local run:** actual SDK ABI acceptance, compiler/driver behavior,
GPU rendering, device loss/reset/Alt+Tab, gameplay/menu/video appearance and FPS.
Reading source and successful host builds do not establish those results.
