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
    
    def __init__(self, output_dir: str = "~/Documents/Crawl_R2R_Data/raw"):
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
    
    def fetch_with_whisper(self, video_url: str, model: str = "large-v3") -> Optional[Dict]:
        """
        使用 Whisper 進行語音辨識
        
        Args:
            video_url: 影片 URL
            model: Whisper 模型
            
        Returns:
            {'text': ..., 'language': ..., 'source': 'whisper'}
        """
        temp_dir = self.output_dir / "_temp"
        temp_dir.mkdir(exist_ok=True)
        
        # 下載音訊
        audio_file = temp_dir / "audio.mp3"
        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "-o", str(audio_file),
            video_url
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to download audio: {e}")
            return None
        
        # 使用 Whisper 辨識
        try:
            cmd = [
                "whisper",
                str(audio_file),
                "--model", model,
                "--output_format", "txt",
                "--output_dir", str(temp_dir)
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            
            # 讀取輸出
            txt_file = temp_dir / "audio.txt"
            if txt_file.exists():
                text = txt_file.read_text(encoding='utf-8')
                return {
                    'text': text,
                    'language': 'auto',
                    'source': 'whisper',
                    'model': model
                }
        except subprocess.CalledProcessError as e:
            print(f"Whisper error: {e}")
        
        return None
    
    def fetch(self, video_url: str, use_whisper_fallback: bool = True) -> Optional[Dict]:
        """
        智能擷取逐字稿
        優先順序: YouTube API → yt-dlp → Whisper
        
        Args:
            video_url: 影片 URL
            use_whisper_fallback: 是否使用 Whisper 備用
            
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
            print("⏳ 字幕不可用，使用 Whisper 進行語音辨識...")
            result = self.fetch_with_whisper(video_url)
            if result:
                print(f"✅ 使用 Whisper 完成語音辨識")
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
    
    print("🎬 Crawl_R2R Transcript Fetcher")
    print("=" * 50)
    print(f"Output dir: {fetcher.output_dir}")
