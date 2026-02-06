import subprocess
import sys
import os
import json
import shlex
from datetime import datetime
import html as html_module

from ai_providers import AIAProviderFactory


def validate_path(path, allowed_prefixes=None):
    if not path or not isinstance(path, str):
        return False

    try:
        real_path = os.path.realpath(path)
    except (OSError, ValueError):
        return False

    if '..' in path or '~' in path:
        return False

    dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\\']
    if any(char in path for char in dangerous_chars):
        return False

    if allowed_prefixes:
        is_allowed = any(real_path.startswith(prefix) for prefix in allowed_prefixes)
        if not is_allowed:
            return False

    return True


def extract_crash_signal(bt_output):
    signals = {
        'SIGSEGV': ('Segmentation Fault', '#dc2626', 'critical'),
        'SIGABRT': ('Abnormal Termination', '#ea580c', 'high'),
        'SIGFPE': ('Floating Point Exception', '#ca8a04', 'medium'),
        'SIGILL': ('Illegal Instruction', '#dc2626', 'critical'),
        'SIGBUS': ('Bus Error', '#9333ea', 'high'),
    }

    for sig, (desc, color, severity) in signals.items():
        if sig in bt_output:
            return sig, desc, color, severity
    return 'UNKNOWN', 'Unknown Signal', '#6b7280', 'low'


