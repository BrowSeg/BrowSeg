@echo off
rem Builds web/dist (threads; needs a cross-origin isolated page) and web/dist-st (single thread) with Emscripten (C:\emsdk)
call C:\emsdk\emsdk_env.bat >nul 2>&1
call emcmake cmake -S . -B build-wasm -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM=C:/emsdk/ninja.exe
if errorlevel 1 exit /b 1
cmake --build build-wasm --target tsc_wasm
if errorlevel 1 exit /b 1
call emcmake cmake -S . -B build-wasm-st -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM=C:/emsdk/ninja.exe -DTSC_SINGLE_THREAD=ON
if errorlevel 1 exit /b 1
cmake --build build-wasm-st --target tsc_wasm
