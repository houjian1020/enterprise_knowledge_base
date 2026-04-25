#================================================================
# Gradio 界面代码
#================================================================
import gradio as gr
import requests
import os
import json
from app.core.logger import get_logger # 1. 导入我们自定义的日志工具
# 2. 创建一个本模块专用的 log
log = get_logger(__name__)


# 1. 获取后端 API 地址
# 优先读取环境变量，如果没有则使用默认本地地址
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")


def chat_with_knowledge(question, history, tenant_id):
    """
    核心聊天函数（优化流式处理）
    参数：question(用户问题), history(聊天历史), tenant_id(租户ID)
    """
    if not question.strip():
        return "请输入有效的问题"

    payload = {
        "tenant_id": tenant_id,
        "question": question
    }

    try:
        with requests.post(
                f"{API_BASE_URL}/chat",
                json=payload,
                stream=True,
                timeout=120
        ) as response:
            if response.status_code == 200:
                final_answer = ""

                # 逐行读取 SSE
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode("utf-8")

                        # 处理 SSE 格式 (data: {...})
                        if line_str.startswith("data: "):
                            json_str = line_str.replace("data: ", "", 1)
                            try:
                                log.info(f"前端响应内容: {json_str}")

                                data = json.loads(json_str)
                                chunk = data.get("answer", "")
                                is_end = data.get("is_end", False)

                                if chunk:
                                    final_answer += chunk
                                    # 实时 Yield，实现打字机效果
                                    yield final_answer

                                if is_end:
                                    # 结束信号，可以在这里拼接参考资料
                                    sources = data.get("sources", [])
                                    if sources:
                                        source_text = "\n\n---\n**📚 参考资料:**\n" + "\n".join(
                                            [f"- {s}" for s in sources])
                                        yield final_answer + source_text
                                    break

                            except json.JSONDecodeError:
                                continue
            else:
                yield f"❌ 后端错误: {response.status_code} {response.text}"

    except Exception as e:
        yield f"❌ 连接失败: {str(e)}"

def build_ui():
    """
    构建 Gradio 界面
    """
    # 使用 Gradio 内置的柔和主题
    with gr.Blocks(title="企业级知识库助手") as demo:
        # --- 顶部标题区 ---
        gr.Markdown("""
        # 🏢 企业级知识库问答系统
        请选择租户，上传文档后，即可进行智能问答。
        """)

        # --- 侧边栏配置区 ---
        with gr.Accordion("⚙️ 租户配置", open=True):
            tenant_id_input = gr.Textbox(
                label="租户 ID",
                value="tenant_A",
                placeholder="请输入租户ID，例如 tenant_A",
                info="不同租户的数据是物理隔离的"
            )

        # --- 核心聊天区 ---
        # ChatInterface 是 Gradio 专为聊天设计的组件
        chatbot = gr.ChatInterface(
            fn=chat_with_knowledge,
            additional_inputs=[tenant_id_input],  # 将租户ID作为附加输入传给函数
            title="💬 智能问答",
            description="输入你的问题，AI 将基于知识库回答",
            examples=[
                ["你好，介绍一下你自己", "tenant_A"],
                ["文档里主要讲了什么？", "tenant_A"],
                ["请总结一下核心观点", "tenant_B"]
            ],
            cache_examples=False,
        )

        # --- 底部状态栏 ---
        gr.Markdown("---")
        status_text = gr.Markdown("状态: 就绪")

    return demo


# 启动入口
if __name__ == "__main__":
    demo = build_ui()
    # 启动服务
    # share=True 会生成一个临时的公网链接，方便演示给客户看
    # 终端启动方式：python -m app.frontend.gradio_app
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, theme="soft")