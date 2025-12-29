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

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    YOUTUBE_TRANSCRIPT_API_AVAILABLE = False


class TranscriptFetcher:
    """逐字稿擷取器類"""
    
    SUBTITLE_LANGS = ["zh-TW", "zh-Hant", "zh-CN", "zh-Hans", "zh", "en"]
    
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
        temp_dir = self.output_dir / "_temp"
        temp_dir.mkdir(exist_ok=True)
        
        langs = ",".join(self.SUBTITLE_LANGS)
        
        # 先嘗試手動字幕
        for auto_flag in ["--write-sub", "--write-auto-sub"]:
            cmd = [
                "yt-dlp",
                "--skip-download",
                auto_flag,
                "--sub-langs", langs,
                "--sub-format", "vtt/srt/best",
                "-o", str(temp_dir / "%(id)s.%(ext)s"),
                video_url
            ]
            
            try:
                subprocess.run(cmd, capture_output=True, check=True)
                
                # 查找字幕檔案
                for ext in ['.vtt', '.srt']:
                    for f in temp_dir.glob(f"*{ext}"):
                        text = self._parse_subtitle_file(f)
                        lang = self._detect_language_from_filename(f.name)
                        return {
                            'text': text,
                            'language': lang,
                            'source': 'yt-dlp',
                            'file': str(f),
                            'is_auto': 'auto' in auto_flag
                        }
            except subprocess.CalledProcessError:
                continue
        
        return None
    
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
        
        # 下載音訊
        audio_file = temp_dir / "audio.mp3"
        
        # 清理舊檔案
        if audio_file.exists():
            audio_file.unlink()
        
        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "-o", str(audio_file),
            "--cookies-from-browser", "chrome",
            video_url
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        except subprocess.CalledProcessError as e:
            print(f"Failed to download audio: {e}")
            return None
        except subprocess.TimeoutExpired:
            print("Audio download timeout")
            return None
        
        if not audio_file.exists():
            for ext in ['.mp3', '.m4a', '.webm', '.opus']:
                alt_file = temp_dir / f"audio{ext}"
                if alt_file.exists():
                    audio_file = alt_file
                    break
        
        if not audio_file.exists():
            print("Audio file not found")
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
            
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                print("⚠️ GROQ_API_KEY 未設置")
                return None
            
            client = Groq(api_key=api_key)
            
            print("⏳ 使用 Groq Whisper API (免費, 超快)...")
            with open(audio_file, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    file=(audio_file.name, f.read()),
                    model="whisper-large-v3",
                    response_format="text"
                )
            
            return {
                'text': transcription,
                'language': 'auto',
                'source': 'groq-whisper',
                'model': 'whisper-large-v3'
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
    
    def _whisper_mlx(self, audio_file: Path, model: str = "small") -> Optional[Dict]:
        """使用 MLX-Whisper (Apple Silicon GPU 加速)"""
        try:
            import mlx_whisper
            
            print(f"⏳ 使用 MLX-Whisper ({model}) GPU 加速辨識中...")
            result = mlx_whisper.transcribe(
                str(audio_file),
                path_or_hf_repo=f"mlx-community/whisper-{model}-mlx",
            )
            
            text = result.get("text", "")
            language = result.get("language", "auto")
            
            if text:
                return {
                    'text': text,
                    'language': language,
                    'source': 'mlx-whisper',
                    'model': model
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
              whisper_backend: str = "mlx", whisper_model: str = "small") -> Optional[Dict]:
        """
        智能擷取逐字稿
        優先順序: YouTube API → yt-dlp → Whisper
        
        Args:
            video_url: 影片 URL
            use_whisper_fallback: 是否使用 Whisper 備用
            whisper_backend: Whisper 後端 (mlx/groq/openai)
            whisper_model: Whisper 模型 (僅 mlx 使用)
            
        Returns:
            逐字稿資訊
        """
        # 提取 video_id
        video_id = self._extract_video_id(video_url)
        
        # 1. 嘗試 YouTube API
        if video_id and YOUTUBE_TRANSCRIPT_API_AVAILABLE:
            result = self.fetch_youtube_transcript(video_id)
            if result:
                print(f"✅ 使用 YouTube API 獲取字幕 (語言: {result['language']})")
                return result
        
        # 2. 嘗試 yt-dlp
        result = self.fetch_with_ytdlp(video_url)
        if result:
            print(f"✅ 使用 yt-dlp 獲取字幕 (語言: {result['language']})")
            return result
        
        # 3. Whisper 備用
        if use_whisper_fallback:
            print(f"⏳ 字幕不可用，使用 Whisper ({whisper_backend}) 進行語音辨識...")
            result = self.fetch_with_whisper(video_url, model=whisper_model, backend=whisper_backend)
            if result:
                print(f"✅ 使用 {result.get('source', 'Whisper')} 完成語音辨識")
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


if __name__ == "__main__":
    fetcher = TranscriptFetcher()
    
    # 測試
    test_url = "https://www.youtube.com/watch?v=example"
    
    print("🎬 MediaMiner Transcript Fetcher")
    print("=" * 50)
    print(f"Output dir: {fetcher.output_dir}")
