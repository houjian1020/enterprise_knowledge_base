#================================================================
# 程序的入口，负责把上面的路由组装起来，并启动服务器
#================================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import router

# 1. 创建 FastAPI 实例
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="企业级知识库 API 服务"
)

# 2. 配置跨域 (CORS)
# 允许前端（如 Gradio 或 React）访问这个 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 注册路由
app.include_router(router, prefix=settings.API_V1_PREFIX)

# 4. 根路径欢迎信息
@app.get("/")
async def root():
    return {
        "message": "欢迎使用企业级知识库系统",
        "docs_url": "/docs"  # FastAPI 自动生成的文档地址
    }

if __name__ == "__main__":
    import uvicorn
    # 启动服务，监听 0.0.0.0 表示允许外部访问
    # 终端启动方式： python -m app.main
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)