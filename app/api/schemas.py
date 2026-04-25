#================================================================
# Pydantic 模型 (请求/响应定义)
# 定义数据格式（请求什么，返回什么）
#================================================================
from pydantic import BaseModel, Field
from typing import List, Optional


#================================================================
# 请求模型 (客户端发给服务器的数据)
#================================================================
class UploadRequest(BaseModel):
    """文件上传请求（实际上传由 FastAPI 的 UploadFile 处理，这里仅作占位）"""
    pass

class ChatRequest(BaseModel):
    """聊天请求"""
    tenant_id: str = Field(..., description="租户ID，用于隔离数据")
    question: str = Field(..., description="用户的问题")



#================================================================
# 响应模型 (服务器返回给客户端的数据)
#================================================================

class ChatResponse(BaseModel):
    """聊天响应"""
    answer: str = Field(..., description="AI 的回答")
    sources: List[str] = Field(default=[], description="参考文档来源列表")
    tenant_id: str = Field(..., description="当前服务的租户ID")

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    message: str