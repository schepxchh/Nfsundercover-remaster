// SPDX-License-Identifier: MIT
// Standalone real-DX9 harness. No Undercover, asset, loader or game process needed.
#include "nfsuc/dx9_renderer.hpp"
#include <Windows.h>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace {
template<class T> void drop(T*& p) {if(p){p->Release();p=nullptr;}}
LRESULT CALLBACK window_proc(HWND h,UINT m,WPARAM w,LPARAM l) {
    if(m==WM_CLOSE) {DestroyWindow(h);return 0;}
    if(m==WM_DESTROY) {PostQuitMessage(0);return 0;}
    return DefWindowProcW(h,m,w,l);
}
HRESULT draw_test_image(IDirect3DDevice9* device,unsigned width,unsigned height) {
    HRESULT hr=device->BeginScene();
    if(FAILED(hr)) return hr;
    for(unsigned i=0;i<8;++i) {
        const unsigned v=i*255/7;
        D3DRECT rect{static_cast<LONG>(i*width/8),0,static_cast<LONG>((i+1)*width/8),static_cast<LONG>(height)};
        hr=device->Clear(1,&rect,D3DCLEAR_TARGET,D3DCOLOR_XRGB(v,v,v),1,0);
        if(FAILED(hr)) break;
    }
    const auto end=device->EndScene();
    return FAILED(hr)?hr:end;
}
bool readback(IDirect3DDevice9* d,IDirect3DSurface9* source,const nfsuc::Config& cfg,
              unsigned width,unsigned height,const std::filesystem::path& capture,bool compare) {
    IDirect3DSurface9* cpu=nullptr;
    HRESULT hr=d->CreateOffscreenPlainSurface(width,height,D3DFMT_X8R8G8B8,D3DPOOL_SYSTEMMEM,&cpu,nullptr);
    if(FAILED(hr)) return false;
    hr=d->GetRenderTargetData(source,cpu);
    D3DLOCKED_RECT locked{};
    if(SUCCEEDED(hr)) hr=cpu->LockRect(&locked,nullptr,D3DLOCK_READONLY);
    if(FAILED(hr)) {drop(cpu);return false;}
    bool good=true;
    auto pixel=[&](unsigned x,unsigned y){return static_cast<const unsigned char*>(locked.pBits)+y*locked.Pitch+x*4;};
    if(compare) {
        for(unsigned i=0;i<8;++i) {
            const float v=static_cast<float>(i*255/7)/255;
            const auto expected=nfsuc::grade_sdr({v,v,v},cfg.grade);
            const auto* p=pixel((2*i+1)*width/16,height/2);
            const float rgb[]={expected.r,expected.g,expected.b};
            for(unsigned channel=0;channel<3;++channel)
                if(std::abs(static_cast<int>(p[2-channel])-std::lround(rgb[channel]*255))>3) good=false;
        }
    }
    if(!capture.empty()) {
        if(std::filesystem::exists(capture)) {std::cerr<<"Capture exists; preserved\n";good=false;}
        else {
            std::ofstream stream(capture,std::ios::binary);
            stream<<"P6\n"<<width<<" "<<height<<"\n255\n";
            for(unsigned y=0;y<height;++y) for(unsigned x=0;x<width;++x) {
                const auto* p=pixel(x,y); const char bytes[]={static_cast<char>(p[2]),static_cast<char>(p[1]),static_cast<char>(p[0])};
                stream.write(bytes,3);
            }
            if(!stream) good=false;
        }
    }
    cpu->UnlockRect();drop(cpu);return good;
}
}

