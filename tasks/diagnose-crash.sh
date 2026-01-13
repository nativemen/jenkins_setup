#!/bin/bash

# =================================================================
# Usage: bash diagnose-crash.sh <binary_full_path>
# =================================================================

BINARY=$1
EXE_NAME=$(basename "$BINARY")
CORE_DIR="/tmp/cores"
REPORT_DIR="/tmp/cores"

echo "--- [MCP Diagnose] Starting AI Analysis for $EXE_NAME ---"

# 1. Find corresponding core file (retain original logic)
CORE_FILE=$(ls -t $CORE_DIR/core.${EXE_NAME}.* $CORE_DIR/core.${EXE_NAME} 2> /dev/null | head -1)

if [ -z "$CORE_FILE" ]; then
    CORE_FILE=$(ls -t $CORE_DIR/core.* 2> /dev/null | grep -v "\.c$" | head -1)
fi

# 2. Verify if core file is valid
if [ ! -f "$CORE_FILE" ]; then
    echo "❌ Error: No coredump file found for $EXE_NAME"
    exit 0
fi

echo "✅ Found Core File: $CORE_FILE"

# 3. [Core Change] Invoke Python MCP analyzer to generate HTML visual reports
# The previous script only redirected output to txt, now we let the Python script directly generate HTML reports via AI
HTML_REPORT="${REPORT_DIR}/report-${EXE_NAME}.html"

echo "--- Invoking AI LLM via mcp_analyzer.py ---"
# Note: Path must match your actual mcp_analyzer.py location
python3 /home/jenkins/mcp_tools/mcp_analyzer.py "$BINARY" "$CORE_FILE" > "$HTML_REPORT" 2>&1

# 4. [Core Change] Retain a lightweight text summary for Jenkins Console viewing
TRACE_FILE="${REPORT_DIR}/trace-${EXE_NAME}.txt"
echo "AI Diagnosis generated at $HTML_REPORT" > "$TRACE_FILE"
echo "Summary of Stack Trace:" >> "$TRACE_FILE"
gdb -batch -ex "bt" "$BINARY" "$CORE_FILE" | head -n 10 >> "$TRACE_FILE"

echo "✅ All reports generated in $REPORT_DIR"
