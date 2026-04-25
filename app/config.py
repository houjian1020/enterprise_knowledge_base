#================================================================
#定义 环境变量 和 定义全局常量
#================================================================

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    全局配置类
    会自动从 .env 文件中读取变量，如果没有则使用默认值
    """

    # --- 项目基础配置 ---
    PROJECT_NAME: str = "企业知识库系统"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    # 接口地址
    API_BASE_URL: str = "http://127.0.0.1:8000/api/v1"

    # --- 存储路径配置 ---
    # 基础存储目录，所有租户数据都存在这下面
    STORAGE_BASE_PATH: str = "./storage"

    # --- 模型配置 ---
    # Embedding 模型名称 (HuggingFace)
    EMBEDDING_MODEL_NAME: str = r"D:\HJ\PythonProject\Local_model\sentence-transformers\all-MiniLM-L6-v2"

    # --- 检索配置 ---
    TOP_K: int = 3  # 默认检索前3个片段
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # --- 模型配置 ---
    DASHSCOPE_API_KEY:str = ""
    DASHSCOPE_BASE_URL:str = ""

    # ================================================================
    # settings.STORAGE_BASE_PATH 自动读取 .env 中的值
    # .env 文件的优先级更高
    # ================================================================
    class Config:
        # 指定从 .env 文件读取  :
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    单例模式获取配置
    使用 lru_cache 确保配置只加载一次，提高性能
    """
    return Settings()


# 实例化配置对象，方便其他文件直接 import
settings = get_settings()