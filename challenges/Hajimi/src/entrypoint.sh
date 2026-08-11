#!/bin/sh
set -eu

# FloatCTF dynamic flag runtime contract:
# 写入 /flag 与 /flag.txt（hajimi 二进制读取 /flag.txt），随后 unset FLAG。
if [ -n "${FLAG:-}" ]; then
    printf '%s\n' "$FLAG" > /flag
    printf '%s\n' "$FLAG" > /flag.txt
    chmod 444 /flag.txt
    unset FLAG
fi

exec "$@"
