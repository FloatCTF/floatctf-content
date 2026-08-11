FROM nginx:1.25-alpine
LABEL maintainer="FloatCTF <myx2727461997@gmail.com>"

WORKDIR /usr/share/nginx/html

COPY index.html ./
COPY result.html ./
COPY app.js ./
COPY style.css ./
COPY flag /flag

# flag 动态替换（标准模板）
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 运行时端口契约来自 meta.toml [docker].port（EXPOSE 仅示意）
EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/sh", "-c", "nginx -g 'daemon off;'"]
