#!/usr/bin/env python3
"""
Markdown 輸出器 (簡化版)
輸出純 MD 格式，不含 YAML frontmatter
Metadata 和繁簡轉換由 rag_data_washer 處理
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class MarkdownFormatter:
    """Markdown 格式化器 (簡化版)"""
    
    def create_markdown(self,
                        content: str,
                        knowledge: str,
                        video_info: Dict) -> str:
        """
        創建純 Markdown 文件 (可讀格式，無 YAML)
        
        Args:
            content: 原始內容 (逐字稿)
            knowledge: 提取的知識
            video_info: 影片資訊
            
        Returns:
            純 Markdown 內容 (無 YAML frontmatter)
        """
        title = video_info.get('title', '未知標題')
        source = video_info.get('source', '未知來源')
        url = video_info.get('url', '')
        duration = video_info.get('duration', '')
        platform = video_info.get('platform', 'youtube')
        
        # 組合純 Markdown (人類可讀)
        markdown_parts = [
            f"# {title}",
            "",
            f"**來源**: {platform.capitalize()} / {source}  ",
            f"**URL**: {url}  " if url else "",
            f"**時長**: {self._format_duration(duration)}  " if duration else "",
            f"**處理日期**: {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "---",
            "",
            "## 商業知識提取",
            "",
            knowledge if knowledge else "_（無知識提取結果）_",
            "",
            "---",
            "",
            "## 原始逐字稿",
            "",
            content if content else "_（無逐字稿）_",
        ]
        
        # 過濾空行
        return '\n'.join([p for p in markdown_parts if p is not None])
    
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
    print("📝 Crawl_R2R Markdown Formatter (v2)")
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
