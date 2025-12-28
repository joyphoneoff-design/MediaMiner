#!/bin/bash
# Crawl_R2R 啟動腳本

echo "🚀 啟動 Crawl_R2R..."
echo "================================"

# 切換到專案目錄
cd "$(dirname "$0")"

# 檢查虛擬環境
if [ ! -d ".venv" ]; then
    echo "📦 創建虛擬環境..."
    python3 -m venv .venv
fi

# 啟動虛擬環境
source .venv/bin/activate

# 安裝依賴 (首次運行)
if [ ! -f ".deps_installed" ]; then
    echo "📦 安裝依賴..."
    pip install -r requirements.txt
    touch .deps_installed
fi

# 載入環境變數
if [ -f "config/api_keys.env" ]; then
    export $(cat config/api_keys.env | grep -v '^#' | xargs)
fi

# 啟動 Streamlit
echo "🌐 啟動 Web UI..."
echo "   URL: http://localhost:8502"
echo "================================"

streamlit run ui/app.py --server.port 8502 --server.headless true
