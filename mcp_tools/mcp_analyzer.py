import subprocess
import sys
import os
import requests
import json

# ================= 配置区 =================
# 建议通过环境变量获取 API KEY
API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_ACTUAL_API_KEY")
MODEL_NAME = "gemini-2.5-flash"
AI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"

def run_gdb(binary, core):
    """
    针对 Gemini 2.5 的超大上下文能力，我们可以抓取更丰富的现场数据
    """
    try:
        # 1. 抓取堆栈：Gemini 2.5 处理长文本能力极强，我们取前 100 层
        bt_cmd = ["gdb", "-batch", "-ex", "bt 100", "-ex", "echo \n... [TRUNCATED] ...\n", "-ex", "bt -10", binary, core]
        bt_raw = subprocess.check_output(bt_cmd, stderr=subprocess.STDOUT).decode('utf-8', 'ignore')

        # 2. 抓取完整的变量信息、寄存器和反汇编崩溃指令
        info_cmd = ["gdb", "-batch", "-ex", "info registers", "-ex", "info locals", "-ex", "disassemble /m", binary, core]
        info_raw = subprocess.check_output(info_cmd, stderr=subprocess.STDOUT).decode('utf-8', 'ignore')

        # 3. 提取源码上下文 (崩溃点附近 50 行)
        src_cmd = ["gdb", "-batch", "-ex", "list 1,50", binary, core]
        src_raw = subprocess.check_output(src_cmd, stderr=subprocess.STDOUT).decode('utf-8', 'ignore')

        return bt_raw, info_raw, src_raw
    except Exception as e:
        return f"GDB Error: {str(e)}", "", ""

def get_ai_insight(bt, info, src, exe_name):
    """
    使用 Gemini 2.5 强大的推理能力进行全量诊断
    """
    prompt = f"""
    [SYSTEM] You are an elite Linux C++ stability engineer. Analyze the crash for: {exe_name}.

    [CONTEXT DATA]
    STACK: {bt}
    REGS & LOCALS & ASM: {info}
    SOURCE: {src}

    [OBJECTIVE]
    1. Direct Cause: Tell me exactly why it crashed (Signal name & description).
    2. Deep Logic Analysis: Explain the memory/logic error (e.g., recursive depth, off-by-one, etc.).
    3. Source Fix: Provide the corrected C/C++ code.

    [STRICT OUTPUT FORMAT]
    Return ONLY a raw JSON object with these keys:
    "root_cause", "location", "explanation", "fix_code", "prevention"
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}
        ],
        "generationConfig": {
            "response_mime_type": "application/json", # 强制 JSON 输出模式
            "temperature": 0.05
        }
    }

    try:
        # Gemini 2.5 处理能力很强，但建议设置合理的超时
        response = requests.post(AI_URL, json=payload, timeout=60)
        res_json = response.json()

        if 'candidates' not in res_json:
            print(f"DEBUG: API Error -> {json.dumps(res_json)}", file=sys.stderr)
            return {
                "root_cause": "Gemini 2.5 API Error",
                "location": "N/A",
                "explanation": f"Failed to get candidates. Message: {res_json.get('error', {}).get('message', 'Check logs')}",
                "fix_code": "// Check Gemini API quota and network.",
                "prevention": "Check API key and internet access."
            }

        content = res_json['candidates'][0]['content']['parts'][0]['text']
        return json.loads(content)
    except Exception as e:
        return {
            "root_cause": "Python Exception",
            "explanation": f"Script error: {str(e)}",
            "location": "N/A", "fix_code": "// Error", "prevention": "// Error"
        }

def build_html(exe_name, bt, ai):
    """
    利用 Tailwind CSS 生成符合 2.0 时代的现代化诊断界面
    """
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    </head>
    <body class="bg-gray-50 p-8">
        <div class="max-w-6xl mx-auto">
            <div class="bg-white rounded-3xl shadow-xl overflow-hidden mb-8 border border-gray-100">
                <div class="bg-gradient-to-r from-red-600 to-orange-500 p-8 text-white">
                    <div class="flex justify-between items-start">
                        <div>
                            <h1 class="text-4xl font-black tracking-tighter uppercase italic">Crash Insight 2.0</h1>
                            <p class="mt-2 text-red-100 font-mono">Process: {exe_name}</p>
                        </div>
                        <div class="bg-white/20 backdrop-blur-md px-4 py-2 rounded-xl text-sm font-bold border border-white/30">
                            Gemini 2.5 FLASH AI
                        </div>
                    </div>
                </div>

                <div class="p-8 grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div class="space-y-4">
                        <h2 class="text-xs font-bold text-red-500 uppercase tracking-widest leading-none">Root Cause</h2>
                        <p class="text-3xl font-bold text-gray-900 leading-tight">{ai['root_cause']}</p>
                        <p class="text-gray-600 leading-relaxed bg-gray-50 p-4 rounded-2xl border border-gray-100 italic">"{ai['explanation']}"</p>
                    </div>
                    <div class="bg-gray-900 rounded-3xl p-6 text-green-400 shadow-2xl border border-gray-800 relative">
                        <h2 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4">AI Suggested Fix</h2>
                        <pre class="font-mono text-sm leading-relaxed overflow-x-auto">{ai['fix_code']}</pre>
                        <div class="absolute bottom-4 right-6 text-[10px] text-gray-600 font-mono italic">Loc: {ai['location']}</div>
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div class="lg:col-span-2 bg-white p-8 rounded-3xl shadow-sm border border-gray-100">
                    <h3 class="text-xl font-bold text-gray-800 mb-6 flex items-center">
                        <i class="fas fa-microchip mr-3 text-red-500"></i> Original Stack Trace
                    </h3>
                    <pre class="text-[11px] font-mono text-gray-400 leading-tight overflow-x-auto bg-gray-50 p-6 rounded-2xl h-[500px] overflow-y-auto">{bt}</pre>
                </div>
                <div class="space-y-8">
                    <div class="bg-white p-8 rounded-3xl shadow-sm border border-gray-100">
                        <h3 class="text-xl font-bold text-gray-800 mb-4 flex items-center">
                            <i class="fas fa-shield-halved mr-3 text-blue-500"></i> Prevention
                        </h3>
                        <p class="text-gray-600 text-sm leading-relaxed">{ai['prevention']}</p>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(1)

    bin_p, core_p = sys.argv[1], sys.argv[2]
    e_name = os.path.basename(bin_p)

    # 1. 抓取 GDB 数据 (Gemini 2.5 采样更深)
    gdb_bt, gdb_info, gdb_src = run_gdb(bin_p, core_p)

    # 2. 调用 Gemini 2.5 推理
    ai_json = get_ai_insight(gdb_bt, gdb_info, gdb_src, e_name)

    # 3. 输出 HTML
    print(build_html(e_name, gdb_bt, ai_json))