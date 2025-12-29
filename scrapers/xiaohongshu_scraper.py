#!/usr/bin/env python3
"""
小紅書爬蟲
擷取小紅書用戶筆記和影片
"""

import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
import requests
from urllib.parse import urlparse, parse_qs

class XiaohongshuScraper:
    """小紅書爬蟲類"""
    
    def __init__(self, output_dir: str = "~/Documents/MediaMiner_Data/raw"):
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def resolve_short_url(self, short_url: str) -> Optional[str]:
        """
        解析短網址到完整 URL
        
        Args:
            short_url: xhslink.com 短網址
            
        Returns:
            完整的小紅書 URL
        """
        try:
            # 跟隨重定向
            response = requests.head(short_url, allow_redirects=True, timeout=10)
            return response.url
        except Exception as e:
            print(f"⚠️ 無法解析短網址: {e}")
            return None
    
    def extract_note_id(self, url: str) -> Optional[str]:
        """
        從 URL 提取筆記 ID
        
        Args:
            url: 小紅書 URL
            
        Returns:
            筆記 ID
        """
        # 筆記 URL 格式: xiaohongshu.com/explore/xxx 或 discovery/item/xxx
        patterns = [
            r'/explore/([a-zA-Z0-9]+)',
            r'/discovery/item/([a-zA-Z0-9]+)',
            r'/note/([a-zA-Z0-9]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def extract_user_id(self, url: str) -> Optional[str]:
        """
        從 URL 提取用戶 ID
        
        Args:
            url: 小紅書用戶頁面 URL
            
        Returns:
            用戶 ID
        """
        # 用戶頁面格式: xiaohongshu.com/user/profile/xxx
        match = re.search(r'/user/profile/([a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        return None
    
    def download_video_with_ytdlp(self, url: str) -> Dict:
        """
        使用 yt-dlp 下載小紅書影片
        
        Args:
            url: 筆記或影片 URL
            
        Returns:
            下載結果
        """
        try:
            # 嘗試下載影片
            cmd = [
                "yt-dlp",
                "--write-info-json",
                "--write-subs",
                "--sub-langs", "all",
                "-o", str(self.output_dir / "%(title)s.%(ext)s"),
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Download timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_note_content_via_api(self, note_url: str) -> Optional[Dict]:
        """
        嘗試透過 API 獲取筆記內容
        (需要進一步研究小紅書 API)
        
        Args:
            note_url: 筆記 URL
            
        Returns:
            筆記內容
        """
        # 小紅書有反爬機制，可能需要使用 Crawl4AI
        # 或者需要用戶手動授權
        return None
    
    def scrape_with_crawl4ai(self, url: str) -> Optional[str]:
        """
        使用 Crawl4AI 爬取頁面內容
        
        Args:
            url: 頁面 URL
            
        Returns:
            頁面內容 (Markdown)
        """
        try:
            from crawl4ai import AsyncWebCrawler
            import asyncio
            
            async def crawl():
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url=url)
                    return result.markdown
            
            return asyncio.run(crawl())
        except ImportError:
            print("⚠️ Crawl4AI 未安裝")
            return None
        except Exception as e:
            print(f"⚠️ Crawl4AI 錯誤: {e}")
            return None
    
    def process_user_profile(self, profile_url: str, max_notes: int = 10) -> List[Dict]:
        """
        處理用戶個人頁面，提取筆記列表
        
        Args:
            profile_url: 用戶頁面 URL
            max_notes: 最大筆記數
            
        Returns:
            處理結果列表
        """
        print(f"📱 處理小紅書用戶頁面: {profile_url}")
        
        # 嘗試使用 Crawl4AI 獲取頁面
        content = self.scrape_with_crawl4ai(profile_url)
        
        if content:
            # 從內容中提取筆記連結
            note_links = re.findall(r'https?://[^\s]+/explore/[a-zA-Z0-9]+', content)
            note_links = list(set(note_links))[:max_notes]
            
            print(f"   找到 {len(note_links)} 個筆記連結")
            
            results = []
            for link in note_links:
                result = self.download_video_with_ytdlp(link)
                results.append({
                    'url': link,
                    **result
                })
            
            return results
        else:
            print("   ⚠️ 無法獲取用戶頁面內容")
            print("   💡 建議：手動複製筆記連結進行處理")
            return []


def test_xiaohongshu():
    """測試小紅書爬蟲"""
    scraper = XiaohongshuScraper()
    
    print("🔴 小紅書爬蟲測試")
    print("=" * 50)
    
    # 測試短網址解析
    short_url = "https://xhslink.com/m/Arc4LKxLJBG"
    full_url = scraper.resolve_short_url(short_url)
    print(f"短網址: {short_url}")
    print(f"完整URL: {full_url}")
    
    if full_url:
        user_id = scraper.extract_user_id(full_url)
        print(f"用戶ID: {user_id}")
    
    print("\n💡 提示:")
    print("1. 小紅書需要直接的筆記連結 (含 /explore/ 或 /note/)")
    print("2. 建議使用瀏覽器獲取具體筆記 URL")
    print("3. 範例: https://www.xiaohongshu.com/explore/xxx")


if __name__ == "__main__":
    test_xiaohongshu()
