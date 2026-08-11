FROM php:5-apache-jessie
LABEL Author="fb0sh <fb0sh@outlook.com>"

COPY index.php /var/www/html/index.php
COPY flag /flag

# flag 动态替换（标准模板）
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /var/www/html

# 运行时端口契约来自 meta.toml [docker].port（EXPOSE 仅示意）
EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["apache2-foreground"]
