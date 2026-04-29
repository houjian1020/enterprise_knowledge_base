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
from langchain_core.messages import AIMessageChunk, HumanMessage,AIMessage # 1. 新增导入
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


@router.delete("/upload")
async def delete_file(
        filename: str,
        tenant_id: str = Form(...)
):
    """
    删除指定的文件及其索引
    """
    try:
        # 1. 初始化该租户的引擎
        engine = RagEngine(tenant_id=tenant_id)

        # 2. 调用删除方法
        success = engine.delete_document(filename)

        if success:
            return {"message": f"文件 {filename} 已成功删除"}
        else:
            raise HTTPException(status_code=400, detail="删除失败，请查看后端日志")

    except Exception as e:
        log.error(f"删除接口异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        # ==============================================
        # 【多轮对话】接收前端传来的对话历史，并转为 LangChain 格式
        # 来源：Gradio 聊天界面自动维护的 history
        # 前端结构：[{"role":"user", "content":[{"text":"内容"}]}]
        # ==============================================
        history_messages = []
        # 遍历前端传来的历史消息
        for msg in request.history:
            role = msg.get("role")  # 获取角色：user / assistant
            content_list = msg.get("content", [])  # content是数组！

            # 提取真正的文本内容
            text = ""
            if isinstance(content_list, list) and len(content_list) > 0:
                text = content_list[0].get("text", "")  # 取出text字段

            # 转为 LangChain 标准消息
            if role == "user" and text:
                history_messages.append(HumanMessage(content=text))
            elif role == "assistant" and text:
                history_messages.append(AIMessage(content=text))

        log.info(f"【多轮对话】解析后历史消息数量：{len(history_messages)}")

        # 1. 准备 LangGraph 的输入状态
        # 注意：这里直接传入字典，LangGraph 会自动映射到 AgentState
        input_state = {
            "tenant_id": request.tenant_id,
            "question": request.question,
            "messages": history_messages,  # 多轮对话核心
            "context_docs": []  # 这里应该先调用检索节点，为了演示先留空
        }

        # 2. 定义生成器：这是流式的核心
        # 2. 流式生成器核心逻辑
        async def generate_stream():
            # 用于存储引用数据
            final_sources = []
            # 标记是否已经发送了引用数据
            sources_initialized = False

            # 【关键】直接遍历 graph 的流
            # 注意：是 astream_events，不是 astream
            async for event in rag_graph.astream_events(input_state, version="v2"):
                event_type = event["event"]
                event_name = event.get("name", "unknown")
                # 这行日志能帮你看到所有底层事件
                log.info(f"--- Raw Event Captured --- Type: {event_type}, Name: {event_name}")

                # --- 核心逻辑：捕获 retrieval 节点结束事件 ---
                if event_type == "on_chain_end" and event_name == "retrieval":
                    try:
                        output_data = event.get("data", {}).get("output", {})
                        retrieved_docs = output_data.get("context_docs", [])

                        log.info(f"--- [RETRIEVAL] 捕获到检索结果 --- 数量: {len(retrieved_docs)}")
                        if retrieved_docs:
                            # 格式化引用数据
                            sources_data = [
                                {
                                    "id": i + 1,
                                    "content": doc.page_content,
                                    "source": doc.metadata.get("source", "Unknown")
                                }
                                for i, doc in enumerate(retrieved_docs)
                            ]
                            # 发送一个特殊的引用数据包
                            # 注意：这里我们使用一个特殊的 type 来标识
                            ref_data = {
                                "answer": "",
                                "sources": sources_data,
                                "is_end": False,
                                "type": "sources"  # 新增一个 type 字段来区分
                            }
                            yield f"data: {json.dumps(ref_data, ensure_ascii=False)}\n\n"

                    except Exception as e:
                        log.error(f"提取引用失败: {e}")

                # 筛选 LLM 流式 token 事件
                if event_type == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        # chunk 是 AIMessageChunk，有 .content 属性
                        data = {
                            "answer": chunk.content,
                            "sources": [],
                            "is_end": False,
                            "type": "token"
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