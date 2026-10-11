@echo off
rem Build tools\demodump\demodump.exe with MSVC. UberDemoTools (GPL-3.0) is cloned at a pinned commit into the
rem git-ignored data\udt folder; its core sources are compiled straight into the tool.
rem   build.bat                      -> tools\demodump\demodump.exe
rem   build.bat demodump.new.exe     -> tools\demodump\demodump.new.exe (its objects in build\demodump.new\): a new
rem                                     binary beside the one in use, to be set against it before it takes its place
rem   set DEMODUMP_NO_MP=1           one compiler process instead of one a core (the PC is busy)
setlocal
cd /d "%~dp0..\.."
set OUT=demodump.exe
set OBJ=tools\demodump\build
if not "%~1"=="" (
  set OUT=%~1
  set OBJ=tools\demodump\build\%~n1
)
set MP=/MP
if defined DEMODUMP_NO_MP set MP=
if not exist data\udt (
  git clone https://github.com/mightycow/uberdemotools.git data\udt || exit /b 1
  git -C data\udt checkout caa22b678f4a9050da63239c971544b382a55044 || exit /b 1
)
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
if not exist %OBJ% mkdir %OBJ%
cl /nologo /O2 /EHsc /MD /W1 %MP% /DUDT_CREATE_DLL /DNDEBUG /DWIN32 /D_CRT_SECURE_NO_WARNINGS ^
  /Idata\udt\UDT_DLL\include /Idata\udt\UDT_DLL\src /Idata\udt\UDT_DLL\src\apps /Fo%OBJ%\ /Fe:tools\demodump\%OUT% ^
  tools\demodump\demodump.cpp data\udt\UDT_DLL\src\*.cpp /link winmm.lib || exit /b 1
echo built tools\demodump\%OUT%
