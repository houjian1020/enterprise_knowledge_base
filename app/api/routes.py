#================================================================
# API 路由：业务逻辑层 (上传、聊天)
#================================================================


import os
import shutil
import json
from typing import List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse,StreamingResponse
from streamlit import success

# 导入我们之前写的组件
from app.api.schemas import ChatRequest, ChatResponse, HealthResponse
from langchain_core.messages import AIMessageChunk # 1. 新增导入
from app.core.rag_engine import RagEngine
from app.core.graph import rag_graph
from app.config import settings
from app.core.logger import get_logger # 1. 导入我们自定义的日志工具
# 2. 创建一个本模块专用的 log
log = get_logger(__name__)

# 创建路由实例
router = APIRouter()


# 确保存储根目录存在
# exist_ok=False 默认，目录已存在，会直接抛出异常
# exist_ok=True 目录已存在时不报错
os.makedirs(settings.STORAGE_BASE_PATH, exist_ok=True)

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查接口，用于确认服务是否启动"""
    return {"status": "success", "message": "知识库服务运行正常"}

@router.post("/upload")
async def upload_document(tenant_id:str = Form(...,description="租户ID"),file: UploadFile = File(...,description="上传的文件")):
    """
    上传文档接口
    1. 保存文件到磁盘
    2. 调用 RAG 引擎进行向量化
    """
    # 1.初始化向量模型
    engine = RagEngine(tenant_id=tenant_id)

    # 1.构建租户目录
    tenant_dir = os.path.join(settings.STORAGE_BASE_PATH, tenant_id)
    # os.makedirs(tenant_dir, exist_ok=True)

    # 2.保存文件
    file_path = os.path.join(f"{tenant_dir}/files", file.filename)
    log.info(f"file_path: {file_path}")
    try:
        with open(file_path, "wb") as buffer:
            # 写文件(最标准、最高效的保存文件方式、支持大文件)
            # 第一个参数：file.file 上传的文件数据流
            # 第二个参数：buffer 本地目标文件
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件保存失败：{str(e)}")

    # 3.向量化到本地
    #engine = RagEngine(tenant_id=tenant_id)
    success = engine.add_document(file_path=file_path,filename=file.filename)

    if success:
        return {"message": "文件上传并索引成功", "filename": file.filename}
    else:
        raise HTTPException(status_code=500, detail="文件索引失败，请检查日志")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    聊天接口
    1. 接收问题和租户ID
    2. 调用 LangGraph 工作流
    3. 返回回答和来源
    4. 支持流式输出
    """
    try:
        # 1. 准备 LangGraph 的输入状态
        # 注意：这里直接传入字典，LangGraph 会自动映射到 AgentState
        input_state = {
            "tenant_id": request.tenant_id,
            "question": request.question,
            "messages": [],  # TODO 这里演示单次问答，多轮对话需维护历史
            "context_docs": []  # 这里应该先调用检索节点，为了演示先留空
        }

        # 2. 定义生成器：这是流式的核心
        # 2. 流式生成器核心逻辑
        async def generate_stream():
            # 【关键】直接遍历 graph 的流
            # 注意：是 astream_events，不是 astream
            async for event in rag_graph.astream_events(input_state, version="v2"):
                event_type = event["event"]
                #log.info(f"事件类型: {event_type}")
                # 筛选 LLM 流式 token 事件
                if event_type == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        # chunk 是 AIMessageChunk，有 .content 属性
                        data = {
                            "answer": chunk.content,
                            "sources": [],
                            "is_end": False
                        }
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            # 发送结束信号
            data = {"answer": "", "sources": [], "is_end": True}
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        # 返回流式响应，指定正确的媒体类型
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲，确保实时输出
            }
        )
    except Exception as e:
        log.error(f"聊天处理出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="系统内部错误")