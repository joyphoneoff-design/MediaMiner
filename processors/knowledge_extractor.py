#!/usr/bin/env python3
"""
知識提取器
從逐字稿中提取商業知識
"""

import os
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

# 導入本地模組
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from processors.llm_client import get_llm_client


class KnowledgeExtractor:
    """商業知識提取器"""
    
    def __init__(self, prompts_dir: str = None):
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent.parent / "config" / "prompts"
        self.prompts_dir = Path(prompts_dir)
        self.llm = get_llm_client()
        
        # 載入 Prompts
        self.knowledge_prompt = self._load_prompt("knowledge_extraction.txt")
        self.speaker_prompt = self._load_prompt("speaker_identification.txt")
    
    def _load_prompt(self, filename: str) -> str:
        """載入 Prompt 模板"""
        prompt_file = self.prompts_dir / filename
        if prompt_file.exists():
            return prompt_file.read_text(encoding='utf-8')
        return ""
    
    def identify_speakers(self, transcript: str, video_info: Dict = None) -> str:
        """
        識別講者（使用影片元數據輔助識別）
        
        Args:
            transcript: 原始逐字稿
            video_info: 影片資訊 {'title', 'channel', 'description'}
            
        Returns:
            標記講者後的逐字稿
        """
        # 從影片元數據提取講者資訊
        speaker_hints = ""
        if video_info:
            channel = video_info.get('channel', '')
            title = video_info.get('title', '')
            description = video_info.get('description', '')[:500] if video_info.get('description') else ''
            
            speaker_hints = f"""
## 已知講者資訊（請優先使用）

- **頻道主持人/主講者**: {channel}
- **影片標題**: {title}
- **描述摘要**: {description[:200] if description else '無'}

### 識別規則
1. 若為單人影片（Vlog、教學），主講者為頻道擁有者「{channel}」
2. 若為訪談，主持人通常是頻道擁有者「{channel}」
3. 訪談嘉賓姓名可能出現在標題或描述中
4. **禁止使用虛構或佔位符姓名**（如 Cortex、張三等）
5. 無法識別時用「主講者」或「嘉賓」代替
"""

        prompt = f"""
{self.speaker_prompt}

{speaker_hints}

## 待分析逐字稿

{transcript[:8000]}
"""
        
        result = self.llm.generate(
            prompt=prompt,
            system_prompt=f"你是專業的語音分析師。此影片來自頻道「{video_info.get('channel', '未知')}」，請識別對話中的不同講者。",
            max_tokens=8000,
            temperature=0.3
        )
        
        return result if result else transcript
    
    def extract_knowledge(self, transcript: str, video_info: Dict = None) -> Dict:
        """
        提取商業知識
        
        Args:
            transcript: 逐字稿 (已標記講者)
            video_info: 影片資訊 {'title': ..., 'url': ..., 'duration': ...}
            
        Returns:
            提取的知識 {'summary': ..., 'knowledge': ..., 'metadata': ...}
        """
        # 準備上下文
        context = ""
        if video_info:
            context = f"""
## 影片資訊
- 標題: {video_info.get('title', '未知')}
- 來源: {video_info.get('channel', '未知')}
- 時長: {video_info.get('duration', '未知')}
"""
        
        prompt = f"""
{self.knowledge_prompt}

{context}

## 逐字稿內容

{transcript[:12000]}  # 限制長度
"""
        
        knowledge_text = self.llm.generate(
            prompt=prompt,
            system_prompt="你是商業知識提取專家，請從逐字稿中提取關鍵商業知識。",
            max_tokens=4000,
            temperature=0.5
        )
        
        if not knowledge_text:
            return {"error": "知識提取失敗"}
        
        # 生成摘要
        summary = self._generate_summary(transcript[:4000])
        
        # 提取關鍵字
        keywords = self._extract_keywords(transcript[:4000])
        
        return {
            "knowledge": knowledge_text,
            "summary": summary,
            "keywords": keywords,
            "metadata": {
                "processed_at": datetime.now().isoformat(),
                "llm_provider": self.llm.current_provider,
                "video_info": video_info
            }
        }
    
    def _generate_summary(self, text: str) -> str:
        """生成一句話摘要"""
        prompt = f"""
請用一句話（不超過100字）總結以下內容的核心觀點：

{text}
"""
        result = self.llm.generate(
            prompt=prompt,
            system_prompt="請用繁體中文輸出簡潔的摘要。",
            max_tokens=200,
            temperature=0.3
        )
        return result if result else ""
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取關鍵字"""
        prompt = f"""
請從以下內容中提取 5-10 個關鍵字，以 JSON 數組格式輸出：

{text}

輸出格式: ["關鍵字1", "關鍵字2", ...]
"""
        result = self.llm.generate(
            prompt=prompt,
            system_prompt="請輸出純 JSON 數組，不要其他文字。",
            max_tokens=200,
            temperature=0.3
        )
        
        if result:
            try:
                import json
                # 清理可能的 markdown 代碼塊
                result = result.strip().strip('`').strip()
                if result.startswith('json'):
                    result = result[4:].strip()
                return json.loads(result)
            except:
                pass
        
        return []
    
    def process_transcript(self, transcript: str, video_info: Dict = None) -> Dict:
        """
        完整處理逐字稿
        
        Args:
            transcript: 原始逐字稿
            video_info: 影片資訊
            
        Returns:
            處理結果
        """
        print("🔍 開始處理逐字稿...")
        
        # 1. 識別講者（使用影片元數據輔助）
        print("   👥 識別講者...")
        marked_transcript = self.identify_speakers(transcript, video_info)
        
        # 2. 提取知識
        print("   📚 提取商業知識...")
        result = self.extract_knowledge(marked_transcript, video_info)
        
        # 3. 添加標記後的逐字稿
        result["marked_transcript"] = marked_transcript
        
        print("✅ 處理完成!")
        return result


if __name__ == "__main__":
    print("🧠 MediaMiner Knowledge Extractor")
    print("=" * 50)
    
    extractor = KnowledgeExtractor()
    
    # 測試文本
    test_transcript = """
    主持人：大家好，歡迎來到今天的節目。今天我們邀請到了知名創業者張先生。
    張先生：謝謝邀請。
    主持人：您能跟我們分享一下創業初期最重要的是什麼嗎？
    張先生：我認為最重要的是找到產品市場匹配。很多創業者一開始就想著擴張，
    但其實應該先驗證你的產品是否真正解決了用戶的痛點。
    """
    
    result = extractor.process_transcript(
        test_transcript,
        {"title": "創業訪談", "channel": "測試頻道"}
    )
    
    print("\n📊 結果:")
    print(f"摘要: {result.get('summary', 'N/A')}")
    print(f"關鍵字: {result.get('keywords', [])}")
