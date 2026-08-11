#!/bin/sh
set -eu

# FloatCTF dynamic flag runtime contract:
# 写入 /flag；静态页面 result.html 中的 __FLAG__ 占位符同步替换为真实 FLAG。
if [ -n "${FLAG:-}" ]; then
    printf '%s\n' "$FLAG" > /flag
    ESCAPED_FLAG=$(printf '%s\n' "$FLAG" | sed -e 's/[\\/&]/\\&/g')
    sed -i "s/__FLAG__/$ESCAPED_FLAG/g" /usr/share/nginx/html/result.html
    unset FLAG
fi

exec "$@"
