# 1. 选择基础镜像：使用 Python 3.10  slim 版本，体积小
FROM python:3.10-slim

# 2. 设置工作目录
WORKDIR /app

# 设置环境变量（避免Python缓冲输出、指定时区）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    API_BASE_URL=http://127.0.0.1:8000/api/v1

# 安装系统依赖（解决PDF/文档处理、编译依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. 复制依赖文件（先复制这个，利用 Docker 缓存层）
COPY requirements.txt .

# 4. 安装依赖
# 使用清华源加速下载，--no-cache-dir 减小镜像体积
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir
#RUN pip install --no-cache-dir -r requirements.txt

# 5. 复制项目代码
COPY . .

# 创建supervisord配置文件
RUN echo '[supervisord] \
nodaemon=true \
logfile=/var/log/supervisord.log \
pidfile=/var/run/supervisord.pid \
\n[program:backend] \
command=uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 \
directory=/app \
stdout_logfile=/var/log/backend.log \
stderr_logfile=/var/log/backend.err \
autorestart=true \
\n[program:frontend] \
command=python -m app.frontend.gradio_app \
directory=/app \
stdout_logfile=/var/log/frontend.log \
stderr_logfile=/var/log/frontend.err \
autorestart=true \
' > /etc/supervisor/conf.d/app.conf

# 创建日志和存储目录
RUN mkdir -p /var/log/supervisor /app/storage && chmod 777 /app/storage


# 暴露端口
EXPOSE 8000 7860

# 启动supervisord管理多进程
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/app.conf"]