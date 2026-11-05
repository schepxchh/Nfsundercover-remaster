# NFS Undercover: Definitive Remaster

## Non-negotiable scope

* Visual changes only. Do not modify physics, handling, AI, economy, progression,
  simulation timing (including SimRate), or gameplay vehicle parameters.
* Do not replace/patch/distribute nfs.exe, bypass DRM, or distribute EA assets.
* Preserve the user's working FusionFix, loader, ultrawide and resolution settings.
  Never replace its INI wholesale. Only documented, independently opt-in visual
  changes with a before/after diff and byte-exact rollback are acceptable.
* Never silently replace DLLs, ASIs, ReShade.ini, presets or user files. Inventory
  loader conflicts before suggesting any proxy configuration. No automatic DLL chain.
* No game files, saves, executable dumps or proprietary reverse-engineered output
  in Git. Local reports can contain paths: inspect/redact before sharing.

## Quality and evidence

Image quality and high-speed readability take priority over effect count. Preserve
the game's strong sun and warm character. Avoid clipped highlights, oversaturation,
sharpening halos, temporal shimmer and excessive bloom. Do not invent a day/night
cycle. Screen-space glare is an approximation, never volumetric light, GI or RT.

Label evidence: **automated**, **source/documentation**, **requires game run** or
**experimental**. File generation and static linting do not prove shader compilation
or Steam 1.0.0.1 compatibility. Record upstream commit, tool version, SHA256,
settings, machine and test scene for every compatibility claim.

Default LOD/culling/memory patches must be off. Do not invent memory addresses,
INI keys, formats or executable fingerprints. Build a local analyzer when evidence
requires user game files. No invasive injection or reverse-engineering runtime
patch may land enabled without exact-build evidence and a rollback path.

## Engineering workflow

Use `.agents/skills/nfsuc-visual-modding/SKILL.md` for relevant work. Keep Core,
Lighting, Shadows & Visibility, Textures, Materials & Vehicles, Particles & FX,
and PostFX modules separate. New writers require a narrow path allowlist,
preflight, backup, hashes, journal, recovery, conflict handling and tests.

Run `python -m unittest discover -s tests -v`, `python tools/validate.py`, and
`python tools/build_release.py` before packaging. Windows CI must exercise the
PowerShell entry point. Real DX9/ReShade compilation, driver and in-game tests
remain separate gates. Use docs/LOCAL_TESTING.md for reproducible comparisons.

## Licensing

Original project code is MIT (LICENSE). Every third-party dependency needs a
recorded upstream URL, version, license and redistribution decision. Default to
official user-installed dependencies; bundle no third-party executable or game
assets. No-license source is inspection-only, not permission to copy. Preserve
notices and obtain rights to any replacement asset before distributing it.

## Native Foundation

Native C++17 code lives in native/. The only vendored source is the pinned official
ReShade add-on SDK under third_party/reshade with its own BSD license and snapshot.
Do not apply our MIT license to those files. No console decompilation code is copied.
Native bridge defaults disabled; no automatic native installation, game-memory writes
or guessed hook ABI. Run portable C++ checks and Windows x86 CMake/CTest before
publishing native source. Shader bytecode compilation is separate from GPU execution.
