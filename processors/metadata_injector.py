#!/usr/bin/env python3
"""
Markdown 輸出器 (統一版)
輸出含 YAML frontmatter 的 MD 格式
包含 source 欄位和統一的元數據結構
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class MarkdownFormatter:
    """Markdown 格式化器 (統一版 - 含 YAML frontmatter)"""
    
    def create_markdown(self,
                        content: str,
                        knowledge: str,
                        video_info: Dict,
                        summary: str = "",
                        keywords: List[str] = None) -> str:
        """
        創建 Markdown 文件 (含統一 YAML frontmatter)
        
        Args:
            content: 原始內容 (逐字稿)
            knowledge: 提取的知識
            video_info: 影片資訊
            summary: AI 摘要
            keywords: 關鍵字列表
            
        Returns:
            Markdown 內容 (含 YAML frontmatter)
        """
        title = video_info.get('title', '未知標題')
        source_name = video_info.get('source', '未知來源')
        url = video_info.get('url', '')
        duration = video_info.get('duration', '')
        platform = video_info.get('platform', 'youtube')
        upload_year = video_info.get('upload_year', None)  # 上傳年份
        guest = video_info.get('guest', None)  # 訪談嘉賓 (新增)
        
        # 決定 source 值
        source_type = self._determine_source_type(platform, video_info)
        
        # 構建 YAML frontmatter
        frontmatter_lines = [
            "---",
            f"title: {title}",
            f"source: {source_type}",
            f"author: {source_name}",  # 主持人/主講者
        ]
        
        # 訪談嘉賓 (若有)
        if guest:
            frontmatter_lines.append(f"guest: {guest}")
        
        if url:
            frontmatter_lines.append(f"url: {url}")
        if duration:
            frontmatter_lines.append(f"duration: \"{self._format_duration(duration)}\"")
        
        # content_year: 上傳年份 (僅年份，無法判斷則省略)
        if upload_year:
            frontmatter_lines.append(f"content_year: {upload_year}")
        
        frontmatter_lines.append(f"processed_at: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}")
        
        # Keywords
        if keywords:
            keywords_str = ", ".join(keywords[:10])
            frontmatter_lines.append(f"keywords: [{keywords_str}]")
        
        # Summary
        if summary:
            # 移除換行符避免 YAML 解析問題
            clean_summary = summary.replace('\n', ' ').replace('"', "'")[:200]
            frontmatter_lines.append(f'summary: "{clean_summary}"')
        
        frontmatter_lines.append("---")
        
        frontmatter = "\n".join(frontmatter_lines)
        
        # 組合 Markdown 內容
        markdown_parts = [
            frontmatter,
            "",
            "## 逐字稿全文",
            "",
            content if content else "_（無逐字稿）_",
            "",
            "---",
            "",
            "## AI 知識提取",
            "",
            knowledge if knowledge else "_（無知識提取結果）_",
        ]
        
        return '\n'.join(markdown_parts)
    
    def _determine_source_type(self, platform: str, video_info: Dict) -> str:
        """決定 source 類型"""
        platform_lower = platform.lower() if platform else ''
        
        if platform_lower in ['youtube', 'yt']:
            return 'youtube'
        elif platform_lower in ['xiaohongshu', 'xhs', 'rednote', '小紅書']:
            return 'xiaohongshu'
        elif platform_lower in ['podcast', 'audio']:
            return 'podcast'
        elif platform_lower in ['ebook', 'pdf', 'book', '電子書']:
            return 'ebook'
        elif platform_lower in ['tutorial', '教程']:
            return 'tutorial'
        elif platform_lower in ['article', 'web', 'blog']:
            return 'article'
        else:
            return platform_lower if platform_lower else 'unknown'
    
    def _format_duration(self, duration) -> str:
        """格式化時長"""
        if not duration:
            return ""
        if isinstance(duration, (int, float)):
            minutes = int(duration) // 60
            seconds = int(duration) % 60
            return f"{minutes}:{seconds:02d}"
        return str(duration)
    
    def generate_safe_filename(self, title: str, max_length: int = 80) -> str:
        """
        生成安全的檔名
        
        Args:
            title: 原始標題
            max_length: 最大長度
            
        Returns:
            安全的檔名 (不含副檔名)
        """
        # 移除特殊字符
        safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
        # 移除連續空白
        safe_title = re.sub(r'\s+', '_', safe_title)
        # 轉換為小寫蛇形命名
        safe_title = safe_title.lower()
        # 限制長度
        if len(safe_title) > max_length:
            safe_title = safe_title[:max_length]
        # 移除尾部下劃線
        safe_title = safe_title.rstrip('_')
        
        return safe_title


# 向後相容別名
MetadataInjector = MarkdownFormatter


if __name__ == "__main__":
    print("📝 MediaMiner Markdown Formatter (v2)")
    print("=" * 50)
    
    formatter = MarkdownFormatter()
    
    # 測試
    md_output = formatter.create_markdown(
        content="大家好，歡迎來到今天的節目。我認為創業最重要的是找到產品市場匹配...",
        knowledge="1. 創業核心：產品市場匹配\n2. 驗證優先於擴張",
        video_info={
            'title': '創業者必看：商業模式設計',
            'source': 'Dan Koe',
            'platform': 'youtube',
            'url': 'https://youtube.com/watch?v=xxx',
            'duration': 930
        }
    )
    
    print("生成的 Markdown:\n")
    print(md_output)
    print("\n" + "=" * 50)
    print(f"檔名範例: {formatter.generate_safe_filename('創業者必看：商業模式設計')}")
