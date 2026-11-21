rem ---- AIM4 default (2.2e, owner 2026-11-19: "make that the aim4 default"; docs/runs/2.2/2.2e/CARD.md): tools/aim2_levels.py TABLE4["default"],
rem      aim3's "better" row with the sight error in proportion to the enemy's size (AIM3_SIZE_A 0, AIM3_SIZE_B 0.49 in train.cmd). Written by
rem      make_files.py; the delays are the trainer's --react-ms 100 --acquire-ms 175 (set in the command).
set AIM_LEVEL=3
set PERCEPT_SPEED=0
set PERCEPT_SPEED_MAX=
set AIM2=1
set AIM2_SPLIT=1
set AIM2_FOCUS=1
set AIM2_FLINCH=1
set PERCEPT_SIGMA=0.64
set PERCEPT_TAU=0.15
set SURPRISE_MS=0
set MOTOR_NOISE=0.080
set MOTOR_BASE=0.038
set AIM2_W=1
set AIM2_SPLIT_W=1
set AIM2_FOCUS_GAIN=0
set AIM2_FOCUS_SIG=0.7
set AIM2_C_SLIP=0.007
set AIM2_S0=5
set AIM2_CAP_SLIP=1.1
set AIM2_C_ECC=0.01
set AIM2_E0=0
set AIM2_CAP_ECC=2.8
set FLINCH_PER_DMG=0
set FLINCH_MAX=0
set FLINCH_TAU=0.3
set VEL_DELAY_MS=175
set VEL_WEBER=0.15
set RANGE_WEBER=0.17
