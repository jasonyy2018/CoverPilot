# 使用官方的Python镜像作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 将当前目录下的所有文件复制到工作目录中
COPY . /app

# 安装项目的依赖库
RUN pip install --no-cache-dir -r requirements.txt

# 暴露Gradio默认的端口
EXPOSE 7860

# 启动 Gradio 应用
CMD ["python", "app/app.py"]
