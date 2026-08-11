FROM ubuntu:22.04

# Install required packages
RUN apt-get update && apt-get install -y \
    gcc \
    xinetd \
    && rm -rf /var/lib/apt/lists/*

# Create ctf user
RUN useradd -m ctf

COPY ret2text.c /tmp/ret2text.c
RUN gcc -fno-stack-protector -no-pie -z relro -O0 -g -o /home/ctf/ret2text /tmp/ret2text.c && \
    chmod 755 /home/ctf/ret2text && \
    rm /tmp/ret2text.c

# Setup xinetd
RUN echo "service ret2text" > /etc/xinetd.d/ret2text && \
    echo "{" >> /etc/xinetd.d/ret2text && \
    echo "    disable = no" >> /etc/xinetd.d/ret2text && \
    echo "    socket_type = stream" >> /etc/xinetd.d/ret2text && \
    echo "    protocol = tcp" >> /etc/xinetd.d/ret2text && \
    echo "    wait = no" >> /etc/xinetd.d/ret2text && \
    echo "    user = ctf" >> /etc/xinetd.d/ret2text && \
    echo "    type = UNLISTED" >> /etc/xinetd.d/ret2text && \
    echo "    port = 1337" >> /etc/xinetd.d/ret2text && \
    echo "    bind = 0.0.0.0" >> /etc/xinetd.d/ret2text && \
    echo "    server = /home/ctf/ret2text" >> /etc/xinetd.d/ret2text && \
    echo "    log_type = FILE /var/log/xinetd.log" >> /etc/xinetd.d/ret2text && \
    echo "    log_on_failure = HOST" >> /etc/xinetd.d/ret2text && \
    echo "    per_source = 10" >> /etc/xinetd.d/ret2text && \
    echo "    rlimit_cpu = 20" >> /etc/xinetd.d/ret2text && \
    echo "    rlimit_as = 512M" >> /etc/xinetd.d/ret2text && \
    echo "}" >> /etc/xinetd.d/ret2text

# flag 动态替换（标准模板）
COPY flag /flag
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose the service port
EXPOSE 1337

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/sbin/xinetd", "-dontfork"]
