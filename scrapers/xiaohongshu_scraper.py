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
    
    def get_user_notes(self, url: str, max_notes: int = 0) -> List[Dict]:
        """
        獲取用戶所有筆記列表 (類似 YouTube get_channel_videos)
        
        Args:
            url: 小紅書 URL (支持短網址 xhslink.com)
            max_notes: 最大筆記數 (0 = 全部)
            
        Returns:
            [{'title': ..., 'url': ..., 'note_id': ..., 'type': 'video'|'image', ...}]
        """
        print(f"📱 獲取小紅書用戶筆記列表...")
        
        # Step 1: 解析 URL 獲取用戶 ID
        full_url = self._resolve_to_profile_url(url)
        if not full_url:
            print("❌ 無法解析 URL")
            return []
        
        user_id = self.extract_user_id(full_url)
        if not user_id:
            print(f"❌ 無法從 URL 提取用戶 ID: {full_url}")
            return []
        
        print(f"   用戶 ID: {user_id}")
        
        # Step 2: 優先使用 CDP (需要 Chrome Debug 模式)
        notes = self._fetch_notes_via_cdp(full_url, max_notes)
        
        if not notes:
            # 備用方案 1: 使用 API
            print("   嘗試備用方案: API...")
            notes = self._fetch_notes_via_api(user_id, max_notes)
        
        if not notes:
            # 備用方案 2: 使用網頁爬取
            print("   嘗試備用方案 2: 網頁爬取...")
            notes = self._fetch_notes_via_web(full_url, max_notes)
        
        if not notes:
            # 備用方案 3: 使用 Playwright 瀏覽器自動化
            print("   嘗試備用方案 3: Playwright 瀏覽器...")
            notes = self._fetch_notes_via_playwright(full_url, max_notes)
        
        print(f"   ✅ 找到 {len(notes)} 個筆記")
        return notes
    
    def _resolve_to_profile_url(self, url: str) -> Optional[str]:
        """解析短網址到完整用戶頁面 URL"""
        # 如果已經是完整 URL
        if 'xiaohongshu.com/user/profile' in url:
            return url
        
        # 使用 yt-dlp 解析短網址 (它會跟隨重定向)
        try:
            import subprocess
            result = subprocess.run(
                ['yt-dlp', '--dump-json', url],
                capture_output=True, text=True, timeout=30
            )
            # yt-dlp 會輸出錯誤信息中包含完整 URL
            if 'xiaohongshu.com/user/profile' in result.stderr:
                import re
                match = re.search(r'(https://www\.xiaohongshu\.com/user/profile/[^\s\?]+)', result.stderr)
                if match:
                    return match.group(1)
        except Exception as e:
            print(f"   ⚠️ yt-dlp 解析失敗: {e}")
        
        # 備用: 直接 HEAD 請求
        try:
            response = requests.head(url, allow_redirects=True, timeout=10)
            if 'xiaohongshu.com' in response.url:
                return response.url
        except:
            pass
        
        return None
    
    def _fetch_notes_via_api(self, user_id: str, max_notes: int = 0) -> List[Dict]:
        """使用小紅書 API 獲取筆記列表"""
        notes = []
        cursor = ""
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Origin': 'https://www.xiaohongshu.com',
            'Referer': f'https://www.xiaohongshu.com/user/profile/{user_id}',
        }
        
        # 小紅書 web API endpoint
        api_url = f"https://edith.xiaohongshu.com/api/sns/web/v1/user_posted"
        
        try:
            for page in range(20):  # 最多 20 頁
                params = {
                    'num': 30,
                    'cursor': cursor,
                    'user_id': user_id,
                    'image_formats': 'jpg,webp,avif'
                }
                
                response = requests.get(api_url, headers=headers, params=params, timeout=15)
                
                if response.status_code != 200:
                    print(f"   ⚠️ API 返回 {response.status_code}")
                    break
                
                data = response.json()
                
                if not data.get('success'):
                    break
                
                items = data.get('data', {}).get('notes', [])
                if not items:
                    break
                
                for item in items:
                    note = {
                        'title': item.get('display_title', '無標題'),
                        'note_id': item.get('note_id'),
                        'url': f"https://www.xiaohongshu.com/explore/{item.get('note_id')}",
                        'type': item.get('type', 'normal'),  # normal=圖片, video=影片
                        'cover': item.get('cover', {}).get('url', ''),
                        'likes': item.get('liked_count', 0),
                        'user': item.get('user', {}).get('nickname', ''),
                    }
                    notes.append(note)
                    
                    if max_notes > 0 and len(notes) >= max_notes:
                        return notes
                
                cursor = data.get('data', {}).get('cursor', '')
                if not cursor or not data.get('data', {}).get('has_more'):
                    break
                    
        except Exception as e:
            print(f"   ⚠️ API 請求失敗: {e}")
        
        return notes
    
    def _fetch_notes_via_web(self, profile_url: str, max_notes: int = 0) -> List[Dict]:
        """備用: 使用網頁爬取獲取筆記列表"""
        notes = []
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        try:
            response = requests.get(profile_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                # 從 HTML 中提取筆記資訊
                import re
                
                # 查找筆記連結
                note_pattern = r'/explore/([a-zA-Z0-9]+)'
                note_ids = list(set(re.findall(note_pattern, response.text)))
                
                for note_id in note_ids[:max_notes if max_notes > 0 else len(note_ids)]:
                    notes.append({
                        'title': f'筆記 {note_id[:8]}...',
                        'note_id': note_id,
                        'url': f'https://www.xiaohongshu.com/explore/{note_id}',
                        'type': 'unknown',
                        'cover': '',
                        'likes': 0,
                        'user': '',
                    })
                    
        except Exception as e:
            print(f"   ⚠️ 網頁爬取失敗: {e}")
        
        return notes
    
    def _fetch_notes_via_playwright(self, profile_url: str, max_notes: int = 0) -> List[Dict]:
        """使用 Playwright 瀏覽器自動化獲取筆記列表"""
        notes = []
        
        try:
            from playwright.sync_api import sync_playwright
            import time
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                    viewport={'width': 390, 'height': 844}
                )
                page = context.new_page()
                
                # 訪問用戶頁面
                page.goto(profile_url, wait_until='networkidle', timeout=30000)
                time.sleep(2)  # 等待動態內容載入
                
                # 滾動載入更多筆記
                for _ in range(3):
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    time.sleep(1)
                
                # 提取筆記資訊
                content = page.content()
                
                # 從 HTML 中提取筆記連結和標題
                import re
                
                # 查找筆記連結
                note_pattern = r'/explore/([a-zA-Z0-9]+)'
                note_ids = list(set(re.findall(note_pattern, content)))
                
                # 嘗試提取標題
                title_pattern = r'<span[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</span>'
                titles = re.findall(title_pattern, content)
                
                for i, note_id in enumerate(note_ids[:max_notes if max_notes > 0 else len(note_ids)]):
                    title = titles[i] if i < len(titles) else f'筆記 {note_id[:8]}...'
                    notes.append({
                        'title': title,
                        'note_id': note_id,
                        'url': f'https://www.xiaohongshu.com/explore/{note_id}',
                        'type': 'unknown',
                        'cover': '',
                        'likes': 0,
                        'user': '',
                    })
                
                browser.close()
                
        except ImportError:
            print("   ⚠️ Playwright 未安裝，請執行: pip install playwright && playwright install chromium")
        except Exception as e:
            print(f"   ⚠️ Playwright 爬取失敗: {e}")
        
        return notes
    
    def _fetch_notes_via_cdp(self, profile_url: str, max_notes: int = 0) -> List[Dict]:
        """使用 Chrome Debug Protocol 連接已登入的瀏覽器獲取筆記列表"""
        notes = []
        
        try:
            import socket
            # 檢查 Chrome Debug 端口是否可用
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 9222))
            sock.close()
            
            if result != 0:
                print("   ⚠️ Chrome 未在 Debug 模式運行 (端口 9222)")
                return notes
            
            from playwright.sync_api import sync_playwright
            import time
            
            print("   🔗 連接到 Chrome Debug Protocol...")
            
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp('http://localhost:9222')
                context = browser.contexts[0] if browser.contexts else None
                
                if not context:
                    print("   ⚠️ 無法獲取瀏覽器上下文")
                    return notes
                
                page = context.new_page()
                
                print(f"   📱 訪問用戶頁面...")
                page.goto(profile_url, wait_until='load', timeout=30000)
                time.sleep(3)
                
                # 滾動載入更多內容
                scroll_count = 10 if max_notes == 0 else max(3, max_notes // 10)
                for i in range(scroll_count):
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    time.sleep(1.5)
                    print(f"   📜 滾動 {i+1}/{scroll_count}...")
                
                content = page.content()
                page.close()
                
                # 提取筆記連結
                note_pattern = r'/explore/([a-zA-Z0-9]+)'
                note_ids = list(dict.fromkeys(re.findall(note_pattern, content)))  # 保持順序去重
                
                # 嘗試提取標題 (從 DOM 中)
                title_pattern = r'class="[^"]*title[^"]*"[^>]*>([^<]+)<'
                titles = re.findall(title_pattern, content)
                
                for i, note_id in enumerate(note_ids):
                    if max_notes > 0 and len(notes) >= max_notes:
                        break
                    
                    title = titles[i] if i < len(titles) else f'筆記 {note_id[:8]}...'
                    notes.append({
                        'title': title,
                        'note_id': note_id,
                        'url': f'https://www.xiaohongshu.com/explore/{note_id}',
                        'type': 'video',
                        'cover': '',
                        'likes': 0,
                        'user': '',
                    })
                
                print(f"   ✅ 通過 CDP 找到 {len(notes)} 個筆記")
                
        except ImportError:
            print("   ⚠️ Playwright 未安裝")
        except Exception as e:
            print(f"   ⚠️ CDP 連接失敗: {e}")
        
        return notes
    
    def process_user_profile(self, profile_url: str, max_notes: int = 10) -> List[Dict]:
        """處理用戶個人頁面 (保留向後兼容)"""
        return self.get_user_notes(profile_url, max_notes)


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
