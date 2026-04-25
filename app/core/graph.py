#================================================================
# LangGraph 工作流定义
#================================================================
import os
from typing import List
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage,BaseMessageChunk
from langchain_core.runnables import RunnableConfig # 1. 导入配置类型
# 导入我们之前定义的 State
from app.core.state import AgentState
from app.core.logger import get_logger # 1. 导入我们自定义的日志工具
from dotenv import load_dotenv

#加载环境变量
load_dotenv()

# 2. 创建一个本模块专用的 log
log = get_logger(__name__)

# 初始化大模型
llm = ChatOpenAI(
    model="qwen-plus",  # 你正在用的模型
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    streaming=True,     # 开启流式模式
    temperature=0.7
)

def retrieval_node(state: AgentState):
    """
    检索节点：根据问题去向量库找资料
    """
    log.info(f"--- 正在为租户 {state['tenant_id']} 检索资料 ---")

    # 这里我们需要动态导入 RagEngine，避免循环引用
    from app.core.rag_engine import RagEngine

    engine = RagEngine(tenant_id=state['tenant_id'])
    docs = engine.search(query=state['question'])

    # 将检索到的文档存入状态
    state['context_docs'] = docs
    return state


async def generation_node(state: AgentState, config: RunnableConfig):
    """
    生成节点：结合资料和用户问题，生成最终回答
    """
    log.info("--- 正在生成回答 ---")

    # 1. 安全地整理上下文
    # 使用 try-except 包裹，防止因为 context_docs 缺失或为空导致崩溃
    context_text = ""
    try:
        # 如果 state['context_docs'] 存在且有内容
        if state.get('context_docs'):
            context_text = "\n\n".join([doc.page_content for doc in state['context_docs']])
            log.info(f"找到参考资料，长度: {len(context_text)}")
        else:
            log.warning("未找到参考资料 (context_docs 为空)")
    except Exception as e:
        log.error(f"整理上下文出错: {e}")

    # 2. 构建提示词
    # 根据有没有资料，动态调整提示词
    if context_text:
        prompt = f"""
        你是一个智能助手。请根据以下参考资料回答用户的问题。

        参考资料：
        {context_text}

        用户问题：{state['question']}

        如果参考资料里没有答案，请如实告知。
        """
    else:
        # 如果没有资料，直接让 LLM 用自己的知识回答
        prompt = f"""
        你是一个智能助手。由于知识库中暂时没有相关文档，请你利用自己的通用知识回答用户的问题。

        用户问题：{state['question']}
        """
        log.info("使用通用模式回答（无参考资料）")

    # 3. 调用 LLM
    try:
        chunks = []
        # 异步流式调用 LLM 逐块生成内容
        # 只有传了 config，LangGraph 才能监听到内部的事件
        async for chunk in llm.astream([HumanMessage(content=prompt)], config=config):
            if chunk.content:
                log.info(f"--- 流式生成内容 --- {chunk.content}")
                chunks.append(chunk.content)
        full_text = "".join(chunks)
        # full_text = llm.invoke([HumanMessage(content=prompt)], config=config).content
        return {"messages": [AIMessage(content=full_text)]}
    except Exception as e:
        log.error(f"LLM 调用失败: {e}")
        return {"messages": [AIMessage(content="抱歉，系统内部出现错误。")]}
    finally:
        log.info("--- 回答生成完成 ---")



def build_graph():
    """
    构建 LangGraph 流程图
    """
    builder = StateGraph(AgentState)

    # 添加节点
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("generation", generation_node)

    # 定义边的连接关系
    # 1. 从开始节点进入检索节点
    builder.add_edge(START, "retrieval")
    # 2. 检索完成后进入生成节点
    builder.add_edge("retrieval", "generation")
    # 3. 生成完成后结束
    builder.add_edge("generation", END)

    return builder.compile()

# 编译好的图，供外部调用
rag_graph = build_graph()