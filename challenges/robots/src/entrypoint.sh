#!/bin/sh
set -eu

# FloatCTF dynamic flag runtime contract:
# 写入 /flag；静态页面 s3cr3t_b4ckd00r.html 中的占位符同步替换为真实 FLAG。
if [ -n "${FLAG:-}" ]; then
    printf '%s\n' "$FLAG" > /flag
    ESCAPED_FLAG=$(printf '%s\n' "$FLAG" | sed -e 's/[\\/&]/\\&/g')
    sed -i "s/flag{test_flag}/$ESCAPED_FLAG/g" /usr/share/nginx/html/s3cr3t_b4ckd00r.html
    unset FLAG
fi

exec "$@"
