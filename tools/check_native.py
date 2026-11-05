#!/usr/bin/env python3
"""Build/run portable native checks with CMake, or g++ when CMake is absent."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import os

ROOT = Path(__file__).resolve().parents[1]


def main():
    def run(command):
        subprocess.run(command, cwd=ROOT, check=True)
    if shutil.which("cmake"):
        build = ROOT / "build" / "native"
        command = ["cmake", "-S", str(ROOT), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"]
        if os.name == "nt":
            command += ["-A", "Win32"]
        run(command)
        run(["cmake", "--build", str(build), "--config", "Release"])
        run(["ctest", "--test-dir", str(build), "-C", "Release", "--output-on-failure"])
    elif os.name != "nt" and shutil.which("g++"):
        with tempfile.TemporaryDirectory(prefix="nfsuc-native-") as directory:
            for name, sources in (("core", ["native/src/core.cpp", "native/tests/core_tests.cpp"]),
                                  ("registry", ["native/tests/shader_registry_tests.cpp"])):
                output = str(Path(directory) / name)
                run(["g++", "-std=c++17", "-O2", "-DNDEBUG", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                     "-pthread", "-I", "native/include", *sources, "-o", output])
                run([output])
        print("Portable native checks PASS. Windows/D3D9 compilation NOT performed here.")
    else:
        raise SystemExit("Install CMake 3.20+ and C++17 build tools (Windows: MSVC + Windows SDK, Win32).")


if __name__ == "__main__":
    main()
