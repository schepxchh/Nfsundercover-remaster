---
name: nfsuc-visual-modding
description: Engineer reversible visual-only modifications for NFS Undercover DX9 with FusionFix, ReShadeFX, asset analysis and evidence-based local testing. Use for this remaster's shaders, textures, geometry research, visual patches, installation and diagnostics.
---

# NFSUC visual modding

Read root AGENTS.md first. Scope is Steam nfs.exe reported as 1.0.0.1, Windows,
3440x1440, already working FusionFix. That report is not a verified executable
fingerprint. Do not change simulation, input, AI, progression or executable bytes.

## Start with evidence

1. Read README.md and docs/STATUS.md. Inspect Git status before edits.
2. Collect `tools/remaster.py diagnose --game-dir ... --output ...` locally.
   Keep executable hashes/PE machine/version evidence and INI observations;
   never upload game binaries. Treat unknown loaders and local changes as unknown.
3. Read docs/TOOLS.md and docs/FUSIONFIX.md. Retrieve authoritative upstream
   source/documentation, pin commit/blob, inspect license. Distinguish UC support
   from MW/Carbon support, loader support from executable-build compatibility,
   and current master from the user's installed FusionFix version.

## Investigate rendering

Map DX9 resource creation, postprocessing order, render-target formats, shadow
maps, LOD, culling, reflection updates and texture ownership from source or local
capture. Use tools appropriate to native D3D9; do not assume RenderDoc supports it.
No addresses or pattern patches without exact build evidence and bounds checks.
Keep captures and extracted content local. Present findings in docs/RENDERING.md
as confirmed, hypothesis or blocked. Original game has no normal day/night cycle.

## Shaders and lighting

Use original ReShadeFX/HLSL in shaders/ and explicit profiles/. Check techniques,
uniform names/ranges, search paths, color space and DX9 limits. ReShade input is
already rendered SDR; highlight rolloff cannot reconstruct clipped light. Bloom
and glare are screen-space approximations and affect HUD unless masked with a
validated method. Depth features require local depth-buffer checks, including
MSAA/menus; do not enable them by default. Avoid sharpening and oversaturation.
Run CPU mathematical tests and static checks, then separately compile in official
ReShade on Windows and test motion. Static tests are not GPU compilation.

## Textures and geometry

Use `tools/assets.py inventory` and `dds-info` on local files. See
docs/ASSET_PIPELINE.md. Record original hashes, dimensions, FourCC, alpha intent,
all mip levels, color space, normal map conventions and texture IDs. Work on
copies outside the game. Verify lossless export/import roundtrip first, then
introduce one original replacement. Preserve DXT/BC support appropriate for DX9;
do not force BC7/DX10 headers into UC. Upscaling is not recovered original detail.
Never use an unknown container writer on live archives.

For geometry, identify exact platform/container, vertex layout, indices, materials,
bounds and every LOD. Require a confirmed UC importer before promising replacement.
Do not modify collision, chassis data or vehicle performance. For materials and
particles, find actual visual-only fields with source evidence; first test one
isolated material/emitter on a copy. No broad VLT edits or guessed field names.

## Integration and rollback

Inventory root and scripts DLL/ASI hashes, PE architecture, ReShade log/config,
FusionFix version/settings and other overlays. Two proxies with one DLL name
conflict; never overwrite one or assume a chain works. User installs official
ReShade; the remaster installer owns only namespaced payload files and state.
Run install preflight/dry-run, backup/journal tests, interrupted-write recovery,
restore tests and user-edit conflict tests. Do not add arbitrary write paths.
Experimental LOD/culling remains separately opt-in and off by default.

## Test and report

Run repository checks from AGENTS.md. Follow docs/LOCAL_TESTING.md: same save,
car, camera, route, resolution, settings, warmup, screenshots and frametime runs.
Check clipping, HUD, alpha edges, shadow shimmer, pop-in, reflections, particles
and high-speed visibility. Log failed tests as well as successes.
Update docs/STATUS.md with automated / source-documentation / requires game run /
experimental labels. Package only original source, configs, tools, docs and tests;
include manifest and SHA256, never third-party DLLs or extracted EA resources.
