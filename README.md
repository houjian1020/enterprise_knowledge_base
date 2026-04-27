# 项目文档

1.项目架构：
enterprise_knowledge_base/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI 入口
│   ├── config.py          # 全局配置 (路径、模型参数)
│   ├── core/              # 【核心业务逻辑层】
│   │   ├── __init__.py
│   │   ├── rag_engine.py  # RAG 引擎类 (加载索引、检索、写入)
│   │   ├── graph.py       # LangGraph 工作流定义
│   │   ├── nodes.py       # LangGraph 节点逻辑 (检索器、生成器)
│   │   └── utils.py       # 工具函数 (文件处理、Embedding加载)
│   │   └── logger.py      # 日志管理
│   ├── api/               # 【接口层】
│   │   ├── __init__.py
│   │   ├── schemas.py     # Pydantic 模型 (请求/响应定义)
│   │   └── routes.py      # API 路由 (上传、聊天)
│   └── frontend/          # 【前端展示层】
│       ├── __init__.py
│       └── gradio_app.py  # Gradio 界面代码
├── storage/               # 【数据持久化层】(Git忽略)
│   ├── tenant_A/          # 租户A的数据
│   │   ├── files/         # 原始PDF/MD文件
│   │   └── index/         # FAISS 索引文件
│   └── tenant_B/          # 租户B的数据
│       ├── files/
│       └── index/
├── requirements.txt       # 依赖列表
├── Dockerfile             # 容器构建文件
├── docker-compose.yml     # 编排文件
└── README.md              # 项目文档




=================================待优化内容=================================
由 TODO 标注

第一步（当前任务）：补充 Gradio 前端缺少的文件上传功能，并打通上传流程。
第二步：后端支持 PDF、Word、Markdown 等多格式解析。
文件相关的问题还没结束，文件删除没有做相关的删除接口，接口逻辑是要删除原文件和索引文件，请给出先关的前后端代码


第三步：完善全局异常处理与友好的 Toast 提示。
后续步骤：依次完成 引用溯源、多轮对话、前端美化 和 部署上线。
