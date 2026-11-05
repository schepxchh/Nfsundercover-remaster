// SPDX-License-Identifier: MIT
#include "nfsuc/dx9_renderer.hpp"
#include <cstring>
#include <iostream>
int main() {
    ID3DBlob *code=nullptr,*errors=nullptr;
    const HRESULT hr=nfsuc::compile_grade_shader(&code,&errors);
    if(errors) {std::cerr.write(static_cast<const char*>(errors->GetBufferPointer()),errors->GetBufferSize());errors->Release();}
    if(FAILED(hr)||!code) {std::cerr<<"ps_3_0 compilation failed\n";return 1;}
    DWORD version=0,end=0;
    const auto bytes=code->GetBufferSize();
    if(bytes>=8) {
        std::memcpy(&version,code->GetBufferPointer(),4);
        std::memcpy(&end,static_cast<const char*>(code->GetBufferPointer())+bytes-4,4);
    }
    code->Release();
    if(bytes<8||version!=0xffff0300u||end!=0x0000ffffu) {std::cerr<<"Unexpected shader bytecode framing\n";return 1;}
    std::cout<<"D3DCompile ps_3_0 PASS ("<<bytes<<" bytes); GPU execution NOT tested\n";
    return 0;
}
