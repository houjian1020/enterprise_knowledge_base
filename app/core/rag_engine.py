#================================================================
# RAG 引擎类 (加载索引、检索、写入)
#================================================================

import os
import shutil
from typing import List, Optional

# LangChain 相关组件
from langchain_community.vectorstores import FAISS
from langchain_core.messages import BaseMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

# 引入配置
from app.config import settings

from app.core.logger import get_logger # 1. 导入我们自定义的日志工具

# 2. 创建一个本模块专用的 log
log = get_logger(__name__)

class RagEngine:
    def __init__(self, tenant_id: str):
        """
        初始化 RAG 引擎
        :param tenant_id: 租户ID，用于隔离数据
        """

        # 定义租户ID
        self.tenant_id = tenant_id

        # 定义存储路径
        self.base_path = os.path.join(settings.STORAGE_BASE_PATH, tenant_id)  # 租户目录
        self.files_path = f"{self.base_path}/files" # 原始文件
        self.index_path = f"{self.base_path}/index" # 索引文件

        # 1. 确保目录 files_path index_path 存在
        os.makedirs(self.files_path, exist_ok=True)
        os.makedirs(self.index_path, exist_ok=True)

        # from modelscope import snapshot_download
        # snapshot_download(settings.EMBEDDING_MODEL_NAME, cache_dir="D:\HJ\PythonProject\Local_model")

        # 2. 初始化 Embedding 模型 (使用 sentence-transformers 的轻量级模型，适合演示)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL_NAME,
            model_kwargs={'device': 'cpu'},  # 如果有GPU可改为 'cuda'
            encode_kwargs={'normalize_embeddings': False}
        )

        # 3. 初始化文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,  # 每个切片500字符
            chunk_overlap=settings.CHUNK_OVERLAP  # 重叠50字符，保持上下文连贯
        )
        log.info(f"为租户 {tenant_id} 初始化 RAG 引擎")


    def load_vector_store(self)-> Optional[FAISS]:
        """
        加载当前租户的本地向量库 到 内存
        :return: FAISS 实例，如果不存在则返回 None
        """

        # 检查租户文件是否存在
        if not os.path.exists(self.files_path) or not os.path.exists(self.index_path):
            return None

        try:
            # 把硬盘里的向量库 → 读回内存使用
            return FAISS.load_local(
                self.index_path,        # 本地向量库的文件夹路径
                self.embeddings,        # 嵌入向量模型
                allow_dangerous_deserialization=True # 允许危险的反序列化（安全开关）
            )
        except Exception as e:
            log.error(f"加载向量库失败: {e}", exc_info=True)
            return None


    def add_document(self, file_path:str, filename:str)->bool:
        """
        添加文档并更新向量库
        :param file_path: 文件在服务器上的绝对路径
        :param filename: 原始文件名
        :return: 是否成功
        """

        try:
            # TODO 1. 读取文件内容 (这里简单处理，只读取文本，实际项目需处理PDF/Word)
            # 演示项目暂且只支持 .txt 和 .md，后续可扩展
            content = ""
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 2. 文本分割,并保存到Document列表
            texts = self.text_splitter.split_text(content)
            documents = [Document(page_content=t, metadata={"source": filename}) for t in texts]

            # 3. 创建或更新向量库
            # 把硬盘里的向量库 → 读回内存使用
            vector_store = self.load_vector_store()

            if vector_store:
                # 往已有的向量库里追加文档: 把文档向量化 → 存入内存
                vector_store.add_documents(documents)
            else:
                # 新建库: 把文档向量化 → 存入内存
                vector_store = FAISS.from_documents(documents,self.embeddings)

            # 4. 把内存里的向量库 → 保存到硬盘
            vector_store.save_local(self.index_path)

            return True
        except Exception as e:
            log.error(f"处理文档失败: {e}")
            return False


    def search(self,query:str,k:int = settings.TOP_K)->List[Document]:
        """
        检索相关文档
        :param query: 用户问题
        :param k: 返回前K个最相关的片段
        :return: 文档列表
        """
        vector_store = self.load_vector_store()
        if not vector_store:
            return []

        # TODO 后续可以改造为： 混合检索+重排序
        docs = vector_store.similarity_search(query, k=k)
        return docs