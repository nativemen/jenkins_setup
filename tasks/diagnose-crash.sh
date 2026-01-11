#!/bin/bash

# =================================================================
# Usage: bash diagnose-crash.sh <binary_full_path>
# =================================================================

BINARY=$1
EXE_NAME=$(basename "$BINARY")
CORE_DIR="/tmp/cores"
REPORT_DIR="/tmp/cores"

echo "--- [MCP Diagnose] Starting AI Analysis for $EXE_NAME ---"

# 1. 查找对应的 Core 文件 (保持原逻辑)
CORE_FILE=$(ls -t $CORE_DIR/core.${EXE_NAME}.* $CORE_DIR/core.${EXE_NAME} 2> /dev/null | head -1)

if [ -z "$CORE_FILE" ]; then
    CORE_FILE=$(ls -t $CORE_DIR/core.* 2> /dev/null | grep -v "\.c$" | head -1)
fi

# 2. 验证 Core 文件是否有效
if [ ! -f "$CORE_FILE" ]; then
    echo "❌ Error: No coredump file found for $EXE_NAME"
    exit 0
fi

echo "✅ Found Core File: $CORE_FILE"

# 3. 【核心修改】调用 Python MCP 分析器生成 HTML 可视化报告
# 之前的脚本只是重定向输出到 txt，现在我们直接让 Python 脚本通过 AI 生成 HTML 报告
HTML_REPORT="${REPORT_DIR}/report-${EXE_NAME}.html"

echo "--- Invoking AI LLM via mcp_analyzer.py ---"
# 注意：路径需与你实际存放 mcp_analyzer.py 的位置一致
python3 /home/jenkins/mcp_tools/mcp_analyzer.py "$BINARY" "$CORE_FILE" > "$HTML_REPORT" 2>&1

# 4. 【核心修改】保留一个轻量级文本摘要供 Jenkins Console 查看
TRACE_FILE="${REPORT_DIR}/trace-${EXE_NAME}.txt"
echo "AI Diagnosis generated at $HTML_REPORT" > "$TRACE_FILE"
echo "Summary of Stack Trace:" >> "$TRACE_FILE"
gdb -batch -ex "bt" "$BINARY" "$CORE_FILE" | head -n 10 >> "$TRACE_FILE"

echo "✅ All reports generated in $REPORT_DIR"
