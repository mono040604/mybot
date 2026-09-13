# ===== 打包说明书：告诉云托管"怎么把你的代码变成能跑的容器" =====
# 每一行是一个步骤，从上往下依次执行。

# ① 基础镜像：拿一个现成的 Python 3.11 环境当底子
#    slim 是"精简版"，去掉用不到的东西，镜像更小、构建更快
FROM python:3.11-slim

# ② 工作目录：容器里之后所有相对路径都以 /app 为基准
WORKDIR /app

# ③ 先复制依赖清单，再装依赖
#    为什么"先 COPY requirements.txt 再 COPY 代码"？
#    因为 Docker 会把每一层缓存起来：只要 requirements.txt 没变，
#    你改代码重打包时这一步就不用重新 pip install，构建快很多。
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ④ 再把整个项目代码复制进来（.dockerignore 里排除的文件不会进来）
COPY . .

# ⑤ 端口：云托管会通过环境变量 PORT 告诉你该监听哪个端口
#    这里的 ENV 只是兜底默认值，真正生效的是云托管注入的 PORT
ENV PORT=80
EXPOSE 80

# ⑥ 启动命令：容器一启动就跑这个
CMD ["python", "gateway.py"]