def run_gdb(binary, core):
    allowed_dirs = ['/tmp/cores', '/home/jenkins/codes', '/home/jenkins']

    if not validate_path(binary, allowed_dirs):
        return "SECURITY ERROR: Binary path validation failed", "(Blocked)", "(Blocked)"

    if not validate_path(core, allowed_dirs):
        return "SECURITY ERROR: Core dump path validation failed", "(Blocked)", "(Blocked)"

    binary_quoted = shlex.quote(binary)
    core_quoted = shlex.quote(core)

    try:
        bt_cmd = ["gdb", "-batch", "-ex", "bt 100", "-ex", "echo \n... [TRUNCATED] ...\n", "-ex", "bt -10",
                  binary, core]
        bt_raw = subprocess.check_output(bt_cmd, stderr=subprocess.STDOUT, text=True)

        info_cmd = ["gdb", "-batch", "-ex", "info registers", "-ex", "info locals", "-ex", "disassemble /m",
                    binary, core]
        try:
            info_raw = subprocess.check_output(info_cmd, stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError:
            reg_cmd = ["gdb", "-batch", "-ex", "info registers", binary, core]
            try:
                info_raw = subprocess.check_output(reg_cmd, stderr=subprocess.STDOUT, text=True)
            except:
                info_raw = "(Register information unavailable)"

        src_cmd = ["gdb", "-batch", "-ex", "list 1,50", binary, core]
        try:
            src_raw = subprocess.check_output(src_cmd, stderr=subprocess.STDOUT, text=True)
        except:
            src_raw = "(Source code not available)"

        return bt_raw, info_raw, src_raw
    except Exception as e:
        return f"GDB Error: {str(e)}", "(Detailed info unavailable)", "(Source unavailable)"


def build_analysis_prompt(exe_name: str, bt: str, info: str, src: str) -> str:
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
    client = AIAProviderFactory.create_client()

    provider_info = AIAProviderFactory.get_provider_info()
    provider = os.getenv('AI_PROVIDER', 'google').lower()
    provider_name = provider_info.get(provider, {}).get('name', 'AI')

    print(f"[*] Using AI provider: {provider_name}", file=sys.stderr)

    prompt = build_analysis_prompt(exe_name, bt, info, src)

    result = client.analyze(prompt)

    result['provider'] = provider_name

    return result


def build_html(exe_name, bt, ai, info, src):
    signal_name, signal_desc, signal_color, severity = extract_crash_signal(bt)

    provider_name = ai.get('provider', 'AI')

    exe_name_safe = html_module.escape(exe_name)
    bt_safe = html_module.escape(bt[:3000])
    ai_root_cause_safe = html_module.escape(str(ai.get('root_cause', 'Unknown')))
    ai_explanation_safe = html_module.escape(str(ai.get('explanation', '')))
    ai_fix_code_safe = html_module.escape(str(ai.get('fix_code', '')))
    ai_prevention_safe = html_module.escape(str(ai.get('prevention', '')))
    ai_location_safe = html_module.escape(str(ai.get('location', 'N/A')))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    severity_score = {'critical': 9, 'high': 7, 'medium': 5, 'low': 3}.get(severity, 5)

    prevention_items = ai_prevention_safe.replace('\n', '</li><li>').replace('  ', '&nbsp;&nbsp;')
    if prevention_items:
        prevention_items = f'<li>{prevention_items}</li>'

    stack_trace_lines = []
    for i, line in enumerate(bt_safe.split('\n')[:50]):
        frame_class = ' frame-0' if i == 0 else ''
        escaped_line = html_module.escape(line)
        stack_trace_lines.append(f'<div class="stack-trace-line{frame_class}">{escaped_line}</div>')
    stack_trace_html = ''.join(stack_trace_lines)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Crash Analysis Report - {exe_name_safe}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary-50: #eff6ff; --primary-100: #dbeafe; --primary-500: #3b82f6; --primary-600: #2563eb;
            --info-50: #eff6ff; --info-100: #dbeafe; --info-500: #3b82f6; --info-600: #2563eb;
            --error-50: #fef2f2; --error-100: #fee2e2; --error-500: #ef4444; --error-600: #dc2626; --error-700: #b91c1c;
            --warning-50: #fffbeb; --warning-100: #fef3c7; --warning-500: #f59e0b; --warning-600: #d97706;
            --success-50: #f0fdf4; --success-100: #dcfce7; --success-500: #22c55e; --success-600: #16a34a; --success-700: #15803d;
            --neutral-50: #f8fafc; --neutral-100: #f1f5f9; --neutral-200: #e2e8f0; --neutral-300: #cbd5e1;
            --neutral-400: #94a3b8; --neutral-500: #64748b; --neutral-600: #475569;
            --neutral-700: #334155; --neutral-800: #1e293b; --neutral-900: #0f172a;
            --signal-color: {signal_color}; --severity-score: {severity_score};
            --font-sans: 'Inter', sans-serif; --font-mono: 'JetBrains Mono', monospace;
            --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1); --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
            --radius: 0.5rem; --radius-lg: 1rem;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: var(--font-sans); background: var(--neutral-50); color: var(--neutral-800); line-height: 1.6; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 0 24px; }}

        .report-header {{ background: linear-gradient(135deg, var(--neutral-900) 0%, var(--neutral-800) 100%); color: white; padding: 48px 0; position: relative; }}
        .report-header::before {{ content: ''; position: absolute; inset: 0; background: radial-gradient(circle at 20% 50%, rgba(59,130,246,0.15) 0%, transparent 50%); pointer-events: none; }}
        .header-content {{ display: grid; grid-template-columns: 1fr auto; gap: 48px; align-items: center; position: relative; z-index: 1; }}
        .header-title {{ display: flex; align-items: center; gap: 24px; }}
        .header-icon {{ width: 64px; height: 64px; background: var(--signal-color); border-radius: var(--radius-lg); display: flex; align-items: center; justify-content: center; font-size: 28px; box-shadow: var(--shadow-lg); }}
        .header-text h1 {{ font-size: 2.5rem; font-weight: 700; letter-spacing: -0.025em; margin-bottom: 8px; }}
        .header-text .subtitle {{ font-size: 1.125rem; color: var(--neutral-400); font-family: var(--font-mono); }}

        .severity-indicator {{ text-align: center; background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 24px; padding: 24px; border: 1px solid rgba(255,255,255,0.2); }}
        .severity-circle {{ width: 120px; height: 120px; position: relative; margin: 0 auto 16px; }}
        .severity-circle svg {{ transform: rotate(-90deg); width: 100%; height: 100%; }}
        .severity-circle .bg-circle {{ fill: none; stroke: rgba(255,255,255,0.2); stroke-width: 8; }}
        .severity-circle .progress-circle {{ fill: none; stroke: var(--signal-color); stroke-width: 8; stroke-linecap: round; stroke-dasharray: 339.292; stroke-dashoffset: calc(339.292 - (339.292 * var(--severity-score)) / 10); }}
        .severity-value {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 2rem; font-weight: 700; color: var(--signal-color); }}
        .severity-label {{ font-size: 0.875rem; color: var(--neutral-400); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }}

        .status-bar {{ background: white; border-bottom: 1px solid var(--neutral-200); padding: 16px 0; position: sticky; top: 0; z-index: 100; box-shadow: var(--shadow); }}
        .status-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px; }}
        .status-item {{ display: flex; align-items: center; gap: 12px; }}
        .status-icon {{ width: 40px; height: 40px; border-radius: var(--radius); display: flex; align-items: center; justify-content: center; font-size: 18px; background: var(--neutral-100); }}
        .status-icon.signal {{ background: var(--error-50); color: var(--error-600); }}
        .status-icon.process {{ background: var(--primary-50); color: var(--primary-600); }}
        .status-icon.ai {{ background: var(--success-50); color: var(--success-600); }}
        .status-label {{ font-size: 0.75rem; color: var(--neutral-500); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }}
        .status-value {{ font-size: 0.9375rem; font-weight: 600; color: var(--neutral-800); }}
        .status-value.mono {{ font-family: var(--font-mono); }}

        .main-content {{ padding: 48px 0; }}
        .content-grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 32px; }}
        @media (max-width: 1024px) {{ .content-grid {{ grid-template-columns: 1fr; }} .header-content {{ grid-template-columns: 1fr; text-align: center; }} .header-title {{ flex-direction: column; }} }}

        .card {{ background: white; border-radius: var(--radius-lg); box-shadow: var(--shadow); border: 1px solid var(--neutral-200); overflow: hidden; margin-bottom: 24px; }}
        .card-header {{ padding: 24px; border-bottom: 1px solid var(--neutral-200); display: flex; align-items: center; gap: 12px; }}
        .card-header h2 {{ font-size: 1.25rem; font-weight: 600; color: var(--neutral-800); }}
        .card-header-icon {{ width: 36px; height: 36px; border-radius: var(--radius); display: flex; align-items: center; justify-content: center; font-size: 16px; }}
        .card-header-icon.analysis {{ background: var(--error-50); color: var(--error-600); }}
        .card-header-icon.code {{ background: var(--success-50); color: var(--success-600); }}
        .card-header-icon.shield {{ background: var(--primary-50); color: var(--primary-600); }}
        .card-header-icon.stack {{ background: var(--warning-50); color: var(--warning-600); }}
        .card-header-icon.debug {{ background: var(--neutral-100); color: var(--neutral-600); }}
        .card-header-icon.info {{ background: var(--primary-50); color: var(--primary-600); }}
        .card-body {{ padding: 24px; }}

        .section-label {{ display: inline-flex; align-items: center; gap: 8px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--signal-color); background: rgba(220,38,38,0.1); padding: 8px 12px; border-radius: 4px; margin-bottom: 12px; }}
        .section-title {{ font-size: 1.5rem; font-weight: 700; color: var(--neutral-900); line-height: 1.4; margin-bottom: 16px; }}
        .explanation-box {{ background: var(--neutral-50); border-left: 4px solid var(--primary-500); padding: 20px; border-radius: 0 var(--radius) var(--radius) 0; }}
        .explanation-box p {{ color: var(--neutral-700); line-height: 1.8; }}

        .info-item {{ padding: 16px 0; border-bottom: 1px solid var(--neutral-200); }}
        .info-item:last-child {{ border-bottom: none; padding-bottom: 0; }}
        .info-item:first-child {{ padding-top: 0; }}
        .info-label {{ font-size: 0.75rem; color: var(--neutral-500); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-bottom: 8px; }}
        .info-value {{ font-size: 0.9375rem; font-weight: 600; color: var(--neutral-800); }}
        .info-value.mono {{ font-family: var(--font-mono); font-size: 0.875rem; }}
        .info-value.location {{ font-size: 0.8125rem; line-height: 1.5; color: var(--neutral-600); }}

        .code-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }}
        .btn {{ display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; border-radius: var(--radius); font-size: 0.875rem; font-weight: 500; cursor: pointer; border: none; background: var(--neutral-100); color: var(--neutral-700); }}
        .btn:hover {{ background: var(--neutral-200); }}
        .code-block {{ background: var(--neutral-900); color: var(--neutral-100); border-radius: var(--radius-lg); overflow: hidden; }}
        .code-block-header {{ background: var(--neutral-800); padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--neutral-700); }}
        .code-language {{ font-size: 0.75rem; color: var(--neutral-400); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }}
        .code-block pre {{ padding: 20px; overflow-x: auto; font-family: var(--font-mono); font-size: 0.875rem; line-height: 1.7; max-height: 500px; overflow-y: auto; }}
        .badge {{ display: inline-flex; align-items: center; gap: 4px; padding: 4px 12px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }}
        .badge-success {{ background: var(--success-100); color: var(--success-700); }}
        .badge-error {{ background: var(--error-100); color: var(--error-700); }}

        .prevention-list {{ list-style: none; }}
        .prevention-list li {{ position: relative; padding-left: 40px; padding-bottom: 16px; border-bottom: 1px solid var(--neutral-200); color: var(--neutral-700); line-height: 1.7; }}
        .prevention-list li:last-child {{ border-bottom: none; padding-bottom: 0; }}
        .prevention-list li::before {{ content: '✓'; position: absolute; left: 0; top: 0; width: 24px; height: 24px; background: var(--success-500); color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }}

        .stack-trace-container {{ max-height: 400px; overflow-y: auto; background: var(--neutral-800); border-radius: var(--radius); padding: 16px; border: 1px solid var(--neutral-700); }}
        .stack-trace-line {{ font-family: var(--font-mono); font-size: 0.8125rem; line-height: 1.6; color: var(--neutral-200); padding: 6px 0; border-bottom: 1px solid var(--neutral-700); }}
        .stack-trace-line:last-child {{ border-bottom: none; }}
        .stack-trace-line.frame-0 {{ color: var(--error-500); font-weight: 600; }}

        .debug-tabs {{ display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid var(--neutral-200); padding-bottom: 16px; }}
        .debug-tab {{ padding: 8px 16px; font-size: 0.875rem; font-weight: 500; color: var(--neutral-600); background: none; border: none; cursor: pointer; border-radius: var(--radius); }}
        .debug-tab:hover {{ background: var(--neutral-100); color: var(--neutral-800); }}
        .debug-tab.active {{ background: var(--primary-500); color: white; }}
        .debug-content {{ display: none; }}
        .debug-content.active {{ display: block; }}

        .report-footer {{ background: var(--neutral-100); border-top: 1px solid var(--neutral-200); padding: 24px 0; margin-top: 48px; }}
        .footer-content {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; color: var(--neutral-600); font-size: 0.875rem; }}

        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .animate-fade-in {{ animation: fadeIn 0.5s ease-out forwards; }}
        .delay-100 {{ animation-delay: 0.1s; }}
        .delay-200 {{ animation-delay: 0.2s; }}
        .delay-300 {{ animation-delay: 0.3s; }}
    </style>
