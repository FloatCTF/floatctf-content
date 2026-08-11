# 使用官方 Python 基础镜像
FROM python:3.10-slim

ENV OLLAMA_MODELS=/root/.ollama
# 安装依赖工具
RUN apt-get update && apt-get install -y \
    curl wget git \
    && rm -rf /var/lib/apt/lists/*

# 安装 Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# 安装 Python 依赖
WORKDIR /app
RUN pip install ollama flask
# 拷贝你的 Python 脚本
COPY main.py /app/main.py
COPY templates /app/templates

RUN mkdir -p ${OLLAMA_MODELS}
COPY .ollama/* ${OLLAMA_MODELS}

# flag 动态替换（标准模板）
COPY flag /flag
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 运行时端口契约来自 meta.toml [docker].port（EXPOSE 仅示意）
EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/sh", "-c", "ollama serve & python /app/main.py"]
