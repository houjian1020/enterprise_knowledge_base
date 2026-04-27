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

# ==========================================
# 后端交互函数
# ==========================================

def upload_file(files, tenant_id):
    """
    支持多文件上传
    files: 在 Gradio 中，当 file_count="multiple" 时，
           传入的通常是一个包含文件路径字符串的列表，或者是 FileData 对象列表。
    """
    # 1. 基础校验
    if not files:
        return "⚠️ 请选择文件", None  # 【修复点】：返回两个值，第二个设为 None 清空输入框

    # 2. 兼容处理：确保 file_list 是一个列表
    # 如果是单个文件（字符串），转为列表；如果是列表则直接用
    file_list = files if isinstance(files, list) else [files]

    results = []

    # 3. 循环处理每个文件
    for file_path in file_list:
        try:
            # 兼容 FileData 对象的情况（Gradio 新版本可能传对象而不是纯字符串路径）
            if hasattr(file_path, 'path'):
                actual_path = file_path.path
            else:
                actual_path = file_path

            # 打开文件并发送给后端
            with open(actual_path, "rb") as f:
                # 注意：requests.files 接受字典，键是字段名，值是文件对象
                files_payload = {"file": f}
                data_payload = {"tenant_id": tenant_id}

                response = requests.post(f"{API_BASE_URL}/upload", files=files_payload, data=data_payload)

                if response.status_code == 200:
                    results.append(f"✅ {os.path.basename(actual_path)}")
                else:
                    results.append(f"❌ {os.path.basename(actual_path)}: {response.text}")

        except Exception as e:
            results.append(f"❌ {os.path.basename(str(file_path))}: {str(e)}")

    return "\n".join(results), None

# [新增] 定义获取文件列表的函数
def get_file_list(tenant_id):
    """获取指定租户下的所有文件名"""
    import os
    ABS_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 获取项目根目录
    files_dir = os.path.join(ABS_PATH, "storage", tenant_id, "files")

    log.info(f"绝对路径：{files_dir}")

    if not os.path.exists(files_dir):
        return []
    return [f for f in os.listdir(files_dir) if os.path.isfile(os.path.join(files_dir, f))]


# [新增] 定义删除文件的函数
def delete_selected_file(filename, tenant_id):
    """调用 API 删除文件"""
    try:
        # 调用后端 API
        url = f"{API_BASE_URL}/upload"
        data = {"tenant_id": tenant_id}
        # 注意：Gradio 的 requests 调用可能需要处理路径问题，这里直接用 requests 库
        import requests
        response = requests.delete(url, params={"filename": filename}, data=data)

        if response.status_code == 200:
            # 删除成功后，刷新文件列表
            new_list = get_file_list(tenant_id)
            return f"✅ 已删除: {filename}", gr.Dropdown(choices=new_list, value=None)
        else:
            return f"❌ 删除失败: {response.text}", gr.Dropdown()
    except Exception as e:
        return f"❌ 异常: {str(e)}", gr.Dropdown()



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


# ==========================================
# 界面构建
# ==========================================

def build_ui():
    with gr.Blocks(title="企业级知识库助手") as demo:
        gr.Markdown("### 🏢 企业级知识库 RAG 系统")

        # 状态组件：存储当前选中的文件名（用于删除）
        selected_filename_state = gr.State("")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("#### ⚙️ 1. 租户配置与上传")
                tenant_id_input = gr.Textbox(label="租户 ID", value="tenant_A", placeholder="请输入租户ID")

                # 【修改点 2】：支持多文件上传
                file_input = gr.File(
                    label="上传文档 (支持多选)",
                    type="filepath",
                    file_count="multiple",  # 关键参数：允许多选
                    file_types=[".pdf", ".doc", ".docx", ".txt", ".md"]
                )
                upload_btn = gr.Button("📤 批量上传", variant="primary")

                gr.Markdown("#### 📂 2. 文件管理")
                # 使用 Dataframe 展示，完整显示文件名，支持横向滚动
                # interactive=False 表示只读
                file_list_df = gr.Dataframe(
                    headers=["文件名"],
                    label="已上传文件列表 (点击选中)",
                    interactive=False,
                    wrap=True,  # 允许长文件名换行
                )

                delete_btn = gr.Button(
                    "🗑️ 删除选中文件",
                    variant="stop",
                )

            with gr.Column(scale=2):
                gr.Markdown("#### 💬 3. 智能问答")
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
                    cache_examples=False
                )

        # 状态显示
        status_text = gr.Markdown("状态: 就绪")

        # ==========================================
        # 事件绑定逻辑
        # ==========================================

        # 1. 上传逻辑
        upload_btn.click(
            fn=upload_file,
            inputs=[file_input, tenant_id_input],
            outputs=[status_text, file_input]
        ).then(
            fn=get_file_list,
            inputs=tenant_id_input,
            outputs=file_list_df
        )

        # 2. 监听表格点击事件 -> 更新 State 中的文件名
        def on_table_select(evt: gr.SelectData):
            """
            标准的 Gradio SelectData 处理
            evt.value 直接包含选中单元格的文本
            """
            # 调试：打印原始事件（可选，为了看清楚结构）
            # log.info(f"👆 原始事件: {evt}")

            if evt.value is not None:
                # evt.value 就是文件名（例如 'read.txt'）
                filename = evt.value
                log.info(f"✅ 成功捕获文件名: {filename}")
                return filename

            log.warning("⚠️ evt.value 为空")
            return ""

        # 3. 绑定表格点击事件
        # 注意：inputs 列表里不需要再放 file_list_df 了，因为我们直接从 evt 里取数据
        file_list_df.select(
            fn=on_table_select,
            inputs=None,  # 改为 None，因为我们直接从 evt 拿数据
            outputs=[selected_filename_state]
        )

        # 4. 删除逻辑
        def delete_file_action(selected_filename, tenant_id):
            log.info(f"🗑️ 删除函数被调用，State值: '{selected_filename}', 租户: {tenant_id}")

            # 这里的判断逻辑没问题
            if not selected_filename:
                return "⚠️ 请先在列表中点击选择一个文件", get_file_list(tenant_id)

            try:
                url = f"{API_BASE_URL}/upload"
                response = requests.delete(url, params={"filename": selected_filename}, data={"tenant_id": tenant_id})

                if response.status_code == 200:
                    log.info(f"✅ 删除成功: {selected_filename}")
                    return f"✅ 已删除: {selected_filename}", get_file_list(tenant_id)
                else:
                    log.error(f"❌ 删除失败: {response.text}")
                    return f"❌ 删除失败: {response.text}", get_file_list(tenant_id)
            except Exception as e:
                log.error(f"❌ 异常: {str(e)}")
                return f"❌ 异常: {str(e)}", get_file_list(tenant_id)

        # 5. 绑定删除按钮
        delete_btn.click(
            fn=delete_file_action,
            inputs=[selected_filename_state, tenant_id_input],  # <--- 这里依赖 State
            outputs=[status_text, file_list_df]
        )

        # 4. 页面加载和租户切换刷新
        def refresh_list(tenant_id):
            return get_file_list(tenant_id)

        demo.load(
            fn=refresh_list,
            inputs=tenant_id_input,
            outputs=[file_list_df]
        )

        tenant_id_input.change(
            fn=refresh_list,
            inputs=tenant_id_input,
            outputs=[file_list_df]
        )

    return demo

# 启动入口
if __name__ == "__main__":
    demo = build_ui()
    # 启动服务
    # share=True 会生成一个临时的公网链接，方便演示给客户看
    # 终端启动方式：python -m app.frontend.gradio_app
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, theme="soft")