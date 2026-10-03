@echo off
rem Build sim\qsim.dll with MSVC (Build Tools 2022). Run from anywhere: sim\build.bat
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
if not exist build mkdir build
cl /nologo /O2 /LD /MD /W2 /D_CRT_SECURE_NO_WARNINGS /DNDEBUG /Fobuild\ /Fe:qsim.dll ^
  sim_api.c q3\bg_pmove.c q3\bg_slidemove.c q3\bg_misc.c q3\q_math.c q3\q_shared.c ^
  q3\cm_load.c q3\cm_patch.c q3\cm_polylib.c q3\cm_test.c q3\cm_trace.c || exit /b 1
echo built %~dp0qsim.dll
