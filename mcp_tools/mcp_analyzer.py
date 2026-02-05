import subprocess
import sys
import os
import json
from datetime import datetime
import html as html_module

# Import the new AI providers module
from ai_providers import AIAProviderFactory

# ================= Configuration Section =================
# AI provider is automatically detected from AI_PROVIDER environment variable
# Default: google (Gemini) for backward compatibility
# Supported: openai, anthropic, deepseek, google, xai, moonshot, alibaba, tencent


def extract_crash_signal(bt_output):
    """Extract crash signal information from stack trace"""
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
    Fetch GDB analysis data for crash diagnosis
    """
    try:
        # 1. Fetch stack trace (top 100 frames)
        bt_cmd = ["gdb", "-batch", "-ex", "bt 100", "-ex", "echo \n... [TRUNCATED] ...\n", "-ex", "bt -10", binary, core]
        bt_raw = subprocess.check_output(bt_cmd, stderr=subprocess.STDOUT, text=True)

        # 2. Fetch complete variable info, registers and crash disassembly
        info_cmd = ["gdb", "-batch", "-ex", "info registers", "-ex", "info locals", "-ex", "disassemble /m", binary, core]
        try:
            info_raw = subprocess.check_output(info_cmd, stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError:
            reg_cmd = ["gdb", "-batch", "-ex", "info registers", binary, core]
            try:
                info_raw = subprocess.check_output(reg_cmd, stderr=subprocess.STDOUT, text=True)
            except:
                info_raw = "(Register information unavailable)"

        # 3. Extract source context (50 lines around crash point)
        src_cmd = ["gdb", "-batch", "-ex", "list 1,50", binary, core]
        try:
            src_raw = subprocess.check_output(src_cmd, stderr=subprocess.STDOUT, text=True)
        except:
            src_raw = "(Source code not available)"

        return bt_raw, info_raw, src_raw
    except Exception as e:
        return f"GDB Error: {str(e)}", "(Detailed info unavailable)", "(Source unavailable)"


def build_analysis_prompt(exe_name: str, bt: str, info: str, src: str) -> str:
    """
    Build the analysis prompt for AI crash analysis
    """
    return f"""
[SYSTEM] You are an elite Linux C++ stability engineer. Analyze the crash for: {exe_name}.

[CONTEXT DATA]
STACK: {bt[:5000]}
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


def get_ai_insight(bt, info, src, exe_name):
    """
    Use AI model for comprehensive crash diagnosis

    Provider is selected from environment variable AI_PROVIDER
    Default: Google Gemini (for backward compatibility)
    """
    # Create AI client based on configuration
    client = AIAProviderFactory.create_client()

    # Get provider name for logging
    provider_info = AIAProviderFactory.get_provider_info()
    provider = os.getenv('AI_PROVIDER', 'google').lower()
    provider_name = provider_info.get(provider, {}).get('name', 'AI')

    print(f"[*] Using AI provider: {provider_name}", file=sys.stderr)

    # Build prompt
    prompt = build_analysis_prompt(exe_name, bt, info, src)

    # Call AI API
    result = client.analyze(prompt)

    # Add provider info
    result['provider'] = provider_name

    return result


def build_html(exe_name, bt, ai, info, src):
    """
    Generate elegant and modern diagnostic report HTML
    """
    # Extract crash signal information
    signal_name, signal_desc, signal_color = extract_crash_signal(bt)

    # Get provider name
    provider_name = ai.get('provider', 'AI')

    # Safely escape HTML content
    exe_name_safe = html_module.escape(exe_name)
    bt_safe = html_module.escape(bt[:3000])
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
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta http-equiv="Content-Security-Policy" content="default-src *; script-src * 'unsafe-inline' 'unsafe-eval'; style-src * 'unsafe-inline'; img-src * data:;">
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
        .report-container {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
            min-height: 100vh;
            padding: 2rem;
        }}
        .card {{
            background: white;
            border-radius: 1rem;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
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
                        <p class="text-white font-bold text-lg"><i class="fas fa-brain text-blue-400 mr-2"></i>{provider_name}</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Main Analysis Section -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
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
            <div class="bg-white rounded-2xl shadow-xl p-8 border border-gray-100 fade-in" style="animation-delay: 0.4s;">
                <h2 class="text-2xl font-bold text-gray-900 mb-6 flex items-center">
                    <i class="fas fa-shield-halved text-blue-600 mr-3"></i>Prevention Strategies
                </h2>
                <div class="space-y-4 text-gray-700 leading-relaxed">
                    {ai_prevention_safe.replace(chr(10), '<br>').replace('  ', '&nbsp;&nbsp;')}
                </div>
            </div>

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
            <p class="mt-2">AI Provider: {provider_name}</p>
        </div>
    </div>
</body>
</html>"""


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python mcp_analyzer.py <binary_path> <core_dump_path>", file=sys.stderr)
        sys.exit(1)

    bin_p, core_p = sys.argv[1], sys.argv[2]

    # Verify file exists
    if not os.path.exists(bin_p):
        print(f"Error: Binary file not found: {bin_p}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(core_p):
        print(f"Error: Core dump file not found: {core_p}", file=sys.stderr)
        sys.exit(1)

    e_name = os.path.basename(bin_p)

    # 1. Fetch GDB data
    print(f"[*] Analyzing crash for: {e_name}", file=sys.stderr)
    gdb_bt, gdb_info, gdb_src = run_gdb(bin_p, core_p)

    # 2. Call AI for analysis (uses AI_PROVIDER env var)
    print("[*] Requesting AI analysis...", file=sys.stderr)
    ai_json = get_ai_insight(gdb_bt, gdb_info, gdb_src, e_name)

    # 3. Output HTML report
    print("[*] Generating report...", file=sys.stderr)
    html_output = build_html(e_name, gdb_bt, ai_json, gdb_info, gdb_src)

    print(html_output, end='')
    print("[+] Report generation completed", file=sys.stderr)
