#!/bin/bash
# Build the test map: tools/make_lab_map.py -> .map, q3map2 -> .bsp, mbspc -> .aas (bots need it), then the pk3.
# Needs q3map2.exe and mbspc.exe (NetRadiant-custom) in data/tools. Run from Git Bash:  bash tools/build_lab_map.sh
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python}"
cd "$ROOT"
"$PYTHON" tools/make_lab_map.py | tail -1
cd data/lab
Q=../tools/q3map2.exe
BP="$(pwd -W)"
$Q -game quakelive -fs_basepath "$BP" -fs_game . -meta maps/bobbylab.map 2>&1 | grep -iE "leak|error|degenerate|bad" | head -5 || true
$Q -game quakelive -fs_basepath "$BP" -fs_game . -vis -fast maps/bobbylab.bsp 2>&1 | grep -iE "error" | head -2 || true
$Q -game quakelive -fs_basepath "$BP" -fs_game . -light -fast maps/bobbylab.bsp 2>&1 | grep -iE "error" | head -2 || true
../tools/mbspc.exe -forcesidesvisible -bsp2aas maps/bobbylab.bsp 2>&1 | grep -iE "error|leak|total reach" | tail -2 || true
cd "$ROOT"
cp data/lab/maps/bobbylab.bsp data/maps/bobbylab.bsp
"$PYTHON" -c "
import zipfile
z = zipfile.ZipFile('maps/bobbylab/bobbylab.pk3', 'w', zipfile.ZIP_DEFLATED)
z.write('data/lab/maps/bobbylab.bsp', 'maps/bobbylab.bsp')
z.write('data/lab/maps/bobbylab.aas', 'maps/bobbylab.aas')
z.close()"
echo "built maps/bobbylab/bobbylab.pk3"