</head>
<body>
    <header class="report-header">
        <div class="container">
            <div class="header-content">
                <div class="header-title">
                    <div class="header-icon">⚠</div>
                    <div class="header-text">
                        <h1>Crash Analysis Report</h1>
                        <p class="subtitle">{exe_name_safe}</p>
                    </div>
                </div>
                <div class="severity-indicator">
                    <div class="severity-circle">
                        <svg viewBox="0 0 120 120">
                            <circle class="bg-circle" cx="60" cy="60" r="54"/>
                            <circle class="progress-circle" cx="60" cy="60" r="54"/>
                        </svg>
                        <div class="severity-value">{severity_score}</div>
                    </div>
                    <div class="severity-label">{severity} Severity</div>
                </div>
            </div>
        </div>
    </header>

    <div class="status-bar">
        <div class="container">
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-icon signal">📡</div>
                    <div>
                        <div class="status-label">Signal Type</div>
                        <div class="status-value">{signal_name}</div>
                    </div>
                </div>
                <div class="status-item">
                    <div class="status-icon process">⚙</div>
                    <div>
                        <div class="status-label">Process</div>
                        <div class="status-value mono">{exe_name_safe}</div>
                    </div>
                </div>
                <div class="status-item">
                    <div class="status-icon">🕐</div>
                    <div>
                        <div class="status-label">Report Time</div>
                        <div class="status-value">{timestamp}</div>
                    </div>
                </div>
                <div class="status-item">
                    <div class="status-icon ai">🤖</div>
                    <div>
                        <div class="status-label">AI Provider</div>
                        <div class="status-value">{provider_name}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <main class="main-content">
        <div class="container">
            <div class="content-grid">
                <div class="left-column">
                    <div class="card animate-fade-in">
                        <div class="card-header">
                            <div class="card-header-icon analysis">🔍</div>
                            <h2>Root Cause Analysis</h2>
                        </div>
                        <div class="card-body">
                            <span class="section-label">⚠ {signal_desc}</span>
                            <h3 class="section-title">{ai_root_cause_safe}</h3>
                            <div class="explanation-box">
                                <p>{ai_explanation_safe}</p>
                            </div>
                        </div>
                    </div>

                    <div class="card animate-fade-in delay-100">
                        <div class="card-header">
                            <div class="card-header-icon code">💡</div>
                            <h2>AI Suggested Fix</h2>
                        </div>
                        <div class="card-body">
                            <div class="code-header">
                                <span class="badge badge-success">Recommended Solution</span>
                                <button class="btn" onclick="copyCode()">📋 Copy</button>
                            </div>
                            <div class="code-block">
                                <div class="code-block-header">
                                    <span class="code-language">C/C++</span>
                                    <span class="badge badge-error">{ai_location_safe}</span>
                                </div>
                                <pre><code id="fix-code">{ai_fix_code_safe}</code></pre>
                            </div>
                        </div>
                    </div>

                    <div class="card animate-fade-in delay-200">
                        <div class="card-header">
                            <div class="card-header-icon shield">🛡</div>
                            <h2>Prevention Strategies</h2>
                        </div>
                        <div class="card-body">
                            <ol class="prevention-list">
                                {prevention_items}
                            </ol>
                        </div>
                    </div>

                    <div class="card animate-fade-in delay-300">
                        <div class="card-header">
                            <div class="card-header-icon stack">📚</div>
                            <h2>Stack Trace</h2>
                        </div>
                        <div class="card-body">
                            <div class="stack-trace-container">
                                {stack_trace_html}
                            </div>
                            <p style="margin-top: 16px; font-size: 0.875rem; color: var(--neutral-500);">ℹ Showing first 50 frames. Full trace available in GDB.</p>
                        </div>
                    </div>

                    <div class="card animate-fade-in delay-300">
                        <div class="card-header">
                            <div class="card-header-icon debug">🔧</div>
                            <h2>Debug Information</h2>
                        </div>
                        <div class="card-body">
                            <div class="debug-tabs">
                                <button class="debug-tab active" onclick="switchTab('registers')">Registers</button>
                                <button class="debug-tab" onclick="switchTab('source')">Source Context</button>
                            </div>
                            <div id="registers" class="debug-content active">
                                <div class="code-block">
                                    <pre><code>{html_module.escape(info[:2000])}</code></pre>
                                </div>
                            </div>
                            <div id="source" class="debug-content">
                                <div class="code-block">
                                    <pre><code>{html_module.escape(src[:2000])}</code></pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="right-column">
                    <div class="card animate-fade-in">
                        <div class="card-header">
                            <div class="card-header-icon info">ℹ</div>
                            <h2>Quick Info</h2>
                        </div>
                        <div class="card-body">
                            <div class="info-item">
                                <div class="info-label">Signal Type</div>
                                <div class="info-value">{signal_name}</div>
                                <div style="font-size: 0.8125rem; color: var(--neutral-500); margin-top: 4px;">{signal_desc}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Process Name</div>
                                <div class="info-value mono">{exe_name_safe}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Crash Location</div>
                                <div class="info-value location mono">{ai_location_safe}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">Report Time</div>
                                <div class="info-value">{timestamp}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">AI Provider</div>
                                <div class="info-value">{provider_name}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <footer class="report-footer">
        <div class="container">
            <div class="footer-content">
                <div>🔒 Automated Crash Analysis Report</div>
                <div>Generated on {timestamp} • AI Provider: {provider_name}</div>
            </div>
        </div>
    </footer>

    <script>
        function copyCode() {{
            const code = document.getElementById('fix-code').innerText;
            navigator.clipboard.writeText(code).then(() => {{
                alert('Code copied to clipboard!');
            }});
        }}

        function switchTab(tabName) {{
            document.querySelectorAll('.debug-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.debug-content').forEach(content => content.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
        }}
    </script>
</body>
</html>"""


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python mcp_analyzer.py <binary_path> <core_dump_path>", file=sys.stderr)
        sys.exit(1)

    bin_p, core_p = sys.argv[1], sys.argv[2]

    allowed_dirs = ['/tmp/cores', '/home/jenkins/codes', '/home/jenkins']

    if not validate_path(bin_p, allowed_dirs):
        print(f"SECURITY ERROR: Invalid binary path: {bin_p}", file=sys.stderr)
        sys.exit(1)

    if not validate_path(core_p, allowed_dirs):
        print(f"SECURITY ERROR: Invalid core dump path: {core_p}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(bin_p):
        print(f"Error: Binary file not found: {bin_p}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(core_p):
        print(f"Error: Core dump file not found: {core_p}", file=sys.stderr)
        sys.exit(1)

    e_name = os.path.basename(bin_p)

    print(f"[*] Analyzing crash for: {e_name}", file=sys.stderr)
    gdb_bt, gdb_info, gdb_src = run_gdb(bin_p, core_p)

    print("[*] Requesting AI analysis...", file=sys.stderr)
    ai_json = get_ai_insight(gdb_bt, gdb_info, gdb_src, e_name)

    print("[*] Generating report...", file=sys.stderr)
    html_output = build_html(e_name, gdb_bt, ai_json, gdb_info, gdb_src)

    print(html_output, end='')
    print("[+] Report generation completed", file=sys.stderr)
