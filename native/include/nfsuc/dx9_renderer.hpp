// SPDX-License-Identifier: MIT
#pragma once
#include <d3d9.h>
#include <d3dcompiler.h>
#include <cstdint>
#include <string>
#include "nfsuc/core.hpp"

namespace nfsuc {
struct Dx9Stats {
    std::uint64_t frames_rendered = 0;
    std::uint64_t frames_skipped = 0;
    HRESULT last_error = S_OK;
};

// Called on the host's render thread. ReShade presents inside its own scene;
// scene_already_active=true borrows that scene without ending/restarting it.
// Device is borrowed. No offsets, executable writes, depth reads or interception.
class Dx9Renderer final {
public:
    Dx9Renderer() = default;
    ~Dx9Renderer() { release(); }
    Dx9Renderer(const Dx9Renderer&) = delete;
    Dx9Renderer& operator=(const Dx9Renderer&) = delete;
    HRESULT render(IDirect3DDevice9* device, IDirect3DSurface9* target, const Config&,
                   bool scene_already_active = false) noexcept;
    // Host must call BEFORE Reset and before releasing the associated device.
    void release() noexcept;
    const Dx9Stats& stats() const noexcept { return stats_; }
private:
    IDirect3DDevice9* device_ = nullptr; // borrowed
    IDirect3DPixelShader9* shader_ = nullptr;
    IDirect3DTexture9* copy_ = nullptr;
    IDirect3DSurface9* copy_surface_ = nullptr;
    D3DSURFACE_DESC desc_{};
    Dx9Stats stats_{};
    HRESULT prepare(IDirect3DDevice9*, const D3DSURFACE_DESC&) noexcept;
};
// Also used by the Windows shader-compiler test; no game or GPU required.
HRESULT compile_grade_shader(ID3DBlob** bytecode, ID3DBlob** errors) noexcept;
}
