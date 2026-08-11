FROM nginx:alpine
LABEL Author="myx2727461997@gmail.com"

# 复制网站文件
COPY index.html /usr/share/nginx/html/
COPY robots.txt /usr/share/nginx/html/
COPY s3cr3t_b4ckd00r.html /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY flag /flag

# flag 动态替换（标准模板）
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 运行时端口契约来自 meta.toml [docker].port（EXPOSE 仅示意）
EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/sh", "-c", "nginx -g 'daemon off;'"]
