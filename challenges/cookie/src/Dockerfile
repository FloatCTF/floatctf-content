FROM php:7.4-apache
LABEL Author="myx2727461997@gmail.com"

# 复制网站文件
COPY index.php /var/www/html/
COPY flag /flag

# flag 动态替换（标准模板）
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /var/www/html

# 运行时端口契约来自 meta.toml [docker].port（EXPOSE 仅示意）
EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["apache2-foreground"]
