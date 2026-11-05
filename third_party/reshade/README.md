# Official ReShade SDK snapshot

Upstream: <https://github.com/crosire/reshade>

Commit: `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0` (retrieved 2026-11-05).
This is the current main revision observed through the GitHub connector on that
date, not a promise of released-injector API compatibility. API version: 20.

Scope: the eight original `include/*.hpp` files and upstream `LICENSE.md`.
All headers are byte-for-byte upstream files, including their copyright notices.
The upstream headers offer `BSD-3-Clause OR MIT`; this project chooses
**BSD-3-Clause** for this dependency, with the full upstream license retained.
`reshade_overlay.hpp` also names Omar Cornut and keeps that notice intact.
No ReShade injector, game assets or ImGui library is included.

`snapshot.json` records file bytes, SHA256 and Git blob SHA-1. It deliberately
does not hash itself or this project-authored README. Before updating the SDK,
retrieve an immutable upstream revision, preserve exact source bytes/notices,
regenerate hashes, verify the API methods/events, compile Win32 and rerun local
DX9 lifecycle tests. Include `LICENSE.md` with any binary distribution built
against these headers. ReShade/crosire names do not endorse this project.
