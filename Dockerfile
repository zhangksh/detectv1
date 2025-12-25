FROM python:3.11-slim

WORKDIR /app

# 复制项目文件
COPY . .

# 安装依赖
RUN pip install torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0 --index-url https://download.pytorch.org/whl/cu128
# CUDA 13.0
RUN pip install -e .\ultralytics-8.3.163\
RUN pip install uvicorn==0.40.0 fastapi==0.127.0 minio==7.2.20 GPUtil==1.4.0
# 设置Python路径
ENV PYTHONPATH=/app

# 设置入口点
CMD ["python", "src/main.py"]