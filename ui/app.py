#!/usr/bin/env python3
"""
MediaMiner Streamlit UI
社交媒體知識提取系統介面
"""

import os
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st

# 添加專案路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.youtube_scraper import YouTubeScraper
from scrapers.transcript_fetcher import TranscriptFetcher
from processors.knowledge_extractor import KnowledgeExtractor
from processors.metadata_injector import MetadataInjector
from integrations.r2r_connector import R2RConnector

# ===========================================
# 頁面配置
# ===========================================
st.set_page_config(
    page_title="MediaMiner - 創業者知識庫",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===========================================
# 自定義樣式
# ===========================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 10px;
        padding: 1.5rem;
        text-align: center;
    }
    .stat-number {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ===========================================
# Session State 初始化
# ===========================================
if 'videos' not in st.session_state:
    st.session_state.videos = []
if 'processed_count' not in st.session_state:
    st.session_state.processed_count = 0
if 'processing' not in st.session_state:
    st.session_state.processing = False

# ===========================================
# 側邊欄
# ===========================================
with st.sidebar:
    st.markdown("### 🎯 MediaMiner")
    st.markdown("**社交媒體知識提取系統**")
    
    st.divider()
    
    # 導航
    page = st.radio(
        "功能選擇",
        ["📺 頻道擷取", "📊 處理狀態", "🔍 知識問答", "⚙️ 設定"],
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # 狀態卡片
    st.markdown("### 📈 統計")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("已處理", st.session_state.processed_count)
    with col2:
        # 計算已處理檔案數
        processed_dir = Path.home() / "Documents" / "MediaMiner_Data" / "processed"
        if processed_dir.exists():
            file_count = len(list(processed_dir.glob("*.md")))
        else:
            file_count = 0
        st.metric("檔案數", file_count)
    
    st.divider()
    
    # R2R 狀態
    r2r = R2RConnector()
    status = r2r.check_r2r_status()
    if status.get('running'):
        st.success("✅ R2R 運行中")
    else:
        st.warning("⚠️ R2R 未運行")

# ===========================================
# 主內容區
# ===========================================

# 頁面標題
st.markdown('<h1 class="main-header">🎯 MediaMiner</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">一人公司創業者知識提取框架</p>', unsafe_allow_html=True)

# 頻道擷取頁面
if page == "📺 頻道擷取":
    st.markdown("## 📺 頻道擷取")
    
    # 輸入區
    col1, col2 = st.columns([3, 1])
    
    with col1:
        channel_url = st.text_input(
            "YouTube 頻道 URL",
            placeholder="https://youtube.com/@dankoetalks",
            help="輸入 YouTube 頻道 URL"
        )
    
    with col2:
        max_videos = st.number_input("影片數量", min_value=1, max_value=100, value=10)
    
    # 預設頻道
    st.markdown("#### 🔖 預設頻道")
    preset_channels = [
        ("Dan Koe (YouTube)", "https://youtube.com/@dankoetalks"),
    ]
    
    col1, col2 = st.columns(2)
    for i, (name, url) in enumerate(preset_channels):
        with [col1, col2][i % 2]:
            if st.button(f"📌 {name}", key=f"preset_{i}"):
                channel_url = url
    
    with st.expander("⚠️ 小紅書限制說明"):
        st.markdown("""
        小紅書有反爬機制，目前支援有限：
        - ❌ 用戶主頁連結無法直接爬取
        - ⚠️ 需要具體筆記連結 (`/explore/xxx`)
        - 💡 建議：手動複製筆記連結
        """)
    
    st.divider()
    
    # 處理按鈕
    if st.button("🚀 開始擷取", type="primary", disabled=st.session_state.processing):
        if channel_url:
            st.session_state.processing = True
            
            progress_bar = st.progress(0, text="初始化...")
            status_container = st.empty()
            
            try:
                # 初始化元件
                scraper = YouTubeScraper()
                fetcher = TranscriptFetcher()
                extractor = KnowledgeExtractor()
                injector = MetadataInjector()
                
                # 1. 獲取影片列表
                progress_bar.progress(10, text="獲取影片列表...")
                videos = scraper.get_channel_videos(channel_url, max_videos)
                
                if not videos:
                    st.error("❌ 無法獲取影片列表")
                    st.session_state.processing = False
                else:
                    st.session_state.videos = videos
                    status_container.info(f"📹 找到 {len(videos)} 部影片")
                    
                    # 2. 處理每部影片
                    results = []
                    for i, video in enumerate(videos):
                        progress = int(10 + (i / len(videos)) * 80)
                        progress_bar.progress(progress, text=f"處理: {video['title'][:40]}...")
                        
                        # 獲取逐字稿
                        transcript = fetcher.fetch(video['url'])
                        
                        if transcript:
                            # 提取知識
                            knowledge = extractor.process_transcript(
                                transcript['text'],
                                video_info={
                                    'title': video['title'],
                                    'channel': channel_url,
                                    'duration': video.get('duration')
                                }
                            )
                            
                            # 生成 MD 檔案 (純 MD，無 YAML frontmatter)
                            md_content = injector.create_markdown(
                                content=transcript['text'],
                                knowledge=knowledge.get('knowledge', ''),
                                video_info={
                                    'title': video['title'],
                                    'source': channel_url,
                                    'platform': 'youtube',
                                    'url': video['url'],
                                    'duration': video.get('duration')
                                }
                            )
                            
                            # 保存檔案
                            output_dir = Path.home() / "Documents" / "MediaMiner_Data" / "processed"
                            output_dir.mkdir(parents=True, exist_ok=True)
                            
                            filename = injector.generate_safe_filename(video['title'])
                            output_file = output_dir / f"{filename}.md"
                            output_file.write_text(md_content, encoding='utf-8')
                            
                            results.append({
                                'video': video,
                                'success': True,
                                'file': str(output_file)
                            })
                            st.session_state.processed_count += 1
                        else:
                            results.append({
                                'video': video,
                                'success': False,
                                'error': '無法獲取逐字稿'
                            })
                    
                    progress_bar.progress(100, text="完成!")
                    
                    # 顯示結果
                    success_count = sum(1 for r in results if r['success'])
                    st.success(f"✅ 完成! 成功處理 {success_count}/{len(videos)} 部影片")
                    
                    # 結果表格
                    with st.expander("📋 處理結果"):
                        for r in results:
                            if r['success']:
                                st.markdown(f"✅ **{r['video']['title'][:50]}...**")
                            else:
                                st.markdown(f"❌ **{r['video']['title'][:50]}...** - {r.get('error', '')}")
                    
            except Exception as e:
                st.error(f"❌ 錯誤: {str(e)}")
            finally:
                st.session_state.processing = False
        else:
            st.warning("⚠️ 請輸入頻道 URL")

# 處理狀態頁面
elif page == "📊 處理狀態":
    st.markdown("## 📊 處理狀態")
    
    # 目錄統計
    data_dir = Path.home() / "Documents" / "MediaMiner_Data"
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        raw_count = len(list((data_dir / "raw").glob("*"))) if (data_dir / "raw").exists() else 0
        st.metric("📥 原始檔案", raw_count)
    
    with col2:
        processed_count = len(list((data_dir / "processed").glob("*.md"))) if (data_dir / "processed").exists() else 0
        st.metric("✅ 已處理", processed_count)
    
    with col3:
        knowledge_count = len(list((data_dir / "knowledge").glob("*.md"))) if (data_dir / "knowledge").exists() else 0
        st.metric("📚 知識卡片", knowledge_count)
    
    st.divider()
    
    # 最近處理的檔案
    st.markdown("### 📄 最近處理的檔案")
    
    processed_dir = data_dir / "processed"
    if processed_dir.exists():
        files = sorted(processed_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]
        
        for f in files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            with st.expander(f"📄 {f.name} ({mtime})"):
                content = f.read_text(encoding='utf-8')
                st.markdown(content[:2000] + "..." if len(content) > 2000 else content)
    else:
        st.info("📭 還沒有處理過的檔案")

# 知識問答頁面
elif page == "🔍 知識問答":
    st.markdown("## 🔍 知識問答")
    
    # 問答輸入
    query = st.text_input(
        "輸入您的問題",
        placeholder="例如：什麼是商業模式畫布？如何建立個人品牌？"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔍 本地搜索", type="primary"):
            if query:
                with st.spinner("搜索中..."):
                    # 本地檔案搜索
                    knowledge_dir = Path.home() / "Documents" / "MediaMiner_Data" / "knowledge"
                    results = []
                    
                    if knowledge_dir.exists():
                        for f in knowledge_dir.glob("*.md"):
                            content = f.read_text(encoding='utf-8')
                            if query.lower() in content.lower():
                                results.append({
                                    'file': f.name,
                                    'content': content[:1000]
                                })
                    
                    if results:
                        st.markdown("### 📋 搜索結果")
                        for r in results:
                            with st.expander(f"📄 {r['file']}"):
                                st.markdown(r['content'])
                    else:
                        st.info("未找到相關內容")
    
    with col2:
        if st.button("🧠 AI 問答"):
            if query:
                with st.spinner("AI 思考中..."):
                    # 使用 LLM 直接回答
                    try:
                        from processors.llm_client import get_llm_client
                        
                        # 讀取所有知識卡片作為上下文
                        knowledge_dir = Path.home() / "Documents" / "MediaMiner_Data" / "knowledge"
                        context = ""
                        if knowledge_dir.exists():
                            for f in list(knowledge_dir.glob("*.md"))[:5]:
                                context += f.read_text(encoding='utf-8')[:2000] + "\n\n"
                        
                        client = get_llm_client()
                        prompt = f"""
基於以下知識庫內容回答問題：

{context[:6000]}

問題：{query}

請用繁體中文回答。
"""
                        answer = client.generate(
                            prompt=prompt,
                            system_prompt="你是一位商業知識專家，請根據提供的知識內容回答問題。",
                            max_tokens=1000
                        )
                        
                        if answer:
                            st.markdown("### 💡 AI 回答")
                            st.markdown(answer)
                        else:
                            st.error("無法獲取回答")
                    except Exception as e:
                        st.error(f"錯誤: {str(e)}")
    
    # R2R 狀態提示
    with st.expander("ℹ️ 關於 R2R"):
        st.markdown("""
        **R2R 向量搜索** 目前未啟用
        
        - 本地搜索：基於關鍵字匹配
        - AI 問答：使用 LLM 直接分析知識卡片
        - RAG 搜索：需要啟動 R2R 服務
        """)

# 設定頁面
elif page == "⚙️ 設定":
    st.markdown("## ⚙️ 設定")
    
    # API 密鑰設定
    st.markdown("### 🔑 API 密鑰")
    
    with st.expander("Gemini API"):
        gemini_key = st.text_input("Gemini API Key", type="password", 
                                    value=os.getenv("GEMINI_API_KEY", ""))
        gemini_key_backup = st.text_input("Gemini Backup Key", type="password",
                                           value=os.getenv("GEMINI_API_KEY_BACKUP", ""))
    
    with st.expander("Cerebras API"):
        cerebras_key = st.text_input("Cerebras API Key", type="password",
                                      value=os.getenv("CEREBRAS_API_KEY", ""))
    
    with st.expander("OpenAI API"):
        openai_key = st.text_input("OpenAI API Key", type="password",
                                    value=os.getenv("OPENAI_API_KEY", ""))
    
    st.divider()
    
    # R2R 設定
    st.markdown("### 🗄️ R2R 配置")
    
    r2r = R2RConnector()
    status = r2r.check_r2r_status()
    
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Collection Name", value="crawl_r2r_dev")
    with col2:
        if status.get('running'):
            st.success("✅ 連接正常")
        else:
            st.error("❌ 連接失敗")

# ===========================================
# 頁腳
# ===========================================
st.divider()
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.9rem;">
    MediaMiner v1.0 | 一人公司創業者知識提取框架
</div>
""", unsafe_allow_html=True)
