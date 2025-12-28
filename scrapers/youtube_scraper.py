#!/usr/bin/env python3
"""
YouTube 頻道爬蟲
批次列舉頻道所有影片並下載字幕
"""

import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import re

class YouTubeScraper:
    """YouTube 頻道爬蟲類"""
    
    def __init__(self, output_dir: str = "~/Documents/Crawl_R2R_Data/raw"):
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def get_channel_videos(self, channel_url: str, max_videos: int = 100) -> List[Dict]:
        """
        列舉頻道所有影片
        
        Args:
            channel_url: YouTube 頻道 URL
            max_videos: 最大影片數量
            
        Returns:
            影片列表 [{'id': ..., 'title': ..., 'url': ...}, ...]
        """
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--dump-json",
            "--playlist-end", str(max_videos),
            channel_url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            videos = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    video = json.loads(line)
                    videos.append({
                        'id': video.get('id'),
                        'title': video.get('title'),
                        'url': f"https://www.youtube.com/watch?v={video.get('id')}",
                        'duration': video.get('duration'),
                        'upload_date': video.get('upload_date')
                    })
            return videos
        except subprocess.CalledProcessError as e:
            print(f"Error getting channel videos: {e.stderr}")
            return []
    
    def download_subtitles(self, video_url: str, langs: List[str] = None) -> Optional[str]:
        """
        下載影片字幕
        
        Args:
            video_url: 影片 URL
            langs: 字幕語言優先順序
            
        Returns:
            字幕檔案路徑
        """
        if langs is None:
            langs = ["zh-TW", "zh-CN", "zh", "en"]
        
        # 先嘗試手動字幕，再嘗試自動字幕
        for auto in [False, True]:
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-sub" if not auto else "--write-auto-sub",
                "--sub-langs", ",".join(langs),
                "--sub-format", "vtt",
                "--convert-subs", "srt",
                "-o", str(self.output_dir / "%(title)s.%(ext)s"),
                video_url
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                # 查找生成的字幕檔案
                for f in self.output_dir.glob("*.srt"):
                    if f.stat().st_mtime > datetime.now().timestamp() - 60:
                        return str(f)
            except subprocess.CalledProcessError:
                continue
        
        return None
    
    def batch_download_subtitles(self, channel_url: str, max_videos: int = 50) -> List[Dict]:
        """
        批次下載頻道影片字幕
        
        Args:
            channel_url: 頻道 URL
            max_videos: 最大影片數
            
        Returns:
            下載結果列表
        """
        print(f"📺 正在獲取頻道影片列表...")
        videos = self.get_channel_videos(channel_url, max_videos)
        print(f"✅ 找到 {len(videos)} 部影片")
        
        results = []
        for i, video in enumerate(videos, 1):
            print(f"⬇️  [{i}/{len(videos)}] 下載字幕: {video['title'][:50]}...")
            
            subtitle_path = self.download_subtitles(video['url'])
            
            results.append({
                'video': video,
                'subtitle_path': subtitle_path,
                'success': subtitle_path is not None
            })
            
            if subtitle_path:
                print(f"   ✅ 成功: {subtitle_path}")
            else:
                print(f"   ⚠️  未找到字幕，稍後將使用 Whisper")
        
        success_count = sum(1 for r in results if r['success'])
        print(f"\n📊 完成! 成功下載 {success_count}/{len(videos)} 部影片字幕")
        
        return results


def clean_vtt_to_text(vtt_content: str) -> str:
    """
    清理 VTT/SRT 字幕為純文字
    
    Args:
        vtt_content: VTT/SRT 內容
        
    Returns:
        純文字內容
    """
    # 移除 VTT 頭部
    lines = vtt_content.split('\n')
    text_lines = []
    
    for line in lines:
        line = line.strip()
        # 跳過時間軸
        if re.match(r'^\d{2}:\d{2}:\d{2}', line):
            continue
        # 跳過序號
        if re.match(r'^\d+$', line):
            continue
        # 跳過空行和 WEBVTT 標記
        if not line or line.startswith('WEBVTT') or line.startswith('NOTE'):
            continue
        # 移除 HTML 標籤
        line = re.sub(r'<[^>]+>', '', line)
        if line:
            text_lines.append(line)
    
    # 合併重複行
    unique_lines = []
    prev_line = ""
    for line in text_lines:
        if line != prev_line:
            unique_lines.append(line)
            prev_line = line
    
    return '\n'.join(unique_lines)


if __name__ == "__main__":
    # 測試
    scraper = YouTubeScraper()
    
    # 測試頻道
    test_channel = "https://youtube.com/@dankoetalks"
    
    print("🚀 Crawl_R2R YouTube Scraper")
    print("=" * 50)
    
    # 獲取影片列表 (先測試 5 部)
    videos = scraper.get_channel_videos(test_channel, max_videos=5)
    
    for v in videos:
        print(f"📹 {v['title'][:60]}...")
        print(f"   URL: {v['url']}")
        print()
