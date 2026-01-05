#!/usr/bin/env python3
"""
MediaMiner Streamlit UI
社交媒體知識提取系統介面
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# 載入環境變數
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

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
        ["📺 頻道擷取", "📱 小紅書", "📊 處理狀態", "🔍 知識問答", "⚙️ 設定"],
        label_visibility="collapsed"
    )
    
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
    
    # Session state for video list
    if 'channel_videos' not in st.session_state:
        st.session_state.channel_videos = []
    if 'selected_videos' not in st.session_state:
        st.session_state.selected_videos = set()
    if 'fetch_complete' not in st.session_state:
        st.session_state.fetch_complete = False
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    
    # 輸入區
    channel_url = st.text_input(
        "YouTube 頻道 URL",
        placeholder="https://youtube.com/@DanKoeTalks",
        help="輸入 YouTube 頻道 URL (支援 @username 格式)"
    )
    
    st.divider()
    
    # ========== 步驟 1: 獲取影片列表 ==========
    col1, col2 = st.columns([1, 3])
    
    with col1:
        fetch_btn = st.button("📋 獲取影片列表", type="secondary")
    
    with col2:
        if st.session_state.fetch_complete:
            st.success(f"✅ 已載入 {len(st.session_state.channel_videos)} 部影片")
    
    if fetch_btn and channel_url:
        st.session_state.processing = True
        st.session_state.fetch_complete = False
        
        with st.spinner("🔍 正在獲取頻道影片列表..."):
            scraper = YouTubeScraper()
            max_vids = 0  # 0 = 獲取全部影片
            videos = scraper.get_channel_videos(channel_url, max_vids)
            
            if videos:
                st.session_state.channel_videos = videos
                
                # 預設僅選擇未處理的影片 (Smart Select)
                from processors.metadata_injector import MetadataInjector
                temp_injector = MetadataInjector()
                temp_output_dir = Path.home() / "Documents" / "MediaMiner_Data" / "processed"
                unprocessed_indices = set()
                for idx, video in enumerate(videos):
                    filename = temp_injector.generate_safe_filename(video['title'])
                    if not (temp_output_dir / f"{filename}.md").exists():
                        unprocessed_indices.add(idx)
                
                st.session_state.selected_videos = unprocessed_indices  # 僅選擇未處理
                st.session_state.fetch_complete = True
                st.success(f"✅ 找到 {len(videos)} 部影片 (🆕 {len(unprocessed_indices)} 部未處理)")
            else:
                st.error("❌ 無法獲取影片列表，請確認 URL 格式正確")
        
        st.session_state.processing = False
        st.rerun()
    
    # ========== 步驟 2: 顯示影片列表與選擇 ==========
    if st.session_state.channel_videos:
        st.markdown("### 📹 影片列表")
        
        # 定義 checkbox 變化處理函數 (已廢棄，改用直接狀態同步)
        # def toggle_video(idx, version): ...
        
        # 初始化 MetadataInjector 用於檢查已處理檔案
        injector = MetadataInjector()
        output_dir = Path.home() / "Documents" / "MediaMiner_Data" / "processed"

        # 全選/取消全選 (使用獨立計數器避免 key 衝突)
        if 'select_version' not in st.session_state:
            st.session_state.select_version = 0
        
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        with col1:
            if st.button("✅ 全選 (未處理)", help="僅選擇尚未下載/處理過的影片"):
                # Smart Select: 僅選擇未處理的影片
                new_selection = set()
                for idx, video in enumerate(st.session_state.channel_videos):
                    filename = injector.generate_safe_filename(video['title'])
                    if not (output_dir / f"{filename}.md").exists():
                        new_selection.add(idx)
                
                st.session_state.selected_videos = new_selection
                st.session_state.select_version += 1  # 強制重新生成所有 checkbox
                st.rerun()
        with col2:
            if st.button("☑️ 強制全選", help="選擇列表中的所有影片（包含已處理）"):
                st.session_state.selected_videos = set(range(len(st.session_state.channel_videos)))
                st.session_state.select_version += 1
                st.rerun()
        with col3:
            if st.button("❌ 清除選擇"):
                st.session_state.selected_videos = set()
                st.session_state.select_version += 1
                st.rerun()
        with col4:
            # 計算統計
            total_selected = len(st.session_state.selected_videos)
            processed_in_selection = 0
            for idx in st.session_state.selected_videos:
                if 0 <= idx < len(st.session_state.channel_videos):
                    v = st.session_state.channel_videos[idx]
                    fname = injector.generate_safe_filename(v['title'])
                    if (output_dir / f"{fname}.md").exists():
                        processed_in_selection += 1
            
            new_in_selection = total_selected - processed_in_selection
            st.info(f"已選 **{total_selected}** 部 (🆕 {new_in_selection} / ✅ {processed_in_selection})")
        
        # 影片表格
        st.markdown("---")
        
        # 分頁顯示 (每頁 50 個)
        videos = st.session_state.channel_videos
        page_size = 50
        total_pages = (len(videos) - 1) // page_size + 1
        
        if 'video_page' not in st.session_state:
            st.session_state.video_page = 0
        
        # 分頁控制
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⬅️ 上一頁", disabled=st.session_state.video_page == 0):
                st.session_state.video_page -= 1
                st.rerun()
        with col2:
            st.markdown(f"<center>第 {st.session_state.video_page + 1} / {total_pages} 頁</center>", unsafe_allow_html=True)
        with col3:
            if st.button("➡️ 下一頁", disabled=st.session_state.video_page >= total_pages - 1):
                st.session_state.video_page += 1
                st.rerun()
        
        # 顯示當前頁的影片
        start_idx = st.session_state.video_page * page_size
        end_idx = min(start_idx + page_size, len(videos))
        
        # 使用版本號作為 key 前綴，確保全選/取消全選後重新生成 checkbox
        version = st.session_state.select_version
        
        for i in range(start_idx, end_idx):
            video = videos[i]
            col1, col2, col3, col4 = st.columns([0.5, 4, 1, 1])
            
            with col1:
                # 使用版本號確保全選/取消全選後 checkbox 正確更新
                checkbox_key = f"v{version}_vid_{i}"
                is_selected = i in st.session_state.selected_videos
                
                checked = st.checkbox(
                    "", 
                    value=is_selected,
                    key=checkbox_key,
                    label_visibility="collapsed"
                )
                
                # 直接狀態同步：如果 Checkbox 狀態與 Set 不一致，立即更新並重跑
                if checked and not is_selected:
                    st.session_state.selected_videos.add(i)
                    st.rerun()
                elif not checked and is_selected:
                    st.session_state.selected_videos.discard(i)
                    st.rerun()
            
            with col2:
                # 檢查是否已處理
                filename = injector.generate_safe_filename(video['title'])
                is_processed = (output_dir / f"{filename}.md").exists()
                
                title_display = video['title'][:60] + "..." if len(video['title']) > 60 else video['title']
                
                if is_processed:
                    st.markdown(f"**{i+1}.** {title_display} `✅ 已完成`")
                else:
                    st.markdown(f"**{i+1}.** {title_display}")
            
            with col3:
                st.caption(video.get('duration_string', 'N/A'))
            
            with col4:
                views = video.get('view_count', 0)
                if views >= 1000000:
                    st.caption(f"{views/1000000:.1f}M 👁")
                elif views >= 1000:
                    st.caption(f"{views/1000:.0f}K 👁")
                else:
                    st.caption(f"{views} 👁")
        
        st.divider()
        
        # ========== 步驟 3: 開始處理 ==========
        st.markdown("### 🚀 開始下載處理")
        
        # 處理設定 - 第一行
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            batch_size = st.slider("批次大小", min_value=1, max_value=10, value=10, 
                                   help="每批處理的影片數量")
        with col2:
            whisper_backend = st.selectbox(
                "Whisper 後端",
                options=["groq", "mlx", "openai"],
                format_func=lambda x: {
                    "mlx": "🖥️ MLX (本地 GPU)",
                    "groq": "⚡ Groq API (免費超快)", 
                    "openai": "🔷 OpenAI API (付費)"
                }.get(x, x),
                help="選擇語音辨識後端"
            )
        with col3:
            if whisper_backend == "mlx":
                whisper_model = "large-v3-turbo"
                st.info("📌 使用 Turbo 模型 (MLX GPU)")
            else:
                whisper_model = "large-v3-turbo"
                st.info("📌 使用 turbo 模型")
        with col4:
            if whisper_backend in ["groq", "openai"]:
                api_workers = st.slider("API 並行", min_value=1, max_value=10, value=10,
                                       help="Groq: 30 req/min，建議 5-7 | 10 可能觸發限速")
            else:
                api_workers = 1
                st.caption("本地處理")
        
        # 保存設定到 session
        st.session_state.whisper_backend = whisper_backend
        st.session_state.whisper_model = whisper_model
        st.session_state.api_workers = api_workers
        
        if st.button("🚀 開始下載字幕並處理", type="primary", 
                     disabled=len(st.session_state.selected_videos) == 0 or st.session_state.processing):
            
            st.session_state.processing = True
            selected_indices = sorted(st.session_state.selected_videos)
            selected_videos = [st.session_state.channel_videos[i] for i in selected_indices]
            
            st.info(f"🎬 準備處理 {len(selected_videos)} 部影片 (批次大小: {batch_size})")
            
            progress_bar = st.progress(0, text="初始化...")
            status_container = st.empty()
            metrics_placeholder = st.empty()
            
            try:
                import time
                import gc
                
                # 初始化元件 (每批重新初始化以釋放記憶體)
                output_dir = Path.home() / "Documents" / "MediaMiner_Data" / "processed"
                output_dir.mkdir(parents=True, exist_ok=True)
                
                results = []
                start_time = time.time()
                error_types = {}
                
                # 分批處理
                total_batches = (len(selected_videos) + batch_size - 1) // batch_size
                
                for batch_idx in range(total_batches):
                    batch_start = batch_idx * batch_size
                    batch_end = min(batch_start + batch_size, len(selected_videos))
                    batch_videos = selected_videos[batch_start:batch_end]
                    
                    status_container.info(f"📦 處理批次 {batch_idx + 1}/{total_batches} ({len(batch_videos)} 部影片)")
                    
                    # 每批重新建立元件以避免記憶體累積
                    fetcher = TranscriptFetcher()
                    extractor = KnowledgeExtractor()
                    injector = MetadataInjector()
                    
                    # 定義單個影片處理函數
                    def process_single_video(args):
                        video_idx, video = args
                        result = {'video': video, 'success': False, 'error': None}
                        
                        try:
                            filename = injector.generate_safe_filename(video['title'])
                            output_file = output_dir / f"{filename}.md"
                            
                            # 獲取逐字稿
                            transcript = fetcher.fetch(
                                video['url'],
                                whisper_backend=st.session_state.get('whisper_backend', 'mlx'),
                                whisper_model=st.session_state.get('whisper_model', 'large-v3-turbo')
                            )
                            
                            if transcript:
                                # 提取知識
                                knowledge = extractor.process_transcript(
                                    transcript['text'],
                                    video_info={
                                        'title': video['title'],
                                        'channel': video.get('channel', ''),
                                        'duration': video.get('duration')
                                    }
                                )
                                
                                # 生成 MD
                                # 將識別到的 guest 放入 video_info
                                guest = knowledge.get('guest')
                                md_content = injector.create_markdown(
                                    content=transcript['text'],
                                    knowledge=knowledge.get('knowledge', ''),
                                    video_info={
                                        'title': video['title'],
                                        'source': video.get('channel', ''),
                                        'platform': 'youtube',
                                        'url': video['url'],
                                        'duration': video.get('duration'),
                                        'guest': guest  # 訪談嘉賓
                                    },
                                    summary=knowledge.get('summary', ''),
                                    keywords=knowledge.get('keywords', []),
                                    entities=knowledge.get('entities', []),
                                    tags=knowledge.get('tags', [])
                                )
                                
                                output_file.write_text(md_content, encoding='utf-8')
                                result = {
                                    'video': video, 
                                    'success': True, 
                                    'file': str(output_file),
                                    'source': transcript.get('source', 'unknown')
                                }
                            else:
                                result['error'] = '無法獲取字幕'
                        except Exception as e:
                            result['error'] = str(e)[:50]
                        
                        return video_idx, result
                    
                    # 根據後端選擇處理方式
                    if whisper_backend in ['groq', 'openai'] and api_workers > 1:
                        # === API 後端：多線程並行處理 ===
                        from concurrent.futures import ThreadPoolExecutor, as_completed
                        
                        status_container.info(f"📦 批次 {batch_idx + 1}/{total_batches} - 多線程處理 ({api_workers} workers)")
                        
                        with ThreadPoolExecutor(max_workers=api_workers) as executor:
                            futures = {
                                executor.submit(process_single_video, (batch_start + i, video)): i 
                                for i, video in enumerate(batch_videos)
                            }
                            
                            for future in as_completed(futures):
                                video_idx, result = future.result()
                                results.append(result)
                                
                                if result['success']:
                                    st.session_state.processed_count += 1
                                else:
                                    error_msg = result.get('error', '未知錯誤')
                                    error_types[error_msg] = error_types.get(error_msg, 0) + 1
                                
                                # 更新進度
                                progress = int((len(results) / len(selected_videos)) * 100)
                                progress_bar.progress(progress, text=f"處理: {len(results)}/{len(selected_videos)}")
                    else:
                        # === MLX 後端：串行處理（優化 GPU 使用） ===
                        for i, video in enumerate(batch_videos):
                            video_idx = batch_start + i + 1
                            progress = int((video_idx / len(selected_videos)) * 100)
                            progress_bar.progress(progress, text=f"處理: {video_idx}/{len(selected_videos)} - {video['title'][:30]}...")
                            
                            _, result = process_single_video((batch_start + i, video))
                            results.append(result)
                            
                            if result['success']:
                                st.session_state.processed_count += 1
                            else:
                                error_msg = result.get('error', '未知錯誤')
                                error_types[error_msg] = error_types.get(error_msg, 0) + 1
                        

                    
                    # 批次完成後清理記憶體
                    del fetcher, extractor, injector
                    gc.collect()
                    
                    # 批次間短暫休息避免速率限制
                    if batch_idx < total_batches - 1:
                        time.sleep(1)
                
                # 計算執行統計
                elapsed_time = time.time() - start_time
                success_count = sum(1 for r in results if r['success'])
                fail_count = len(results) - success_count
                
                progress_bar.progress(100, text="✅ 完成!")
                
                # 顯示統計指標 (簡化版，因為不再跳過任何檔案)
                with metrics_placeholder.container():
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("✅ 成功", f"{success_count}/{len(results)}")
                    with col2:
                        st.metric("❌ 失敗", fail_count)
                    with col3:
                        st.metric("⏱️ 耗時", f"{elapsed_time:.1f}s")
                    
                    # 顯示錯誤分布
                    if error_types:
                        st.markdown("**錯誤類型分布:**")
                        for err, count in sorted(error_types.items(), key=lambda x: -x[1])[:5]:
                            st.caption(f"  • {err}: {count} 次")
                
                # 顯示結果
                if success_count > 0:
                    st.success(f"🎉 完成! 成功處理 {success_count}/{len(selected_videos)} 部影片")
                else:
                    st.error(f"❌ 處理失敗，請檢查網路連線或稍後再試")
                
                with st.expander("📋 處理結果詳情"):
                    for r in results:
                        if r['success']:
                            st.markdown(f"✅ **{r['video']['title'][:50]}...**")
                        else:
                            st.markdown(f"❌ **{r['video']['title'][:50]}...** - {r.get('error', '')}")
                
            except Exception as e:
                st.error(f"❌ 錯誤: {str(e)}")
            finally:
                st.session_state.processing = False

# 小紅書擷取頁面
elif page == "📱 小紅書":
    st.markdown("## 📱 小紅書擷取")
    
    st.info("""
    **使用方式**：貼上小紅書筆記連結（支援 xhslink.com 短網址）
    
    💡 如何獲取連結：在小紅書 App 或網頁版，點擊「分享」→「複製連結」
    """)
    
    # Session state for XHS notes
    if 'xhs_notes' not in st.session_state:
        st.session_state.xhs_notes = []
    if 'xhs_selected' not in st.session_state:
        st.session_state.xhs_selected = set()
    
    st.divider()
    
    # ========== 方式 A: 從用戶主頁獲取筆記列表 ==========
    st.markdown("### 📥 方式 A: 從用戶主頁獲取")
    
    # Chrome Debug 模式說明
    with st.expander("💡 如何啟用完整獲取模式（推薦）", expanded=False):
        st.markdown("""
        **Chrome Debug 模式可讓系統使用您的登入狀態獲取完整筆記列表：**
        
        1. **完全關閉 Chrome**（Command+Q）
        2. **執行以下終端命令**：
        ```bash
        /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222
        ```
        3. **在 Chrome 中登入小紅書**
        4. 返回此頁面，輸入主頁 URL 並點擊「獲取筆記列表」
        """)
    
    with st.form("xhs_profile_form"):
        profile_url = st.text_input(
            "輸入小紅書用戶主頁 URL",
            placeholder="https://www.xiaohongshu.com/user/profile/xxx 或 xhslink.com/xxx",
            help="支持完整主頁 URL 或分享的短連結"
        )
        col_a1, col_a2 = st.columns([1, 1])
        with col_a1:
            max_notes = st.number_input("最大筆記數", min_value=0, max_value=500, value=0, step=10, help="0 = 獲取全部")
        with col_a2:
            fetch_profile_btn = st.form_submit_button("🔍 獲取筆記列表", type="secondary", use_container_width=True)
    
    if fetch_profile_btn and profile_url:
        with st.spinner("正在獲取筆記列表..."):
            from scrapers.xiaohongshu_scraper import XiaohongshuScraper
            scraper = XiaohongshuScraper()
            
            # 嘗試獲取筆記
            notes = scraper.get_user_notes(profile_url, max_notes=max_notes)
            
            if notes:
                st.session_state.xhs_notes = notes
                st.session_state.xhs_selected = set(range(len(notes)))
                st.success(f"✅ 找到 {len(notes)} 個筆記")
                st.rerun()
            else:
                st.warning("""
                ⚠️ **無法自動獲取筆記列表**
                
                小紅書限制了未登入用戶的訪問。請使用以下替代方案:
                1. 在瀏覽器中登入小紅書
                2. 訪問用戶主頁，手動複製想要的筆記連結
                3. 貼到下方「方式 B」的輸入框中
                """)
                
                # 提供快捷按鈕打開主頁
                import webbrowser
                if st.button(f"🌐 在瀏覽器中打開主頁"):
                    webbrowser.open(profile_url)
    
    st.divider()
    
    # ========== 方式 B: 貼上筆記連結 ==========
    st.markdown("### 📋 方式 B: 貼上筆記連結")
    with st.form("xhs_url_form"):
        raw_text = st.text_area(
            "貼上包含筆記連結的文字",
            placeholder="例如:\n分享一個很棒的創業心得 https://xhslink.com/xxx\n另一個好內容 https://www.xiaohongshu.com/explore/yyy",
            height=150
        )
        col1, col2 = st.columns([3, 1])
        with col1:
            parse_btn = st.form_submit_button("📋 解析連結", type="secondary")
        with col2:
            fetch_titles = st.checkbox("獲取真實標題", value=False, help="較慢但顯示影片真實標題")
    
    if parse_btn and raw_text:
        # 提取 URL
        import re
        import subprocess
        url_pattern = re.compile(r'https?://[^\s,;"\'\<\>]+')
        all_urls = url_pattern.findall(raw_text)
        
        # 過濾出小紅書相關連結
        xhs_urls = [url for url in all_urls if 'xhslink.com' in url or 'xiaohongshu.com' in url]
        
        if xhs_urls:
            notes = []
            progress_text = st.empty()
            
            if fetch_titles:
                # === 多線程獲取真實標題 ===
                from concurrent.futures import ThreadPoolExecutor
                
                def get_title(args):
                    i, url = args
                    title = None
                    
                    # 策略 1: 優先從輸入文字提取（最可靠）
                    lines = raw_text.split('\n')
                    for line in lines:
                        if url in line:
                            before_url = line.split(url)[0].strip()
                            if before_url and len(before_url) > 2:
                                title = before_url[:60]
                                break
                    
                    # 策略 2: 若無文字，使用 yt-dlp 獲取真實標題
                    if not title:
                        try:
                            result = subprocess.run(
                                ["yt-dlp", "--get-title", "--cookies-from-browser", "chrome", 
                                 "--no-warnings", "--ignore-errors", url],
                                capture_output=True, text=True, timeout=25
                            )
                            if result.returncode == 0 and result.stdout.strip():
                                title = result.stdout.strip()[:60]
                        except Exception:
                            pass
                    
                    return i, url, title if title else f'小紅書筆記 #{i+1}'
                
                progress_text.info(f"🔍 多線程解析中 ({len(xhs_urls)} 個連結)...")
                
                with ThreadPoolExecutor(max_workers=10) as executor:
                    results = list(executor.map(get_title, enumerate(xhs_urls)))
                
                for i, url, title in sorted(results, key=lambda x: x[0]):
                    notes.append({
                        'title': title,
                        'url': url,
                        'note_id': url.split('/')[-1][:10] if '/' in url else f'note_{i}',
                        'type': 'video'
                    })
            else:
                # === 快速模式：從輸入文字提取或使用編號 ===
                for i, url in enumerate(xhs_urls):
                    title = None
                    lines = raw_text.split('\n')
                    for line in lines:
                        if url in line:
                            before_url = line.split(url)[0].strip()
                            if before_url and len(before_url) > 2:
                                title = before_url[:50]
                                break
                    
                    if not title:
                        title = f'小紅書筆記 #{i+1}'
                    
                    notes.append({
                        'title': title,
                        'url': url,
                        'note_id': url.split('/')[-1][:10] if '/' in url else f'note_{i}',
                        'type': 'video'
                    })
            
            progress_text.empty()
            st.session_state.xhs_notes = notes
            st.session_state.xhs_selected = set(range(len(notes)))
            st.success(f"✅ 找到 {len(notes)} 個小紅書連結")
            st.rerun()
        else:
            st.error("❌ 未找到有效的小紅書連結")
    
    # ========== 步驟 2: 顯示連結列表與選擇 ==========
    if st.session_state.xhs_notes:
        st.markdown("### 📝 連結列表")
        
        # 全選/清除按鈕
        col1, col2 = st.columns(2)
        with col1:
            select_all = st.button("✅ 全選", key="xhs_select_all", use_container_width=True)
        with col2:
            clear_all = st.button("❌ 清除", key="xhs_clear_all", use_container_width=True)
        
        # 處理按鈕點擊
        if select_all:
            for i in range(len(st.session_state.xhs_notes)):
                st.session_state.xhs_selected.add(i)
            st.rerun()
        if clear_all:
            st.session_state.xhs_selected.clear()
            st.rerun()
        
        # 顯示連結列表 - 使用 callback 確保狀態同步
        def toggle_selection(idx):
            if idx in st.session_state.xhs_selected:
                st.session_state.xhs_selected.discard(idx)
            else:
                st.session_state.xhs_selected.add(idx)
        
        for idx, note in enumerate(st.session_state.xhs_notes):
            checkbox_key = f"xhs_note_{idx}"
            
            # 確保 session state 初始化
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = idx in st.session_state.xhs_selected
            
            # 使用 on_change 回調同步狀態
            def on_checkbox_change(note_idx, key):
                if st.session_state[key]:
                    st.session_state.xhs_selected.add(note_idx)
                else:
                    st.session_state.xhs_selected.discard(note_idx)
            
            st.checkbox(
                f"**{note['title']}** - `{note['url'][:50]}...`",
                key=checkbox_key,
                on_change=on_checkbox_change,
                args=(idx, checkbox_key)
            )
        
        st.caption(f"**已選擇: {len(st.session_state.xhs_selected)}/{len(st.session_state.xhs_notes)}**")
        
        st.divider()
        
        # ========== 步驟 3: 開始處理 ==========
        st.markdown("### 🎬 開始處理")
        
        # 處理設定 (對標 YouTube 頁面)
        with st.expander("⚙️ 處理設定", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                xhs_batch_size = st.slider("批次大小", min_value=1, max_value=10, value=5,
                                           help="每批處理的筆記數量", key="xhs_batch_size")
            with col2:
                xhs_whisper_backend = st.selectbox(
                    "Whisper 後端",
                    options=["groq", "mlx", "openai"],
                    format_func=lambda x: {
                        "groq": "⚡ Groq (免費超快)",
                        "mlx": "🖥️ MLX (本地 GPU)", 
                        "openai": "🔷 OpenAI (付費)"
                    }.get(x, x),
                    key="xhs_whisper_backend"
                )
            with col3:
                if xhs_whisper_backend in ["groq", "openai"]:
                    xhs_api_workers = st.slider("API 並行", min_value=1, max_value=5, value=3,
                                                help="API 並行請求數 (建議 3)", key="xhs_api_workers")
                else:
                    xhs_api_workers = 1
                    st.caption("🖥️ 本地處理")
            with col4:
                xhs_auto_cleanup = st.selectbox(
                    "臨時檔清理",
                    options=["即時刪除", "保留3天", "不刪除"],
                    index=0,
                    help="處理完成後如何處理音頻檔",
                    key="xhs_auto_cleanup"
                )
        
        if st.button("🚀 開始下載並處理", type="primary", 
                     disabled=len(st.session_state.xhs_selected) == 0 or st.session_state.processing,
                     key="xhs_start_process"):
            
            st.session_state.processing = True
            selected_notes = [st.session_state.xhs_notes[i] for i in sorted(st.session_state.xhs_selected)]
            
            # 初始化處理器
            from scrapers.xiaohongshu_scraper import XiaohongshuScraper
            from scrapers.transcript_fetcher import TranscriptFetcher
            from processors.knowledge_extractor import KnowledgeExtractor
            from processors.metadata_injector import MetadataInjector
            
            output_dir = Path.home() / "Documents" / "MediaMiner_Data" / "processed"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            progress_bar = st.progress(0, text="準備中...")
            status_placeholder = st.empty()  # 詳細狀態顯示
            metrics_placeholder = st.empty()
            
            results = []
            import time
            start_time = time.time()
            
            try:
                fetcher = TranscriptFetcher()
                extractor = KnowledgeExtractor()
                injector = MetadataInjector()
                
                # 清理過期臨時檔案 (保留3天模式)
                if xhs_auto_cleanup == "保留3天":
                    fetcher.cleanup_temp_files(max_age_days=3)
                
                # 用於顯示當前狀態的變數
                current_status = {"msg": "準備中...", "steps": []}
                
                # === 單筆處理函數（包含步驟記錄）===
                def process_single_note(note, note_idx=0, total=1):
                    steps = []  # 收集處理步驟
                    
                    try:
                        # 進度回調函數 - 記錄步驟
                        def on_progress(msg):
                            steps.append(msg)
                            current_status["msg"] = f"[{note_idx+1}/{total}] {note['title'][:15]}... | {msg}"
                        
                        on_progress("📥 開始處理...")
                        
                        transcript = fetcher.fetch(
                            note['url'],
                            whisper_backend=xhs_whisper_backend,
                            whisper_model='large-v3-turbo',
                            progress_callback=on_progress
                        )
                        
                        if transcript:
                            on_progress("📝 知識提取中...")
                            knowledge_result = extractor.process_transcript(
                                transcript['text'],
                                video_info={
                                    'title': note['title'],
                                    'channel': '小紅書',
                                    'duration': None
                                }
                            )
                            
                            knowledge_str = knowledge_result.get('knowledge', '') if isinstance(knowledge_result, dict) else str(knowledge_result)
                            
                            on_progress("💾 寫入檔案中...")
                            filename = injector.generate_safe_filename(note['title'])
                            output_file = output_dir / f"{filename}.md"
                            
                            # 提取識別到的 guest
                            guest = knowledge_result.get('guest') if isinstance(knowledge_result, dict) else None
                            
                            md_content = injector.create_markdown(
                                content=transcript.get('text', ''),
                                knowledge=knowledge_str,
                                video_info={
                                    'title': note['title'],
                                    'url': note['url'],
                                    'source': '小紅書',
                                    'platform': 'xiaohongshu',
                                    'guest': guest  # 訪談嘉賓
                                },
                                summary=knowledge_result.get('summary', '') if isinstance(knowledge_result, dict) else '',
                                keywords=knowledge_result.get('keywords', []) if isinstance(knowledge_result, dict) else [],
                                entities=knowledge_result.get('entities', []) if isinstance(knowledge_result, dict) else [],
                                tags=knowledge_result.get('tags', []) if isinstance(knowledge_result, dict) else []
                            )
                            
                            output_file.write_text(md_content, encoding='utf-8')
                            on_progress("✅ 完成!")
                            return {'note': note, 'success': True, 'file': str(output_file), 'steps': steps}
                        else:
                            on_progress("❌ 無法獲取逐字稿")
                            return {'note': note, 'success': False, 'error': '無法獲取逐字稿（可能是純圖片筆記）', 'steps': steps}
                            
                    except Exception as e:
                        steps.append(f"❌ 錯誤: {str(e)[:50]}")
                        return {'note': note, 'success': False, 'error': str(e)[:100], 'steps': steps}
                
                # === 多線程處理 (API模式) / 串行處理 (本地模式) ===
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                total_notes = len(selected_notes)
                log_container = st.container()  # 用於顯示處理日誌
                
                if xhs_whisper_backend in ["groq", "openai"] and xhs_api_workers > 1:
                    # 多線程並行處理
                    with ThreadPoolExecutor(max_workers=xhs_api_workers) as executor:
                        futures = {executor.submit(process_single_note, note, i, total_notes): (i, note) 
                                   for i, note in enumerate(selected_notes)}
                        completed = 0
                        for future in as_completed(futures):
                            completed += 1
                            progress = int((completed / total_notes) * 100)
                            idx, note = futures[future]
                            result = future.result()
                            
                            progress_bar.progress(progress, text=f"✅ 完成: {completed}/{total_notes}")
                            
                            # 顯示該筆記的處理步驟
                            with log_container:
                                steps_str = " → ".join(result.get('steps', []))
                                if result['success']:
                                    st.success(f"**[{completed}] {note['title'][:25]}...** | {steps_str}")
                                else:
                                    st.error(f"**[{completed}] {note['title'][:25]}...** | {steps_str}")
                            
                            results.append(result)
                            if result['success']:
                                pass  # 成功計數已在上方處理
                else:
                    # 串行處理
                    for i, note in enumerate(selected_notes):
                        progress_bar.progress(int((i / total_notes) * 100), text=f"處理: {i+1}/{total_notes} - {note['title'][:20]}...")
                        status_placeholder.info(f"🔄 處理中: {note['title'][:30]}...")
                        
                        result = process_single_note(note, i, total_notes)
                        
                        # 顯示該筆記的處理步驟
                        progress_bar.progress(int(((i+1) / total_notes) * 100), text=f"✅ 完成: {i+1}/{total_notes}")
                        with log_container:
                            steps_str = " → ".join(result.get('steps', []))
                            if result['success']:
                                st.success(f"**[{i+1}] {note['title'][:25]}...** | {steps_str}")
                            else:
                                st.error(f"**[{i+1}] {note['title'][:25]}...** | {steps_str}")
                        
                        results.append(result)
                        if result['success']:
                            pass  # 成功計數已在上方處理
                
                status_placeholder.empty()
                
                # 統計結果
                elapsed_time = time.time() - start_time
                success_count = sum(1 for r in results if r['success'])
                
                progress_bar.progress(100, text="✅ 完成!")
                
                with metrics_placeholder.container():
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("✅ 成功", f"{success_count}/{len(results)}")
                    with col2:
                        st.metric("❌ 失敗", len(results) - success_count)
                    with col3:
                        st.metric("⏱️ 耗時", f"{elapsed_time:.1f}s")
                
                if success_count > 0:
                    st.success(f"🎉 完成! 成功處理 {success_count}/{len(selected_notes)} 個筆記")
                else:
                    st.warning("⚠️ 處理失敗。小紅書筆記可能是純圖片，無法提取語音逐字稿。")
                
                # 顯示失敗詳情
                failed_results = [r for r in results if not r['success']]
                if failed_results:
                    with st.expander("📋 失敗詳情", expanded=True):
                        for r in failed_results:
                            st.error(f"**{r['note']['title']}**: {r.get('error', '未知錯誤')}")
                    
            except Exception as e:
                st.error(f"❌ 發生錯誤: {str(e)}")
                import traceback
                st.code(traceback.format_exc(), language="text")
            finally:
                st.session_state.processing = False

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
