@echo off
rem Overnight movement training (human 125 fps physics) followed by evaluation. Runs detached:
rem   start "" /min sim\overnight.cmd <run> <minutes>
cd /d "%~dp0.."
set RUN=%1
set MIN=%2
if "%RUN%"=="" set RUN=bloodrun_human_v1
if "%MIN%"=="" set MIN=600
python sim\train_move.py --minutes %MIN% --workers 12 --envs 256 --run %RUN% --resume > data\sim_runs\%RUN%.log 2>&1
python sim\eval_move.py --run %RUN% > data\sim_runs\%RUN%_eval.txt 2>&1
