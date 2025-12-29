# MediaMiner 🎯

> 一人公司創業者社交媒體知識提取框架

## ✨ 功能特色

- 📺 **批次擷取** - YouTube/小紅書頻道逐字稿
- 👥 **講者辨識** - 自動識別主持人與受訪者
- 📚 **知識提取** - LLM 提取商業知識重點
- 🔗 **R2R 整合** - 自動向量化，支持 RAG 問答
- 🖥️ **Streamlit UI** - 友善的操作介面

## 🚀 快速開始

```bash
# 1. 進入專案目錄
cd ~/MediaMiner

# 2. 設定執行權限
chmod +x run.sh

# 3. 啟動系統
./run.sh
```

Web UI: http://localhost:8502

## 📁 專案結構

```
MediaMiner/
├── config/
│   ├── config.yaml        # 主配置
│   ├── api_keys.env       # API 密鑰
│   └── prompts/           # LLM Prompts
├── scrapers/
│   ├── youtube_scraper.py # YouTube 爬蟲
│   └── transcript_fetcher.py # 逐字稿擷取
├── processors/
│   ├── llm_client.py      # 多提供商 LLM
│   ├── knowledge_extractor.py # 知識提取
│   └── metadata_injector.py # Metadata 注入
├── integrations/
│   ├── r2r_connector.py   # R2R 連接器
│   └── file_watcher.py    # 檔案監控
├── ui/
│   └── app.py             # Streamlit UI
└── run.sh                 # 啟動腳本
```

## 🔑 API 優先順序 (免費優先)

1. **Gemini 2.5 Flash Lite** (免費)
2. **OpenRouter** gemini-2.0-flash-exp:free
3. **Cerebras** Qwen3-235B
4. **LM Studio** 本地
5. **OpenAI** (付費備用)

## 📋 使用流程

1. **頻道擷取** - 輸入 YouTube 頻道 URL
2. **自動下載** - 批次下載字幕 (yt-dlp)
3. **知識提取** - LLM 分析商業知識
4. **R2R 整合** - 自動向量化存儲
5. **問答查詢** - RAG 知識庫問答

## 🎯 目標頻道

- YouTube: @dankoetalks
- 小紅書: xhslink

## 📦 依賴

- yt-dlp (YouTube 下載)
- openai-whisper (語音辨識)
- google-generativeai (Gemini API)
- streamlit (Web UI)
- watchdog (檔案監控)

## 📄 License

MIT
