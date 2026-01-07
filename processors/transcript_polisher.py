#!/usr/bin/env python3
"""
逐字稿專業梳理器
將自動生成的逐字稿轉換為專業級文本

功能：
1. 清理元數據行 (Kind: captions 等)
2. 合併零散段落為連貫文本
3. 添加適當標點符號
4. 保持原語言不變
5. 中文內容轉繁體+台灣用詞
"""

import re
from typing import Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from processors.llm_client import get_llm_client


class TranscriptPolisher:
    """逐字稿專業梳理器"""
    
    # 需要清理的元數據行模式
    METADATA_PATTERNS = [
        r'^Kind:\s*.+$',
        r'^Language:\s*.+$',
        r'^WEBVTT$',
        r'^NOTE\s*.*$',
        r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->.*$',  # 時間戳
        r'^\d+$',  # 純序號
        r'^<c>.*</c>$',  # VTT 標籤
    ]
    
    # 資深逐字稿處理專家 Prompt
    POLISHER_PROMPT = """你是擁有 20 年經驗的專業逐字稿處理專家。

## 任務
將以下自動生成的逐字稿梳理為專業級文本。

## 嚴格規則
1. **保持原語言**：英文內容保持英文，中文內容保持中文，絕不翻譯
2. **合併段落**：將零散的句子片段合併為完整、連貫的句子
3. **添加標點**：為文本添加適當的標點符號（句號、逗號、問號、驚嘆號等）
4. **移除填充詞**：刪除 "um", "uh", "like", "you know", "嗯", "那個", "就是說" 等口語填充詞
5. **保留說話者標記**：若原文有說話者標記（如「主講者:」），保留並統一格式
6. **不得改寫**：不要改寫內容、不要添加內容、不要總結
7. **自然分段**：根據話題轉換或邏輯分段，每段 3-5 句為宜

## 輸出格式
直接輸出梳理後的純文本逐字稿，不加任何標題或說明。

## 待處理逐字稿
"""

    def __init__(self):
        self.llm = get_llm_client()
    
    def clean_metadata(self, text: str) -> str:
        """清理元數據行"""
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # 跳過空行連續超過 2 行
            if not stripped:
                if cleaned_lines and cleaned_lines[-1] == '':
                    continue
                cleaned_lines.append('')
                continue
            
            # 檢查是否匹配元數據模式
            is_metadata = False
            for pattern in self.METADATA_PATTERNS:
                if re.match(pattern, stripped, re.IGNORECASE):
                    is_metadata = True
                    break
            
            if not is_metadata:
                cleaned_lines.append(stripped)
        
        return '\n'.join(cleaned_lines).strip()
    
    def detect_language(self, text: str) -> str:
        """偵測文本主要語言"""
        # 計算中文字符比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(re.findall(r'\w', text)) + chinese_chars
        
        if total_chars == 0:
            return 'unknown'
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:
            return 'zh'
        else:
            return 'en'
    
    def convert_to_traditional_tw(self, text: str) -> str:
        """
        簡體中文 → 繁體中文 (台灣用詞)
        
        使用 OpenCC 進行轉換 (若已安裝)
        否則使用基本詞彙替換表
        """
        try:
            import opencc
            converter = opencc.OpenCC('s2twp')  # 簡體到繁體（台灣用詞）
            return converter.convert(text)
        except ImportError:
            # 基本詞彙替換表（部分常見用詞）
            replacements = {
                '视频': '影片',
                '软件': '軟體',
                '硬件': '硬體',
                '内存': '記憶體',
                '程序': '程式',
                '信息': '資訊',
                '数据': '資料',
                '网络': '網路',
                '云端': '雲端',
                '用户': '使用者',
                '服务器': '伺服器',
                '文件': '檔案',
                '字节': '位元組',
                '界面': '介面',
                '系统': '系統',
                '质量': '品質',
                '优化': '最佳化',
                '方案': '方案',  # 保持
                '项目': '專案',
                '团队': '團隊',
                '创业': '創業',
                '商业': '商業',
                '营销': '行銷',
                '品牌': '品牌',  # 保持
                '客户': '客戶',
                '产品': '產品',
                '服务': '服務',
                '管理': '管理',  # 保持
                '技术': '技術',
                '发展': '發展',
            }
            
            result = text
            for simp, trad in replacements.items():
                result = result.replace(simp, trad)
            
            return result
    
    def polish(self, transcript: str, use_llm: bool = True) -> str:
        """
        完整的逐字稿梳理流程
        
        Args:
            transcript: 原始逐字稿
            use_llm: 是否使用 LLM 進行深度梳理
            
        Returns:
            梳理後的逐字稿
        """
        if not transcript:
            return transcript
        
        # Step 1: 清理元數據
        cleaned = self.clean_metadata(transcript)
        
        if not cleaned:
            return transcript
        
        # Step 2: 偵測語言
        lang = self.detect_language(cleaned)
        
        # Step 3: LLM 深度梳理 (可選)
        if use_llm and len(cleaned) > 100:
            try:
                polished = self.llm.generate(
                    prompt=f"{self.POLISHER_PROMPT}\n\n{cleaned[:12000]}",
                    system_prompt="你是專業逐字稿處理專家。嚴格遵守規則，特別是保持原語言。",
                    max_tokens=8000,
                    temperature=0.2
                )
                if polished and len(polished) > len(cleaned) * 0.5:  # 確保輸出合理
                    cleaned = polished
            except Exception as e:
                print(f"⚠️ LLM 梳理失敗，使用原始清理版本: {e}")
        
        # Step 4: 中文內容轉繁體+台灣用詞
        if lang == 'zh':
            cleaned = self.convert_to_traditional_tw(cleaned)
        
        return cleaned


# 便捷函數
def polish_transcript(transcript: str, use_llm: bool = True) -> str:
    """便捷函數：梳理逐字稿"""
    polisher = TranscriptPolisher()
    return polisher.polish(transcript, use_llm=use_llm)


if __name__ == "__main__":
    print("📝 TranscriptPolisher 測試")
    print("=" * 50)
    
    # 測試文本
    test_transcript = """Kind: captions
Language: zh-Hans

我开始思考的一件事是
Cortex 有什么问题
我们好像完全无法前进
只是原地踏步
评论不断涌入
其他事情也接踵而来
我们到底在做什么"""
    
    polisher = TranscriptPolisher()
    
    # 測試清理
    cleaned = polisher.clean_metadata(test_transcript)
    print("清理後:")
    print(cleaned)
    print()
    
    # 測試語言偵測
    lang = polisher.detect_language(cleaned)
    print(f"偵測語言: {lang}")
    print()
    
    # 測試繁體轉換
    trad = polisher.convert_to_traditional_tw(cleaned)
    print("繁體轉換:")
    print(trad)
