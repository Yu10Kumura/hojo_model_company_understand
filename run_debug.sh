#!/bin/bash
cd /Users/yutokumura/Desktop/Python/企業理解HOJO_model_v4
source /Users/yutokumura/Desktop/Python/.venv/bin/activate

# 既存のログをクリア
> debug_output.log

echo "=== Starting Streamlit with debug logging ===" | tee -a debug_output.log
echo "Log file: debug_output.log" | tee -a debug_output.log
echo "Access at: http://localhost:8601" | tee -a debug_output.log
echo "" | tee -a debug_output.log

# Streamlitを実行してログファイルに出力
streamlit run app.py --server.port 8601 --server.headless true 2>&1 | tee -a debug_output.log
