// SPDX-License-Identifier: MIT
#include <d3dcompiler.h>
#include "nfsuc/dx9_renderer.hpp"
#include "shader_source.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>

namespace nfsuc {
namespace {
template<class T> void drop(T*& p) noexcept { if (p) { p->Release(); p = nullptr; } }
bool allowed(const NativeGrade& g) noexcept {
    auto range = [](float v,float lo,float hi){return std::isfinite(v)&&v>=lo&&v<=hi;};
    return range(g.exposure,-.5f,.5f)&&range(g.contrast,0,.2f)&&range(g.saturation,.8f,1.15f)
        &&range(g.warmth,-.5f,.5f)&&range(g.shoulder,0,.5f)&&range(g.strength,0,1);
}
// D3DSBT_ALL does not include render-target/depth bindings. Capture them explicitly.
class State final {
public:
    explicit State(IDirect3DDevice9* d) noexcept : d_(d) {}
    HRESULT capture(unsigned count) noexcept {
        count_ = std::min(count,4u);
        HRESULT hr=d_->CreateStateBlock(D3DSBT_ALL,&block_);
        if (FAILED(hr)) return hr;
        if (FAILED(hr=block_->Capture())) return hr;
        for (unsigned i=0;i<count_;++i) {
            hr=d_->GetRenderTarget(i,&targets_[i]);
            if (FAILED(hr)&&hr!=D3DERR_NOTFOUND) return hr;
        }
        hr=d_->GetDepthStencilSurface(&depth_);
        if (FAILED(hr)&&hr!=D3DERR_NOTFOUND) return hr;
        if (FAILED(hr=d_->GetViewport(&viewport_))) return hr;
        valid_=true;
        return S_OK;
    }
    HRESULT restore() noexcept {
        if (!valid_) return S_OK;
        valid_=false;
        HRESULT first=S_OK;
        auto keep=[&](HRESULT hr){if(FAILED(hr)&&SUCCEEDED(first)) first=hr;};
        for(unsigned i=1;i<count_;++i) keep(d_->SetRenderTarget(i,nullptr));
        keep(d_->SetDepthStencilSurface(nullptr));
        for(unsigned i=0;i<count_;++i) keep(d_->SetRenderTarget(i,targets_[i]));
        keep(d_->SetDepthStencilSurface(depth_));
        keep(block_->Apply());
        keep(d_->SetViewport(&viewport_));
        return first;
    }
    ~State() { restore(); for(auto& p:targets_) drop(p); drop(depth_); drop(block_); }
private:
    IDirect3DDevice9* d_;
    IDirect3DStateBlock9* block_=nullptr;
    IDirect3DSurface9* targets_[4]{};
    IDirect3DSurface9* depth_=nullptr;
    D3DVIEWPORT9 viewport_{};
    unsigned count_=0;
    bool valid_=false;
};
}

HRESULT compile_grade_shader(ID3DBlob** bytecode,ID3DBlob** errors) noexcept {
    return D3DCompile(grade_shader_source,std::strlen(grade_shader_source),"NFSUC native grade",
        nullptr,nullptr,"main","ps_3_0",D3DCOMPILE_ENABLE_STRICTNESS|D3DCOMPILE_OPTIMIZATION_LEVEL3,
        0,bytecode,errors);
}

void Dx9Renderer::release() noexcept {
    drop(copy_surface_); drop(copy_); drop(shader_); device_=nullptr; desc_={};
}

HRESULT Dx9Renderer::prepare(IDirect3DDevice9* device,const D3DSURFACE_DESC& desc) noexcept {
    if(device_!=device || desc.Width!=desc_.Width || desc.Height!=desc_.Height || desc.Format!=desc_.Format)
        release();
    device_=device;
    if(!shader_) {
        ID3DBlob *code=nullptr,*errors=nullptr;
        HRESULT hr=compile_grade_shader(&code,&errors);
        drop(errors);
        if(SUCCEEDED(hr)) hr=device->CreatePixelShader(static_cast<const DWORD*>(code->GetBufferPointer()),&shader_);
        drop(code);
        if(FAILED(hr)) { release(); return hr; }
    }
    if(!copy_) {
        HRESULT hr=device->CreateTexture(desc.Width,desc.Height,1,D3DUSAGE_RENDERTARGET,desc.Format,
            D3DPOOL_DEFAULT,&copy_,nullptr);
        if(SUCCEEDED(hr)) hr=copy_->GetSurfaceLevel(0,&copy_surface_);
        if(FAILED(hr)) { release(); return hr; }
        desc_=desc;
    }
    return S_OK;
}

HRESULT Dx9Renderer::render(IDirect3DDevice9* device,IDirect3DSurface9* target,const Config& config,
                            bool scene_already_active) noexcept {
    auto skip=[&](HRESULT hr){++stats_.frames_skipped;stats_.last_error=hr;return hr;};
    if(!config.enabled) return skip(S_FALSE);
    if(!device||!target||!allowed(config.grade)) return skip(E_INVALIDARG);
    D3DSURFACE_DESC desc{}; D3DCAPS9 caps{};
    HRESULT hr=target->GetDesc(&desc);
    if(FAILED(hr)) return skip(hr);
    if(FAILED(hr=device->GetDeviceCaps(&caps))) return skip(hr);
    if(caps.PixelShaderVersion<D3DPS_VERSION(3,0)||desc.Width==0||desc.Height==0||
       desc.Width>caps.MaxTextureWidth||desc.Height>caps.MaxTextureHeight||
       (desc.Format!=D3DFMT_A8R8G8B8&&desc.Format!=D3DFMT_X8R8G8B8)) return skip(D3DERR_NOTAVAILABLE);
    IDirect3DDevice9* owner=nullptr;
    hr=target->GetDevice(&owner);
    const bool same=SUCCEEDED(hr)&&owner==device; drop(owner);
    if(!same) return skip(E_INVALIDARG);
    if(FAILED(hr=prepare(device,desc))) return skip(hr);
    // Resolve MSAA (when supported) and copy into a distinct sampleable render target.
    if(FAILED(hr=device->StretchRect(target,nullptr,copy_surface_,nullptr,D3DTEXF_NONE))) return skip(hr);
    State state(device);
    if(FAILED(hr=state.capture(caps.NumSimultaneousRTs))) return skip(hr);
    if(!scene_already_active&&FAILED(hr=device->BeginScene())) return skip(hr);
    // Every setup error stops before DrawPrimitiveUP; the state guard still restores bindings.
    auto draw=[&]() noexcept -> HRESULT {
        HRESULT h;
#define NFSUC_SET(call) do { h=(call); if(FAILED(h)) return h; } while(false)
        for(unsigned i=1;i<std::min<unsigned>(caps.NumSimultaneousRTs,4);++i)
            NFSUC_SET(device->SetRenderTarget(i,nullptr));
        NFSUC_SET(device->SetDepthStencilSurface(nullptr));
        NFSUC_SET(device->SetRenderTarget(0,target));
        D3DVIEWPORT9 vp{0,0,desc.Width,desc.Height,0.0f,1.0f};
        NFSUC_SET(device->SetViewport(&vp));
        NFSUC_SET(device->SetVertexShader(nullptr));
        NFSUC_SET(device->SetPixelShader(shader_));
        NFSUC_SET(device->SetFVF(D3DFVF_XYZRHW|D3DFVF_TEX1));
        NFSUC_SET(device->SetTexture(0,copy_));
        for(unsigned i=0;i<2;++i) {
            NFSUC_SET(device->SetTextureStageState(i,D3DTSS_TEXTURETRANSFORMFLAGS,D3DTTFF_DISABLE));
            NFSUC_SET(device->SetTextureStageState(i,D3DTSS_TEXCOORDINDEX,i));
        }
        const struct {D3DRENDERSTATETYPE state;DWORD value;} states[]={
            {D3DRS_ZENABLE,FALSE},{D3DRS_ZWRITEENABLE,FALSE},{D3DRS_ALPHABLENDENABLE,FALSE},
            {D3DRS_ALPHATESTENABLE,FALSE},{D3DRS_CULLMODE,D3DCULL_NONE},{D3DRS_SCISSORTESTENABLE,FALSE},
            {D3DRS_FOGENABLE,FALSE},{D3DRS_STENCILENABLE,FALSE},{D3DRS_LIGHTING,FALSE},
            {D3DRS_CLIPPING,FALSE},{D3DRS_SRGBWRITEENABLE,FALSE},{D3DRS_COLORWRITEENABLE,15},
            {D3DRS_FILLMODE,D3DFILL_SOLID},{D3DRS_MULTISAMPLEMASK,0xffffffffu},
            {D3DRS_SEPARATEALPHABLENDENABLE,FALSE},{D3DRS_CLIPPLANEENABLE,0},{D3DRS_WRAP0,0}};
        for(const auto& s:states) NFSUC_SET(device->SetRenderState(s.state,s.value));
        const struct {D3DSAMPLERSTATETYPE state;DWORD value;} samplers[]={
            {D3DSAMP_ADDRESSU,D3DTADDRESS_CLAMP},{D3DSAMP_ADDRESSV,D3DTADDRESS_CLAMP},
            {D3DSAMP_MINFILTER,D3DTEXF_POINT},{D3DSAMP_MAGFILTER,D3DTEXF_POINT},
            {D3DSAMP_MIPFILTER,D3DTEXF_NONE},{D3DSAMP_SRGBTEXTURE,FALSE},
            {D3DSAMP_MAXMIPLEVEL,0},{D3DSAMP_MAXANISOTROPY,1},{D3DSAMP_MIPMAPLODBIAS,0}};
        for(const auto& s:samplers) NFSUC_SET(device->SetSamplerState(0,s.state,s.value));
        const float a[]={config.grade.exposure,config.grade.contrast,config.grade.saturation,config.grade.warmth};
        const float b[]={config.grade.shoulder,config.grade.strength,0,0};
        NFSUC_SET(device->SetPixelShaderConstantF(0,a,1));
        NFSUC_SET(device->SetPixelShaderConstantF(1,b,1));
        struct Vertex {float x,y,z,rhw,u,v;};
        const float w=static_cast<float>(desc.Width),hgt=static_cast<float>(desc.Height);
        // DX9 transformed vertices require a half-pixel offset; texel-centres align exactly.
        const Vertex vertices[]={{-.5f,-.5f,0,1,0,0},{w-.5f,-.5f,0,1,1,0},
            {-.5f,hgt-.5f,0,1,0,1},{w-.5f,hgt-.5f,0,1,1,1}};
        NFSUC_SET(device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP,2,vertices,sizeof(Vertex)));
#undef NFSUC_SET
        return S_OK;
    };
    hr=draw();
    const HRESULT end=scene_already_active?S_OK:device->EndScene();
    const HRESULT restored=state.restore();
    if(SUCCEEDED(hr)&&FAILED(end)) hr=end;
    if(SUCCEEDED(hr)&&FAILED(restored)) hr=restored;
    if(FAILED(hr)) return skip(hr);
    ++stats_.frames_rendered;stats_.last_error=S_OK;return S_OK;
}
}
