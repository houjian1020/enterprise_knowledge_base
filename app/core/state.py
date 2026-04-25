#================================================================
# 工作流的数据载体
#================================================================
from typing import List, Annotated, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
import operator

# 聚合操作： 合并列表（例如合并多个来源的文档）
def merge_lists(left: List[Any], right: List[Any]) -> List[Any]:
    return left + right

# 定义全局状态
class AgentState(Dict):
    # 租户ID
    tenant_id: str

    # 用户问题：当前轮次的输入
    question: str

    # 历史对话： LangGraph会自动管理消息历史
    messages: Annotated[List[BaseMessage], operator.add]

    # 检索到的上下文文档：由检索节点写入， 生成节点读取
    context_docs: List[Any] = []

    # 最终生成的回答: 由生成节点写入
    answer: str

    # 错误信息：用于前端展示错误
    error: str
