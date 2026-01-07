#!/usr/bin/env python3
"""
逐字稿擷取器
從多種來源擷取影片逐字稿
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

# 載入環境變數
from dotenv import load_dotenv
load_dotenv()

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPT_API_AVAILABLE = False


class TranscriptFetcher:
    """逐字稿擷取器類"""
    
    # 語言優先順序配置
    # 英文內容：優先原語言 (English first)
    SUBTITLE_LANGS_EN = ["en", "en-US", "en-GB", "en-AU"]
    # 中文內容：優先繁體中文
    SUBTITLE_LANGS_ZH = ["zh-TW", "zh-Hant", "zh-CN", "zh-Hans", "zh"]
    # 預設：原語言優先 (英文優先於中文)
    SUBTITLE_LANGS = ["en", "en-US", "zh-TW", "zh-Hant", "zh-CN", "zh-Hans", "zh"]
    
    def __init__(self, output_dir: str = "~/Documents/MediaMiner_Data/raw"):
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def fetch_youtube_transcript(self, video_id: str) -> Optional[Dict]:
        """
        使用 YouTube Transcript API 獲取逐字稿
        
        Args:
            video_id: YouTube 影片 ID
            
        Returns:
            {'text': ..., 'language': ..., 'source': 'youtube_api'}
        """
        if not YOUTUBE_TRANSCRIPT_API_AVAILABLE:
            return None
            
        try:
            # 嘗試獲取字幕
            for lang in self.SUBTITLE_LANGS:
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                    text = '\n'.join([e['text'] for e in transcript])
                    return {
                        'text': text,
                        'language': lang,
                        'source': 'youtube_api',
                        'is_auto': False
                    }
                except:
                    continue
            
            # 嘗試任意可用字幕
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
                text = '\n'.join([e['text'] for e in transcript])
                return {
                    'text': text,
                    'language': 'auto',
                    'source': 'youtube_api',
                    'is_auto': True
                }
            except:
                pass
                
        except Exception as e:
            print(f"YouTube Transcript API error: {e}")
        
        return None
    
    def fetch_with_ytdlp(self, video_url: str) -> Optional[Dict]:
        """
        使用 yt-dlp 下載字幕
        
        Args:
            video_url: 影片 URL
            
        Returns:
            {'text': ..., 'language': ..., 'source': 'yt-dlp', 'file': ...}
        """
        import uuid
        
        # 提取 video_id 用於精確匹配
        video_id = self._extract_video_id(video_url)
        
        # 使用唯一的臨時目錄避免多線程/批次污染
        unique_id = str(uuid.uuid4())[:8]
        temp_dir = self.output_dir / "_temp" / f"yt_{unique_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        langs = ",".join(self.SUBTITLE_LANGS)
        
        try:
            # 先嘗試手動字幕，再嘗試自動字幕
            for auto_flag in ["--write-sub", "--write-auto-sub"]:
                cmd = [
                    "yt-dlp",
                    "--skip-download",
                    auto_flag,
                    "--sub-langs", langs,
                    "--sub-format", "vtt/srt/best",
                    "-o", str(temp_dir / "%(id)s.%(ext)s"),
                    "--cookies-from-browser", "chrome",
                    video_url
                ]
                
                try:
                    subprocess.run(cmd, capture_output=True, check=True, timeout=60)
                    
                    # 查找這個影片的字幕檔案 (使用 video_id 精確匹配)
                    for ext in ['.vtt', '.srt']:
                        # 優先匹配 video_id
                        if video_id:
                            pattern = f"{video_id}*{ext}"
                        else:
                            pattern = f"*{ext}"
                        
                        for f in temp_dir.glob(pattern):
                            text = self._parse_subtitle_file(f)
                            lang = self._detect_language_from_filename(f.name)
                            
                            # 清理臨時檔案
                            try:
                                import shutil
                                shutil.rmtree(temp_dir)
                            except: pass
                            
                            return {
                                'text': text,
                                'language': lang,
                                'source': 'yt-dlp',
                                'file': str(f),
                                'is_auto': 'auto' in auto_flag
                            }
                except subprocess.CalledProcessError:
                    continue
                except subprocess.TimeoutExpired:
                    continue
            
            return None
        finally:
            # 確保清理臨時目錄
            try:
                import shutil
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except: pass
    
    def fetch_with_whisper(self, video_url: str, model: str = "small", backend: str = "mlx") -> Optional[Dict]:
        """
        使用 Whisper 進行語音辨識
        
        Args:
            video_url: 影片 URL
            model: Whisper 模型 (tiny/base/small/medium/large-v3)
            backend: 
                - "mlx": Apple Silicon GPU 加速 (本地)
                - "groq": Groq API (免費, 超快)
                - "openai": OpenAI API (付費, 最準確)
            
        Returns:
            {'text': ..., 'language': ..., 'source': 'whisper'}
        """
        temp_dir = self.output_dir / "_temp"
        temp_dir.mkdir(exist_ok=True)
        
        # 使用唯一檔名避免多線程衝突
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        audio_file = temp_dir / f"audio_{unique_id}.mp3"
        
        # 下載音訊 (低音質足夠語音辨識，節省頻寬)
        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "5",  # 較低音質 (~64kbps)，足夠辨識
            "-o", str(audio_file),
            "--cookies-from-browser", "chrome",
            "--no-warnings",
            video_url
        ]
        
        print(f"⏳ 下載音頻中...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5分鐘超時
            if result.returncode != 0:
                error_msg = result.stderr[:200] if result.stderr else "未知錯誤"
                print(f"❌ 音頻下載失敗: {error_msg}")
                return None
        except subprocess.TimeoutExpired:
            print("❌ 音頻下載超時 (>5分鐘)")
            return None
        
        if not audio_file.exists():
            # 搜索相同 UUID 前綴的其他格式
            base_name = f"audio_{unique_id}"
            for ext in ['.mp3', '.m4a', '.webm', '.opus', '.mp4']:
                alt_file = temp_dir / f"{base_name}{ext}"
                if alt_file.exists():
                    audio_file = alt_file
                    break
        
        if not audio_file.exists():
            # 搜索任何最近的音頻檔
            audio_files = list(temp_dir.glob("audio_*.*"))
            if audio_files:
                audio_file = max(audio_files, key=lambda f: f.stat().st_mtime)
                print(f"⚠️ 找到替代音頻檔: {audio_file.name}")
        
        if not audio_file.exists():
            print("❌ 音頻檔案未找到")
            return None
        
        result = None
        
        # === Backend: Groq API (免費, 超快) ===
        if backend == "groq":
            result = self._whisper_groq(audio_file)
        
        # === Backend: OpenAI API (付費, 最準確) ===
        elif backend == "openai":
            result = self._whisper_openai(audio_file)
        
        # === Backend: MLX (本地 GPU 加速) ===
        elif backend == "mlx":
            result = self._whisper_mlx(audio_file, model)
        
        # 清理暫存檔
        try:
            audio_file.unlink()
        except:
            pass
        
        return result
    
    def _whisper_groq(self, audio_file: Path) -> Optional[Dict]:
        """使用 Groq Whisper API (免費, 超快)"""
        try:
            from groq import Groq
            
            # 支援多帳號輪換 (與 llm_client.py 一致)
            api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY_1")
            if not api_key:
                print("⚠️ GROQ_API_KEY 或 GROQ_API_KEY_1 未設置")
                return None
            
            client = Groq(api_key=api_key)
            
            # 使用 Turbo 版本 - 速度快 2-3 倍，品質接近 large-v3
            print("⏳ 使用 Groq Whisper API (large-v3-turbo)...")
            with open(audio_file, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    file=(audio_file.name, f.read()),
                    model="whisper-large-v3-turbo",  # Turbo 版本更快
                    response_format="text"
                )
            
            return {
                'text': transcription,
                'language': 'auto',
                'source': 'groq-whisper',
                'model': 'whisper-large-v3-turbo'
            }
        except ImportError:
            print("groq package not installed. Run: pip install groq")
        except Exception as e:
            print(f"Groq Whisper error: {e}")
        return None
    
    def _whisper_openai(self, audio_file: Path) -> Optional[Dict]:
        """使用 OpenAI Whisper API (付費, 最準確)"""
        try:
            from openai import OpenAI
            
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                print("⚠️ OPENAI_API_KEY 未設置")
                return None
            
            client = OpenAI(api_key=api_key)
            
            print("⏳ 使用 OpenAI Whisper API...")
            with open(audio_file, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            
            return {
                'text': transcription.text,
                'language': 'auto',
                'source': 'openai-whisper',
                'model': 'whisper-1'
            }
        except ImportError:
            print("openai package not installed. Run: pip install openai")
        except Exception as e:
            print(f"OpenAI Whisper error: {e}")
        return None
    
    def _whisper_mlx(self, audio_file: Path, model: str = "large-v3-turbo") -> Optional[Dict]:
        """使用 MLX-Whisper Turbo (Apple Silicon GPU 加速)"""
        try:
            import mlx_whisper
            
            # 統一使用 Turbo 模型 (最佳性價比)
            mlx_model = "mlx-community/whisper-large-v3-turbo"
            print(f"⏳ 使用 MLX-Whisper Turbo (GPU 加速) 辨識中...")
            
            # 根據 URL 判斷語言（小紅書默認中文）
            force_lang = None
            if hasattr(self, '_current_url') and self._current_url:
                if 'xiaohongshu' in self._current_url or 'xhslink' in self._current_url:
                    force_lang = 'zh'
                    print(f"   📌 小紅書內容，強制使用中文辨識")
            
            transcribe_kwargs = {
                'audio': str(audio_file),
                'path_or_hf_repo': mlx_model,
            }
            if force_lang:
                transcribe_kwargs['language'] = force_lang
            
            result = mlx_whisper.transcribe(**transcribe_kwargs)
            
            text = result.get("text", "")
            language = result.get("language", force_lang or "auto")
            
            if text:
                return {
                    'text': text,
                    'language': language,
                    'source': 'mlx-whisper',
                    'model': 'large-v3-turbo'
                }
                
        except ImportError:
            print("MLX-Whisper not installed, falling back to CLI whisper")
            try:
                cmd = [
                    "whisper",
                    str(audio_file),
                    "--model", model,
                    "--output_format", "txt",
                    "--output_dir", str(audio_file.parent)
                ]
                
                subprocess.run(cmd, capture_output=True, check=True, timeout=600)
                
                txt_file = audio_file.parent / "audio.txt"
                if txt_file.exists():
                    text = txt_file.read_text(encoding='utf-8')
                    return {
                        'text': text,
                        'language': 'auto',
                        'source': 'whisper-cli',
                        'model': model
                    }
            except Exception as e:
                print(f"Whisper CLI error: {e}")
        
        except Exception as e:
            print(f"MLX-Whisper error: {e}")
        
        return None
    
    def fetch(self, video_url: str, use_whisper_fallback: bool = True, 
              whisper_backend: str = "mlx", whisper_model: str = "small",
              progress_callback=None, prefer_original_lang: bool = True) -> Optional[Dict]:
        """
        智能擷取逐字稿
        優先順序: YouTube API → yt-dlp → Whisper
        
        Args:
            video_url: 影片 URL
            use_whisper_fallback: 是否使用 Whisper 備用
            whisper_backend: Whisper 後端 (mlx/groq/openai)
            whisper_model: Whisper 模型 (僅 mlx 使用)
            progress_callback: 進度回調函數 (接收字符串訊息)
            prefer_original_lang: True=優先保留原語言 (英文內容保持英文)
            
        Returns:
            逐字稿資訊
        """
        def update_progress(msg: str):
            print(msg)  # 保留終端輸出
            if progress_callback:
                progress_callback(msg)
        
        # 記錄當前 URL 供 Whisper 語言檢測使用
        self._current_url = video_url
        
        # 提取 video_id
        video_id = self._extract_video_id(video_url)
        
        # 1. 嘗試 YouTube API
        if video_id and YOUTUBE_TRANSCRIPT_API_AVAILABLE:
            update_progress("📥 檢查 YouTube 字幕...")
            result = self.fetch_youtube_transcript(video_id)
            if result:
                update_progress(f"✅ 使用 YouTube API 獲取字幕 (語言: {result['language']})")
                return result
        
        # 2. 嘗試 yt-dlp 獲取內嵌字幕
        update_progress("📥 下載內嵌字幕中...")
        result = self.fetch_with_ytdlp(video_url)
        if result:
            lang = result.get('language', '')
            is_chinese = lang.startswith('zh') or lang in ['zh', 'zh-TW', 'zh-CN', 'zh-Hans', 'zh-Hant']
            is_english = lang.startswith('en') or lang in ['en', 'en-US', 'en-GB']
            
            # 小紅書內容：必須使用中文字幕
            is_xhs = 'xiaohongshu' in video_url or 'xhslink' in video_url
            
            if is_xhs and is_chinese:
                update_progress(f"✅ 使用 yt-dlp 獲取中文字幕 (語言: {lang})")
                return result
            elif is_xhs and not is_chinese:
                # 小紅書內容但只有英文字幕，改用 Whisper 中文辨識
                update_progress(f"⚠️ 僅有英文字幕，改用 Whisper 中文辨識...")
            elif prefer_original_lang:
                # 非小紅書：優先保留原語言（英文內容保持英文）
                update_progress(f"✅ 使用 yt-dlp 獲取原語言字幕 (語言: {lang})")
                return result
            else:
                # 舊行為：接受任何語言
                update_progress(f"✅ 使用 yt-dlp 獲取字幕 (語言: {lang})")
                return result
        
        # 3. Whisper 備用
        if use_whisper_fallback:
            backend_names = {"groq": "Groq API", "openai": "OpenAI API", "mlx": "MLX 本地 GPU"}
            update_progress(f"🎤 準備 Whisper 語音辨識 ({backend_names.get(whisper_backend, whisper_backend)})...")
            result = self.fetch_with_whisper(video_url, model=whisper_model, backend=whisper_backend)
            if result:
                update_progress(f"✅ {result.get('source', 'Whisper')} 語音辨識完成")
                return result
        
        print("❌ 無法獲取逐字稿")
        return None
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """從 URL 提取 YouTube 影片 ID"""
        patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11})(?:[&?/]|$)',
            r'youtu\.be/([0-9A-Za-z_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def _parse_subtitle_file(self, file_path: Path) -> str:
        """解析字幕檔案為純文字"""
        content = file_path.read_text(encoding='utf-8')
        
        lines = content.split('\n')
        text_lines = []
        
        for line in lines:
            line = line.strip()
            # 跳過時間軸和序號
            if re.match(r'^\d{2}:\d{2}', line) or re.match(r'^\d+$', line):
                continue
            if line.startswith('WEBVTT') or '-->' in line:
                continue
            # 移除 HTML 標籤
            line = re.sub(r'<[^>]+>', '', line)
            if line:
                text_lines.append(line)
        
        # 去重
        unique_lines = []
        prev = ""
        for line in text_lines:
            if line != prev:
                unique_lines.append(line)
                prev = line
        
        return '\n'.join(unique_lines)
    
    def _detect_language_from_filename(self, filename: str) -> str:
        """從檔名偵測語言"""
        lang_patterns = {
            'zh-TW': ['zh-TW', 'zh-Hant', 'Traditional'],
            'zh-CN': ['zh-CN', 'zh-Hans', 'Simplified'],
            'en': ['en', 'English']
        }
        for lang, patterns in lang_patterns.items():
            for p in patterns:
                if p.lower() in filename.lower():
                    return lang
        return 'unknown'
    
    def delete_audio_file(self, audio_path: Path) -> bool:
        """刪除指定音頻檔案"""
        try:
            if audio_path and audio_path.exists():
                audio_path.unlink()
                return True
        except Exception as e:
            print(f"刪除失敗: {e}")
        return False
    
    def cleanup_temp_files(self, max_age_days: int = 3) -> int:
        """
        清理過期臨時檔案
        
        Args:
            max_age_days: 檔案最大保留天數
            
        Returns:
            刪除的檔案數量
        """
        import time
        temp_dir = self.output_dir / "_temp"
        if not temp_dir.exists():
            return 0
        
        deleted = 0
        now = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        
        for f in temp_dir.glob("*"):
            if f.is_file():
                file_age = now - f.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        f.unlink()
                        deleted += 1
                    except Exception:
                        pass
        
        if deleted > 0:
            print(f"🧹 清理了 {deleted} 個過期臨時檔案")
        return deleted


if __name__ == "__main__":
    fetcher = TranscriptFetcher()
    
    # 測試
    test_url = "https://www.youtube.com/watch?v=example"
    
    print("🎬 MediaMiner Transcript Fetcher")
    print("=" * 50)
    print(f"Output dir: {fetcher.output_dir}")
