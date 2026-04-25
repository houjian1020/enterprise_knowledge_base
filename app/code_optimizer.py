from openai import OpenAI
import os

# ===================== 你的配置（直接用）=====================
client = OpenAI(
    base_url="https://api.siliconflow.cn/v1",
    api_key="sk-kjnznehqqqebwxtljphrgdgtaxvvwblaiegywfxtqqvalfwu"
)

# =====================【你只需要改这里！】=====================
# 1. 要优化的文件路径（直接复制粘贴）
FILE_PATH = r"D:\HJ\PythonProject\enterprise_knowledge_base\app\api\routes.py"

# 2. 要优化的 函数名 / 接口名
TARGET_FUNCTION = "chat"  # 你想优化哪个方法/接口
# ===================================================================

def read_file(file_path):
    """读取文件内容"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def optimize_code(file_content, func_name):
    """让AI优化指定方法/接口"""
    prompt = f"""
你是专业Python工程师。

我需要你：
1. 从下面代码中，找到 **{func_name}** 这个函数/接口
2. 只优化这个函数，不要改动其他代码
3. 优化方向：
   - 代码规范
   - 性能提升
   - 增加注释
   - 异常处理
   - 类型注解
   - 可维护性

输出要求：
- 只返回 **优化后的完整代码**
- 不要解释
- 不要多余内容

代码如下：
{file_content}
"""

    response = client.chat.completions.create(
        model="Qwen/Qwen3-Coder-30B-A3B-Instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ===================== 主执行 =====================
if __name__ == "__main__":
    print(f"正在读取文件：{FILE_PATH}")
    code = read_file(FILE_PATH)

    print(f"正在优化函数：{TARGET_FUNCTION}...\n")
    optimized_code = optimize_code(code, TARGET_FUNCTION)

    # 输出结果
    print("=" * 30 + " 优化完成 " + "=" * 30)
    print(optimized_code)