@echo off
rem Build tools\demodump\demodump.exe with MSVC. UberDemoTools (GPL-3.0) is cloned at a pinned commit into the
rem git-ignored data\udt folder; its core sources are compiled straight into the tool.
setlocal
cd /d "%~dp0..\.."
if not exist data\udt (
  git clone https://github.com/mightycow/uberdemotools.git data\udt || exit /b 1
  git -C data\udt checkout caa22b678f4a9050da63239c971544b382a55044 || exit /b 1
)
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
if not exist tools\demodump\build mkdir tools\demodump\build
cl /nologo /O2 /EHsc /MD /W1 /MP /DUDT_CREATE_DLL /DNDEBUG /DWIN32 /D_CRT_SECURE_NO_WARNINGS ^
  /Idata\udt\UDT_DLL\include /Idata\udt\UDT_DLL\src /Idata\udt\UDT_DLL\src\apps /Fotools\demodump\build\ /Fe:tools\demodump\demodump.exe ^
  tools\demodump\demodump.cpp data\udt\UDT_DLL\src\*.cpp /link winmm.lib || exit /b 1
echo built tools\demodump\demodump.exe
