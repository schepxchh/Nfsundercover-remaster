// SPDX-License-Identifier: MIT
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <iostream>

// Verify the loader ABI without registering ReShade, rendering or loading a game.
int main(int argc,char** argv) {
    if(argc!=2) return 2;
    HMODULE module=LoadLibraryA(argv[1]);
    if(!module) {std::cerr<<"Cannot load own add-on, Win32 error="<<GetLastError()<<"\n";return 1;}
    bool good=true;
    for(const char* name:{"AddonInit","AddonUninit","NAME","DESCRIPTION"}) {
        if(!GetProcAddress(module,name)) {std::cerr<<"Missing undecorated export: "<<name<<"\n";good=false;}
    }
    FreeLibrary(module);
    if(good) std::cout<<"Win32 add-on loader exports PASS; SDK registration/game NOT tested\n";
    return good?0:1;
}
