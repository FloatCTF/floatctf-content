FROM php:5-apache-jessie
LABEL Author="ablklice <ablklice@gmail.com>"

COPY ./files /tmp/
RUN cp -rf /tmp/html /var/www/ && chown -R www-data:www-data /var/www/html
COPY flag /flag

# flag 动态替换（标准模板）
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /var/www/html

# 运行时端口契约来自 meta.toml [docker].port（EXPOSE 仅示意）
EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["apache2-foreground"]
