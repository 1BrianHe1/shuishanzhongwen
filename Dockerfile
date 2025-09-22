FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libjpeg62-turbo zlib1g ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /code

# 安装依赖（requirements.txt 在 app/ 下）
COPY app/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt

# 复制源码：把宿主机 app/ 作为一个包放到 /code/app
COPY app/ /code/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