int main(int argc,char** argv) {
    bool selftest=false; std::filesystem::path capture;
    for(int i=1;i<argc;++i) {
        const std::string arg=argv[i];
        if(arg=="--self-test") selftest=true;
        else if(arg=="--capture"&&i+1<argc) capture=argv[++i];
        else {std::cerr<<"Usage: nfsuc_dx9_host [--self-test] [--capture NEW.ppm]\n";return 2;}
    }
    if(!capture.empty()&&std::filesystem::exists(capture)) {std::cerr<<"Capture exists; preserved\n";return 2;}
    const HINSTANCE instance=GetModuleHandleW(nullptr);
    WNDCLASSW wc{};wc.lpfnWndProc=window_proc;wc.hInstance=instance;wc.lpszClassName=L"NFSUCNativeStandalone";
    if(!RegisterClassW(&wc)) return 2;
    HWND window=CreateWindowW(wc.lpszClassName,L"NFSUC Native DX9 | F1 grade | R reset/resize | Esc exit",
        WS_OVERLAPPEDWINDOW,50,50,1280,760,nullptr,nullptr,instance,nullptr);
    if(!window) return 2;
    ShowWindow(window,SW_SHOW);
    IDirect3D9* api=Direct3DCreate9(D3D_SDK_VERSION);
    if(!api) {DestroyWindow(window);return 3;}
    D3DPRESENT_PARAMETERS pp{};pp.Windowed=TRUE;pp.SwapEffect=D3DSWAPEFFECT_DISCARD;
    pp.BackBufferWidth=1280;pp.BackBufferHeight=720;pp.BackBufferFormat=D3DFMT_X8R8G8B8;
    pp.hDeviceWindow=window;pp.PresentationInterval=D3DPRESENT_INTERVAL_ONE;
    IDirect3DDevice9* device=nullptr;
    HRESULT hr=api->CreateDevice(D3DADAPTER_DEFAULT,D3DDEVTYPE_HAL,window,
        D3DCREATE_HARDWARE_VERTEXPROCESSING,&pp,&device);
    if(FAILED(hr)) hr=api->CreateDevice(D3DADAPTER_DEFAULT,D3DDEVTYPE_HAL,window,
        D3DCREATE_SOFTWARE_VERTEXPROCESSING,&pp,&device);
    if(FAILED(hr)) {std::cerr<<"No native DX9 HAL device, HRESULT="<<std::hex<<hr<<"\n";drop(api);DestroyWindow(window);return 3;}
    nfsuc::Config cfg;cfg.enabled=true;
    nfsuc::Dx9Renderer renderer;
    unsigned frames=0,resets=0;bool good=true,running=true;
    std::cout<<"Own native SDR grade; no depth, GI, bloom, engine changes or game files\n";
    while(running) {
        MSG message{};
        while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)) {
            if(message.message==WM_QUIT) running=false;
            if(message.message==WM_KEYDOWN&&message.wParam==VK_ESCAPE) running=false;
            if(message.message==WM_KEYDOWN&&message.wParam==VK_F1) cfg.enabled=!cfg.enabled;
            if(message.message==WM_KEYDOWN&&message.wParam=='R') resets=1;
            TranslateMessage(&message);DispatchMessageW(&message);
        }
        if(!running) break;
        if((selftest&&frames==1)||resets==1) {
            renderer.release(); // All DEFAULT surfaces/state references released before Reset.
            pp.BackBufferWidth=pp.BackBufferWidth==1280?960:1280;
            pp.BackBufferHeight=pp.BackBufferHeight==720?540:720;
            hr=device->Reset(&pp);
            if(FAILED(hr)) {good=false;break;}
            resets=2;
        }
        hr=device->TestCooperativeLevel();
        if(hr==D3DERR_DEVICELOST) {renderer.release();Sleep(20);continue;}
        if(hr==D3DERR_DEVICENOTRESET) {
            renderer.release();hr=device->Reset(&pp);if(FAILED(hr)){Sleep(20);continue;}
        }
        if(FAILED(hr)) {good=false;break;}
        if(FAILED(draw_test_image(device,pp.BackBufferWidth,pp.BackBufferHeight))) {good=false;break;}
        IDirect3DSurface9* backbuffer=nullptr;
        hr=device->GetBackBuffer(0,0,D3DBACKBUFFER_TYPE_MONO,&backbuffer);
        if(FAILED(hr)) {good=false;break;}
        // Sentinel state that the renderer must restore exactly after drawing.
        device->SetRenderState(D3DRS_FOGENABLE,TRUE);
        device->SetRenderState(D3DRS_ALPHABLENDENABLE,TRUE);
        D3DVIEWPORT9 sentinel{7,9,pp.BackBufferWidth-14,pp.BackBufferHeight-18,.1f,.9f};
        device->SetViewport(&sentinel);
        // Second self-test frame exercises the borrowed-scene path used by ReShade.
        const bool borrowed=selftest&&frames==1;
        const auto begin=borrowed?device->BeginScene():S_OK;
        hr=FAILED(begin)?begin:renderer.render(device,backbuffer,cfg,borrowed);
        if(borrowed&&SUCCEEDED(begin)) {
            const auto end=device->EndScene();if(FAILED(end)) hr=end;
        }
        DWORD fog=0,blend=0;D3DVIEWPORT9 restored{};
        device->GetRenderState(D3DRS_FOGENABLE,&fog);device->GetRenderState(D3DRS_ALPHABLENDENABLE,&blend);
        device->GetViewport(&restored);
        IDirect3DSurface9* rt=nullptr;device->GetRenderTarget(0,&rt);
        good=good&&SUCCEEDED(hr)&&fog==TRUE&&blend==TRUE&&rt==backbuffer&&
            restored.X==sentinel.X&&restored.Y==sentinel.Y&&restored.Width==sentinel.Width&&
            restored.Height==sentinel.Height&&restored.MinZ==sentinel.MinZ&&restored.MaxZ==sentinel.MaxZ;
        drop(rt);
        if((selftest||!capture.empty())&&cfg.enabled)
            good=readback(device,backbuffer,cfg,pp.BackBufferWidth,pp.BackBufferHeight,
                frames==0?capture:std::filesystem::path{},selftest)&&good;
        if(frames==0) capture.clear();
        drop(backbuffer);
        if(!good) break;
        hr=device->Present(nullptr,nullptr,nullptr,nullptr);
        if(FAILED(hr)&&hr!=D3DERR_DEVICELOST) {good=false;break;}
        ++frames;
        if(selftest&&frames>=2) break;
    }
    const auto stats=renderer.stats();
    renderer.release();drop(device);drop(api);if(IsWindow(window)) DestroyWindow(window);
    std::cout<<"rendered="<<stats.frames_rendered<<" skipped="<<stats.frames_skipped<<" reset_state="<<resets
        <<" result="<<(good?"PASS":"FAIL")<<"\n";
    return good?0:1;
}
