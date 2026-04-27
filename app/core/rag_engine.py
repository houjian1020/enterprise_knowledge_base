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
from langchain_community.document_loaders import ( # 请添加到文件顶部的 import 区域
    TextLoader,
    UnstructuredPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredMarkdownLoader
)

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

        # 检查租户索引文件是否存在
        # FAISS 会生成 index.faiss 和 index.pkl 两个文件
        index_file = os.path.join(self.index_path, "index.faiss")

        # 如果索引文件不存在，直接返回 None，不报错
        if not os.path.exists(index_file):
            log.info(f"未找到向量索引文件: {index_file}，将创建新库。")
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
            # 1. 读取文件内容 (PDF/Word/txt)
            # 1. 根据文件扩展名选择加载器 ===
            file_extension = os.path.splitext(filename.lower())[1]

            # 2. 文本分割,并保存到Document列表
            loader = None

            if file_extension == ".pdf":
                loader = UnstructuredPDFLoader(file_path)
            elif file_extension in [".doc", ".docx"]:
                loader = UnstructuredWordDocumentLoader(file_path)
            elif file_extension == ".md":
                loader = UnstructuredMarkdownLoader(file_path)
            elif file_extension == ".txt":
                loader = TextLoader(file_path, encoding="utf-8")
            else:
                log.error(f"不支持的文件格式: {file_extension}")
                return False

            # 使用加载器读取文档
            documents = loader.load()

            # [变更] 使用文本分割器切分 Document 对象，而不是字符串
            split_docs = self.text_splitter.split_documents(documents)

            # 3. 创建或更新向量库
            # 把硬盘里的向量库 → 读回内存使用
            vector_store = self.load_vector_store()

            if vector_store:
                # 往已有的向量库里追加文档: 把文档向量化 → 存入内存
                vector_store.add_documents(split_docs)
            else:
                # 新建库: 把文档向量化 → 存入内存
                vector_store = FAISS.from_documents(split_docs,self.embeddings)

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