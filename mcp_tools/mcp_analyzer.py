import subprocess
import sys
import os
import requests
import json
from datetime import datetime
import re
import html as html_module

# ================= 配置区 =================
# 建议通过环境变量获取 API KEY
API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_ACTUAL_API_KEY")
MODEL_NAME = "gemini-2.5-flash"
AI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"

def extract_crash_signal(bt_output):
    """从堆栈跟踪中提取崩溃信号信息"""
    signals = {
        'SIGSEGV': ('Segmentation Fault', '#e74c3c'),
        'SIGABRT': ('Abnormal Termination', '#e67e22'),
        'SIGFPE': ('Floating Point Exception', '#f39c12'),
        'SIGILL': ('Illegal Instruction', '#c0392b'),
        'SIGBUS': ('Bus Error', '#8e44ad'),
    }

    for sig, (desc, color) in signals.items():
        if sig in bt_output:
            return sig, desc, color
    return 'UNKNOWN', 'Unknown Signal', '#95a5a6'

def run_gdb(binary, core):
    """
    针对 Gemini 2.5 的超大上下文能力，我们可以抓取更丰富的现场数据
    """
    try:
        # 1. 抓取堆栈：Gemini 2.5 处理长文本能力极强，我们取前 100 层
        bt_cmd = ["gdb", "-batch", "-ex", "bt 100", "-ex", "echo \n... [TRUNCATED] ...\n", "-ex", "bt -10", binary, core]
        bt_raw = subprocess.check_output(bt_cmd, stderr=subprocess.STDOUT, text=True)

        # 2. 抓取完整的变量信息、寄存器和反汇编崩溃指令
        info_cmd = ["gdb", "-batch", "-ex", "info registers", "-ex", "info locals", "-ex", "disassemble /m", binary, core]
        try:
            info_raw = subprocess.check_output(info_cmd, stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError:
            # 即使命令失败，也尝试提取寄存器信息
            reg_cmd = ["gdb", "-batch", "-ex", "info registers", binary, core]
            try:
                info_raw = subprocess.check_output(reg_cmd, stderr=subprocess.STDOUT, text=True)
            except:
                info_raw = "(Register information unavailable)"

        # 3. 提取源码上下文 (崩溃点附近 50 行)
        src_cmd = ["gdb", "-batch", "-ex", "list 1,50", binary, core]
        try:
            src_raw = subprocess.check_output(src_cmd, stderr=subprocess.STDOUT, text=True)
        except:
            src_raw = "(Source code not available)"

        return bt_raw, info_raw, src_raw
    except Exception as e:
        return f"GDB Error: {str(e)}", "(Detailed info unavailable)", "(Source unavailable)"

def get_ai_insight(bt, info, src, exe_name):
    """
    使用 Gemini 2.5 强大的推理能力进行全量诊断
    """
    prompt = f"""
    [SYSTEM] You are an elite Linux C++ stability engineer. Analyze the crash for: {exe_name}.

    [CONTEXT DATA]
    STACK: {bt[:5000]}  # 限制输入长度
    REGS & LOCALS & ASM: {info[:3000]}
    SOURCE: {src[:2000]}

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
            "response_mime_type": "application/json",
            "temperature": 0.05
        }
    }

    try:
        response = requests.post(AI_URL, json=payload, timeout=60)
        res_json = response.json()

        if 'candidates' not in res_json:
            error_msg = res_json.get('error', {}).get('message', 'Unknown error')
            print(f"DEBUG: API Error -> {error_msg}", file=sys.stderr)
            return {
                "root_cause": "Analysis Pending",
                "location": "N/A",
                "explanation": "API analysis not available. Please check your Gemini API key and quota.",
                "fix_code": "# Analyze the stack trace above for potential issues",
                "prevention": "Enable memory sanitizers and use safe C++ practices."
            }

        content = res_json['candidates'][0]['content']['parts'][0]['text']
        result = json.loads(content)

        # 验证必要的字段
        required_fields = ["root_cause", "location", "explanation", "fix_code", "prevention"]
        for field in required_fields:
            if field not in result:
                result[field] = f"(Unable to determine {field})"

        return result
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {str(e)}", file=sys.stderr)
        return {
            "root_cause": "Parse Error",
            "explanation": "Failed to parse AI response",
            "location": "N/A",
            "fix_code": "# Check logs for details",
            "prevention": "Retry analysis"
        }
    except Exception as e:
        return {
            "root_cause": "System Error",
            "explanation": f"Analysis failed: {str(e)}",
            "location": "N/A",
            "fix_code": "# Manual analysis required",
            "prevention": "Check network and API configuration"
        }

def build_html(exe_name, bt, ai, info, src):
    """
    生成优雅美观的现代化诊断报告 HTML
    """
    # 提取崩溃信号信息
    signal_name, signal_desc, signal_color = extract_crash_signal(bt)

    # 安全转义 HTML 内容
    exe_name_safe = html_module.escape(exe_name)
    bt_safe = html_module.escape(bt[:3000])  # 限制输出长度
    ai_root_cause_safe = html_module.escape(str(ai.get('root_cause', 'Unknown')))
    ai_explanation_safe = html_module.escape(str(ai.get('explanation', '')))
    ai_fix_code_safe = html_module.escape(str(ai.get('fix_code', '')))
    ai_prevention_safe = html_module.escape(str(ai.get('prevention', '')))
    ai_location_safe = html_module.escape(str(ai.get('location', 'N/A')))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crash Analysis Report - {exe_name_safe}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --signal-color: {signal_color};
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif;
        }}
        .code-block {{
            background: #1e293b;
            color: #e2e8f0;
            border-radius: 12px;
            padding: 16px;
            overflow-x: auto;
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.5;
        }}
        .signal-badge {{
            background: var(--signal-color);
        }}
        .collapsible-section {{
            transition: all 0.3s ease;
        }}
        .stack-trace {{
            max-height: 500px;
            overflow-y: auto;
        }}
        .fade-in {{
            animation: fadeIn 0.5s ease-in;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .highlight-line {{
            background: rgba(248, 113, 113, 0.1);
            border-left: 3px solid #f87171;
            padding-left: 12px;
        }}
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
    </style>
</head>
<body class="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 min-h-screen">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- Header Card -->
        <div class="bg-white rounded-2xl shadow-2xl overflow-hidden mb-8 fade-in border border-gray-100">
            <div class="bg-gradient-to-r from-slate-900 to-slate-800 p-8 text-white">
                <div class="flex justify-between items-start gap-8 flex-wrap">
                    <div class="flex-1 min-w-0">
                        <h1 class="text-5xl font-black tracking-tight mb-2">
                            <i class="fas fa-triangle-exclamation text-red-500 mr-3"></i>Crash Analysis
                        </h1>
                        <p class="text-slate-300 text-lg font-mono mb-4">{exe_name_safe}</p>
                        <div class="flex items-center gap-4 flex-wrap">
                            <span class="inline-flex items-center px-4 py-2 rounded-full signal-badge text-white font-bold text-lg">
                                <i class="fas fa-exclamation-circle mr-2"></i>{signal_name}
                            </span>
                            <span class="text-slate-400 text-sm font-mono">{timestamp}</span>
                        </div>
                    </div>
                    <div class="bg-white/10 backdrop-blur-md px-6 py-4 rounded-xl text-right border border-white/20 flex-shrink-0">
                        <p class="text-sm text-slate-300 mb-2">Powered by</p>
                        <p class="text-white font-bold text-lg"><i class="fas fa-brain text-blue-400 mr-2"></i>Gemini 2.5 AI</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Main Analysis Section -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
            <!-- Root Cause & Explanation (Left: 2 cols) -->
            <div class="lg:col-span-2">
                <div class="bg-white rounded-2xl shadow-xl p-8 border border-gray-100 fade-in" style="animation-delay: 0.1s;">
                    <h2 class="text-2xl font-bold text-gray-900 mb-6 flex items-center">
                        <span class="status-indicator signal-badge"></span>
                        Root Cause Analysis
                    </h2>
                    <div class="mb-6">
                        <h3 class="text-lg font-bold text-gray-800 mb-3 uppercase tracking-wide text-red-600">
                            {signal_desc}
                        </h3>
                        <p class="text-2xl font-bold text-gray-900 leading-relaxed mb-4">
                            {ai_root_cause_safe}
                        </p>
                    </div>
                    <div class="bg-slate-50 rounded-xl p-6 border border-slate-200">
                        <h4 class="font-semibold text-gray-800 mb-3 text-sm uppercase tracking-wide">
                            <i class="fas fa-lightbulb text-amber-500 mr-2"></i>Detailed Explanation
                        </h4>
                        <p class="text-gray-700 leading-relaxed text-base">
                            {ai_explanation_safe}
                        </p>
                    </div>
                </div>
            </div>

            <!-- Quick Info Card (Right: 1 col) -->
            <div class="bg-white rounded-2xl shadow-xl p-8 border border-gray-100 fade-in" style="animation-delay: 0.2s;">
                <h2 class="text-lg font-bold text-gray-900 mb-6 flex items-center">
                    <i class="fas fa-info-circle text-blue-500 mr-3"></i>Quick Info
                </h2>
                <div class="space-y-5">
                    <div class="border-b border-gray-200 pb-4">
                        <p class="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Signal Type</p>
                        <p class="text-lg font-bold text-gray-900">{signal_name}</p>
                        <p class="text-sm text-gray-600 mt-1">{signal_desc}</p>
                    </div>
                    <div class="border-b border-gray-200 pb-4">
                        <p class="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Process Name</p>
                        <p class="text-lg font-bold text-gray-900 font-mono">{exe_name_safe}</p>
                    </div>
                    <div class="border-b border-gray-200 pb-4">
                        <p class="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Crash Location</p>
                        <p class="text-lg font-bold text-gray-900 font-mono text-sm">{ai_location_safe}</p>
                    </div>
                    <div>
                        <p class="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Report Time</p>
                        <p class="text-sm text-gray-700">{timestamp}</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Code Fix Section -->
        <div class="bg-white rounded-2xl shadow-xl p-8 border border-gray-100 mb-8 fade-in" style="animation-delay: 0.3s;">
            <h2 class="text-2xl font-bold text-gray-900 mb-6 flex items-center">
                <i class="fas fa-code text-green-600 mr-3"></i>AI Suggested Fix
            </h2>
            <div class="code-block">
                <pre class="font-mono text-sm leading-relaxed">{ai_fix_code_safe}</pre>
            </div>
            <div class="mt-4 text-xs text-gray-600 font-mono">
                <i class="fas fa-map-marker mr-2"></i>Location: {ai_location_safe}
            </div>
        </div>

        <!-- Prevention & Stack Trace Section -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            <!-- Prevention Strategies -->
            <div class="bg-white rounded-2xl shadow-xl p-8 border border-gray-100 fade-in" style="animation-delay: 0.4s;">
                <h2 class="text-2xl font-bold text-gray-900 mb-6 flex items-center">
                    <i class="fas fa-shield-halved text-blue-600 mr-3"></i>Prevention Strategies
                </h2>
                <div class="space-y-4 text-gray-700 leading-relaxed">
                    {ai_prevention_safe.replace(chr(10), '<br>').replace('  ', '&nbsp;&nbsp;')}
                </div>
            </div>

            <!-- Stack Trace Summary -->
            <div class="bg-white rounded-2xl shadow-xl p-8 border border-gray-100 fade-in" style="animation-delay: 0.5s;">
                <h2 class="text-2xl font-bold text-gray-900 mb-6 flex items-center">
                    <i class="fas fa-layer-group text-purple-600 mr-3"></i>Stack Trace (Summary)
                </h2>
                <div class="code-block stack-trace">
                    <pre>{bt_safe}</pre>
                </div>
                <p class="text-xs text-gray-600 mt-4 italic">
                    <i class="fas fa-info-circle mr-2"></i>Showing first 3000 characters. Full trace available in GDB.
                </p>
            </div>
        </div>

        <!-- Debug Info Section (Collapsible) -->
        <details class="bg-white rounded-2xl shadow-xl border border-gray-100 fade-in" style="animation-delay: 0.6s;">
            <summary class="p-8 cursor-pointer hover:bg-gray-50 transition-colors">
                <h2 class="text-xl font-bold text-gray-900 flex items-center">
                    <i class="fas fa-bug text-orange-600 mr-3"></i>Debug Information
                    <i class="fas fa-chevron-down ml-auto text-gray-600"></i>
                </h2>
            </summary>
            <div class="p-8 border-t border-gray-200">
                <div class="space-y-6">
                    <div>
                        <h3 class="text-lg font-bold text-gray-900 mb-3">Registers & Locals</h3>
                        <div class="code-block max-h-96 overflow-y-auto">
                            <pre class="text-xs">{html_module.escape(info[:2000])}</pre>
                        </div>
                    </div>
                    <div>
                        <h3 class="text-lg font-bold text-gray-900 mb-3">Source Context</h3>
                        <div class="code-block max-h-96 overflow-y-auto">
                            <pre class="text-xs">{html_module.escape(src[:2000])}</pre>
                        </div>
                    </div>
                </div>
            </div>
        </details>

        <!-- Footer -->
        <div class="mt-12 text-center text-gray-500 text-sm">
            <p><i class="fas fa-shield-alt mr-2"></i>Automated Crash Analysis Report - Generated on {timestamp}</p>
            <p class="mt-2">For more information, consult your system administrator or development team.</p>
        </div>
    </div>
</body>
</html>"""

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python mcp_analyzer.py <binary_path> <core_dump_path>", file=sys.stderr)
        sys.exit(1)

    bin_p, core_p = sys.argv[1], sys.argv[2]

    # 验证文件存在
    if not os.path.exists(bin_p):
        print(f"Error: Binary file not found: {bin_p}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(core_p):
        print(f"Error: Core dump file not found: {core_p}", file=sys.stderr)
        sys.exit(1)

    e_name = os.path.basename(bin_p)

    # 1. 抓取 GDB 数据
    print(f"[*] Analyzing crash for: {e_name}", file=sys.stderr)
    gdb_bt, gdb_info, gdb_src = run_gdb(bin_p, core_p)

    # 2. 调用 Gemini 2.5 推理
    print("[*] Requesting AI analysis...", file=sys.stderr)
    ai_json = get_ai_insight(gdb_bt, gdb_info, gdb_src, e_name)

    # 3. 输出 HTML
    print("[*] Generating report...", file=sys.stderr)
    html_output = build_html(e_name, gdb_bt, ai_json, gdb_info, gdb_src)
    print(html_output)
    print("[+] Report generation completed", file=sys.stderr)