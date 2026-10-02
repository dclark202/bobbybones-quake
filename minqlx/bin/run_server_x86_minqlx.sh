#!/bin/bash
cd "$(dirname "$0")"
export LD_PRELOAD=$LD_PRELOAD:./minqlx.x86.so
LD_LIBRARY_PATH=".:$LD_LIBRARY_PATH" exec ./qzeroded.x86 +set zmq_stats_enable 1 "$@"
