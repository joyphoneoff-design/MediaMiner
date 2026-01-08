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
    
    def _smart_sample(self, content: str, target_length: int = 10000) -> str:
        """
        智慧採樣：開頭 + 中間 + 結尾
        
        80/20 優化：以最小成本（不增加 token）獲得最大覆蓋率提升
        
        Args:
            content: 完整內容
            target_length: 目標採樣長度（默認 10000）
        
        Returns:
            採樣後的內容
        """
        total_len = len(content)
        
        # 內容不長，直接返回
        if total_len <= target_length:
            return content
        
        # 計算各部分長度（開頭50% + 中間30% + 結尾20%）
        head_len = int(target_length * 0.5)
        middle_len = int(target_length * 0.3)
        tail_len = int(target_length * 0.2)
        
        # 提取開頭
        head = content[:head_len]
        
        # 提取中間（從 40% 位置開始）
        middle_start = int(total_len * 0.4)
        middle = content[middle_start:middle_start + middle_len]
        
        # 提取結尾
        tail = content[-tail_len:]
        
        # 組合（添加分隔符）
        sampled = f"{head}\n\n[...中間內容省略...]\n\n{middle}\n\n[...後續內容省略...]\n\n{tail}"
        
        print(f"   📊 智慧採樣: {total_len} → {len(sampled)} 字 (開頭+中段+結尾)")
        
        return sampled
    
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
    
    def _load_ontology_entities(self) -> List[str]:
        """載入本體論實體清單 (80/20 優化)"""
        ontology_path = Path.home() / "R2R/config/ontology/solo_entrepreneur_synonyms.json"
        try:
            if ontology_path.exists():
                import json
                with open(ontology_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 提取所有 entity 的 key (主實體名稱)
                return list(data.keys())
        except Exception:
            pass
        return []
    
    def _load_ontology_tags(self) -> List[str]:
        """載入預設標籤清單 (80/20 優化 - 嚴格限制)"""
        tags_path = Path.home() / "R2R/config/ontology/solo_entrepreneur_tags.yaml"
        try:
            if tags_path.exists():
                import yaml
                with open(tags_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                # 提取所有 dimensions 下的 tags
                all_tags = []
                for dim_key, dim_val in data.get('dimensions', {}).items():
                    for cat_key, cat_val in dim_val.get('categories', {}).items():
                        all_tags.extend(cat_val.get('tags', []))
                return all_tags
        except Exception:
            pass
        return []
    
    def _fuzzy_match(self, text: str, candidates: List[str], threshold: float = 0.3) -> Optional[str]:
        """
        模糊匹配：找到最接近的候選項
        使用簡單的字符重疊算法（無需額外依賴）
        """
        if not text or not candidates:
            return None
        
        text_lower = text.lower().replace(' ', '')
        best_match = None
        best_score = threshold
        
        for candidate in candidates:
            candidate_lower = candidate.lower().replace(' ', '')
            
            # 完全匹配
            if text_lower == candidate_lower:
                return candidate
            
            # 包含匹配（優先）
            if text_lower in candidate_lower or candidate_lower in text_lower:
                score = min(len(text_lower), len(candidate_lower)) / max(len(text_lower), len(candidate_lower))
                if score > best_score:
                    best_score = score
                    best_match = candidate
                continue
            
            # 字符重疊分數
            common = set(text_lower) & set(candidate_lower)
            score = len(common) / max(len(set(text_lower)), len(set(candidate_lower)))
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        return best_match
    
    def _validate_entities(self, entities: List[str]) -> List[str]:
        """
        後處理驗證：確保 entities 100% 符合預設本體論
        不符合的項目會映射到最接近的預設實體
        """
        ontology_entities = self._load_ontology_entities()
        if not ontology_entities:
            return entities[:8]  # 無 ontology 則直接返回
        
        validated = []
        ontology_set = set(ontology_entities)
        
        for entity in entities:
            # 完全匹配
            if entity in ontology_set:
                if entity not in validated:
                    validated.append(entity)
            else:
                # 模糊匹配
                match = self._fuzzy_match(entity, ontology_entities)
                if match and match not in validated:
                    validated.append(match)
                    print(f"   📎 Entity 映射: {entity} → {match}")
        
        return validated[:8]  # 最多 8 個
    
    def _validate_tags(self, tags: List[str]) -> List[str]:
        """
        後處理驗證：確保 tags 100% 符合預設標籤集
        不符合的項目會映射到最接近的預設標籤
        """
        ontology_tags = self._load_ontology_tags()
        if not ontology_tags:
            return tags[:5]  # 無預設則直接返回
        
        validated = []
        tags_set = set(ontology_tags)
        
        for tag in tags:
            # 完全匹配
            if tag in tags_set:
                if tag not in validated:
                    validated.append(tag)
            else:
                # 模糊匹配
                match = self._fuzzy_match(tag, ontology_tags)
                if match and match not in validated:
                    validated.append(match)
                    print(f"   🏷️ Tag 映射: {tag} → {match}")
        
        return validated[:5]  # 最多 5 個
    
    def _is_interview_content(self, transcript: str, video_info: Dict = None) -> bool:
        """
        預檢：判斷是否為訪談內容 (不調用 LLM，節約 API)
        
        檢驗機制：
        1. 標題關鍵字檢查
        2. 逐字稿內容關鍵字檢查
        
        Returns:
            True = 可能是訪談，需要識別 guest
            False = 非訪談，跳過 guest 識別
        """
        # 訪談相關關鍵字
        interview_keywords = [
            '訪談', '專訪', '對談', '對話', '訪問', '請到', '邀請',
            '嘉賓', '老師', '來賓', '特別嘉賓',
            'interview', 'podcast', 'guest', 'feat', 'ft.', 'with',
            'q&a', 'qa', '問答', '連線'
        ]
        
        # 1. 檢查標題
        title = ""
        if video_info:
            title = video_info.get('title', '').lower()
        
        for keyword in interview_keywords:
            if keyword.lower() in title:
                return True
        
        # 2. 檢查逐字稿前 500 字
        transcript_head = transcript[:500].lower() if transcript else ""
        
        # 訪談開場特徵
        interview_patterns = [
            '今天我們請到', '今天的嘉賓', '今天邀請', '歡迎來到',
            '請問', '可以介紹一下', '先做個自我介紹',
            '謝謝邀請', '很高興來到', '感謝主持人',
            "today's guest", "welcome to the show", "thanks for having me"
        ]
        
        for pattern in interview_patterns:
            if pattern.lower() in transcript_head:
                return True
        
        return False
    
    def extract_knowledge(self, transcript: str, video_info: Dict = None) -> Dict:
        """
        提取商業知識（合併調用：知識 + 摘要 + 關鍵字 + 實體 + 標籤 + 嘉賓 + 逐字稿格式化）
        
        80/20 優化：在源頭一次完成所有提取，避免 R2R Phase1 重複 API 調用
        新增：逐字稿標點符號與斷句修復（同一調用中完成）
        
        Args:
            transcript: 逐字稿 (已標記講者)
            video_info: 影片資訊 {'title': ..., 'url': ..., 'duration': ...}
            
        Returns:
            提取的知識 {'summary': ..., 'knowledge': ..., 'keywords': ..., 'entities': ..., 'tags': ..., 'guest': ..., 'formatted_transcript': ...}
        """
        # 智慧採樣優化：移除重複行後使用智慧採樣
        lines = transcript.split('\n')
        unique_lines = list(dict.fromkeys(lines))
        full_transcript = '\n'.join([l for l in unique_lines if len(l.strip()) > 5])
        clean_transcript = self._smart_sample(full_transcript, 10000)
        
        # 載入本體論實體 (80/20 優化)
        ontology_entities = self._load_ontology_entities()
        ontology_tags = self._load_ontology_tags()
        
        ontology_hint = ""
        if ontology_entities:
            ontology_hint = f"""
### 實體 (Entities) [必填 - 嚴格限制]
**請「只能」從以下預定義實體中選擇 3-8 個最匹配的，禁止自行創造新實體：**
{', '.join(ontology_entities[:100])}

⚠️ 注意：只能選擇上述實體，不得創造任何新項目！

**必須**在文末添加：
`<!-- ENTITIES: ["實體1", "實體2", ...] -->`

### 標籤 (Tags) [必填 - 嚴格限制]
**請「只能」從以下預定義標籤中選擇 3-5 個最匹配的，禁止自行創造新標籤：**
{', '.join(ontology_tags[:60])}

⚠️ 注意：只能選擇上述標籤，不得創造任何新項目！

**必須**在文末添加：
`<!-- TAGS: ["標籤1", "標籤2", ...] -->`
"""
        else:
            # 無 ontology 時的備用（但仍提供常見選項）
            ontology_hint = """
### 實體 (Entities) [必填]
請從以下常見商業概念中選擇 3-8 個：
商業模式, 創業, 產品市場匹配, 定位策略, 訂閱制, 內容行銷, 個人品牌, 精實創業, MVP, 獲利模式

**必須**在文末添加：
`<!-- ENTITIES: ["實體1", "實體2", ...] -->`

### 標籤 (Tags) [必填]
請從以下常見標籤中選擇 3-5 個：
市場定位, 價值主張, 訂閱制, 內容行銷, 從零開始, 規模化, 自動化, 被動收入, AI工具

**必須**在文末添加：
`<!-- TAGS: ["標籤1", "標籤2", ...] -->`
"""
        
        # 訪談嘉賓識別 (預檢機制節約 API)
        is_interview = self._is_interview_content(clean_transcript, video_info)
        guest_hint = ""
        if is_interview:
            guest_hint = """
### 訪談嘉賓 (Guest)
如果這是訪談/對談內容，請識別受訪者/嘉賓姓名。
注意：主持人/頻道主不算嘉賓，只識別被邀請的來賓。
如無嘉賓或無法識別，請輸出空字串。
請在文末添加：
`<!-- GUEST: "嘉賓姓名" -->`
"""
        
        # 準備上下文
        context = ""
        channel = video_info.get('channel', '未知') if video_info else '未知'
        if video_info:
            context = f"""
## 影片資訊
- 標題: {video_info.get('title', '未知')}
- 來源: {channel}
- 時長: {video_info.get('duration', '未知')}
"""
        
        # 合併 Prompt：知識提取 + 摘要 + 關鍵字 + 實體 + 標籤 + 嘉賓 + 逐字稿格式化
        prompt = f"""
{self.knowledge_prompt}

{context}

## 逐字稿內容

{clean_transcript}

---

## 額外輸出（請在知識提取後添加，所有標記都是必填）

### 逐字稿格式化與翻譯 [必填]
請將逐字稿翻譯為**繁體中文（台灣用語）**，並依以下規則整理格式：

**翻譯原則：**
- 忠實傳達原意，不增刪內容，不過度詮釋
- 所有語言（英文、簡體中文、日文等）一律翻譯為繁體中文
- 使用台灣慣用詞彙（video→影片、information→資訊、software→軟體、network→網路、user→使用者）
- 保留專有名詞原文（人名、公司名可附英文，如：伊隆·馬斯克 Elon Musk）

**格式規則：**
- 添加適當標點符號：句號、逗號、問號、驚嘆號
- 每 2-4 句話為一段落，主題轉換時換行
- 保留口語特色（如「嗯」「對」「就是說」等語氣詞）
- 長句適當拆分，確保閱讀流暢

**必須**在文末添加（翻譯並整理後的逐字稿）：
`<!-- FORMATTED_TRANSCRIPT_START -->`
[翻譯並整理後的繁體中文逐字稿全文]
`<!-- FORMATTED_TRANSCRIPT_END -->`

### 一句話摘要 [必填]
**必須**在文末添加：
`<!-- SUMMARY: [不超過100字的核心觀點摘要] -->`

### 關鍵字 [必填]
**必須**在文末添加：
`<!-- KEYWORDS: ["關鍵字1", "關鍵字2", ...] -->`

### 講者標記 [必填]
在格式化逐字稿中，請標記講者身份：
- 若為單人影片，使用「**主講者 [{channel}]:**」
- 若為訪談，主持人標記為「**主持人:**」，嘉賓標記為「**受訪者 [姓名]:**」
- 無法識別講者時使用「**主講者:**」

{ontology_hint}
{guest_hint}
"""
        # 動態調整 max_tokens：長逐字稿需要更多輸出空間
        transcript_length = len(clean_transcript)
        if transcript_length > 20000:  # 超過 2 萬字元 (約 60 分鐘影片)
            max_tokens = 15000
        elif transcript_length > 10000:  # 超過 1 萬字元 (約 30 分鐘影片)
            max_tokens = 12000
        else:
            max_tokens = 8000
        
        result_text = self.llm.generate(
            prompt=prompt,
            system_prompt="""你是資深逐字稿處理專家及翻譯大師，同時也是商業知識提取專家。

【逐字稿處理原則】
1. 忠實原意：翻譯時必須保留講者原意，不增刪、不改寫、不過度詮釋
2. 適當斷句：依語意自然停頓處加入標點符號（句號、逗號、問號、驚嘆號）
3. 段落分明：每 2-4 句話為一段，主題轉換時換行分段
4. 口語保留：保留講者的口語特色和語氣詞（如「嗯」「對」「就是說」等）
5. 專有名詞：人名、公司名、產品名保留原文或附註英文
6. 台灣用語：使用繁體中文及台灣慣用詞（影片、資訊、軟體、網路、使用者）

【輸出要求】
請在文末按指定格式添加所有必填標記（摘要、關鍵字、實體、標籤、格式化逐字稿）。每個標記都必須輸出。""",
            max_tokens=max_tokens,
            temperature=0.3  # 降低溫度以提高翻譯穩定性
        )
        
        if not result_text:
            return {"error": "知識提取失敗"}
        
        # 解析合併結果
        summary = ""
        keywords = []
        entities = []
        tags = []
        knowledge = result_text
        
        # 提取摘要
        import re
        import json
        
        summary_match = re.search(r'<!-- SUMMARY: (.+?) -->', result_text)
        if summary_match:
            summary = summary_match.group(1).strip()
            knowledge = knowledge.replace(summary_match.group(0), '')
        
        # 提取關鍵字
        keywords_match = re.search(r'<!-- KEYWORDS: (\[.+?\]) -->', result_text)
        if keywords_match:
            try:
                keywords = json.loads(keywords_match.group(1))
                knowledge = knowledge.replace(keywords_match.group(0), '')
            except:
                pass
        
        # 提取實體 (80/20 優化)
        entities_match = re.search(r'<!-- ENTITIES: (\[.+?\]) -->', result_text)
        if entities_match:
            try:
                entities = json.loads(entities_match.group(1))
                knowledge = knowledge.replace(entities_match.group(0), '')
            except:
                pass
        
        # 提取標籤 (80/20 優化)
        tags_match = re.search(r'<!-- TAGS: (\[.+?\]) -->', result_text)
        if tags_match:
            try:
                tags = json.loads(tags_match.group(1))
                knowledge = knowledge.replace(tags_match.group(0), '')
            except:
                pass
        
        # 提取訪談嘉賓 (條件式：只在訪談內容時提取)
        guest = None
        guest_match = re.search(r'<!-- GUEST: "(.+?)" -->', result_text)
        if guest_match:
            guest = guest_match.group(1).strip()
            if guest and guest not in ['', '無', 'None', 'null', '無法識別']:
                knowledge = knowledge.replace(guest_match.group(0), '')
            else:
                guest = None
        
        # 提取格式化逐字稿 (80/20 優化：單次 API 完成標點符號修復)
        formatted_transcript = None
        transcript_match = re.search(
            r'<!-- FORMATTED_TRANSCRIPT_START -->\s*(.*?)\s*<!-- FORMATTED_TRANSCRIPT_END -->', 
            result_text, 
            re.DOTALL
        )
        if transcript_match:
            formatted_transcript = transcript_match.group(1).strip()
            knowledge = knowledge.replace(transcript_match.group(0), '')
        
        # 後處理驗證：確保 entities 和 tags 100% 符合預設本體論
        validated_entities = self._validate_entities(entities) if entities else []
        validated_tags = self._validate_tags(tags) if tags else []
        
        return {
            "knowledge": knowledge.strip(),
            "summary": summary,
            "keywords": keywords,
            "entities": validated_entities,  # 驗證後的 entities
            "tags": validated_tags,  # 驗證後的 tags
            "guest": guest,
            "formatted_transcript": formatted_transcript,
            "metadata": {
                "processed_at": datetime.now().isoformat(),
                "llm_provider": self.llm.current_provider,
                "video_info": video_info,
                "optimized": True,
                "ontology_used": len(ontology_entities) > 0,
                "is_interview": is_interview,
                "entities_validated": len(validated_entities) > 0,
                "tags_validated": len(validated_tags) > 0
            }
        }
    def _should_skip_speaker_id(self, video_info: Dict) -> bool:
        """
        判斷是否跳過講者識別（優化 API 調用）
        
        跳過條件：
        - 標題不包含訪談相關詞彙
        - 非明顯多人對話內容
        """
        if not video_info:
            return False
        
        title = video_info.get('title', '').lower()
        
        # 訪談相關關鍵字（需要講者識別）
        interview_keywords = [
            '訪談', '專訪', '對談', '對話', 'interview', 'podcast', 
            '嘉賓', 'guest', 'feat', 'ft.', 'ft', 'with', '與', '和',
            'q&a', 'qa', '問答'
        ]
        
        # 如果標題包含訪談關鍵字，不跳過
        for keyword in interview_keywords:
            if keyword in title:
                return False
        
        # 單人內容關鍵字（可跳過講者識別）
        solo_keywords = [
            'vlog', '教學', 'tutorial', 'guide', '分享', '心得',
            'review', '評測', '開箱', 'unbox', '日常', 'routine'
        ]
        
        for keyword in solo_keywords:
            if keyword in title:
                return True
        
        # 預設：不跳過（保守策略）
        return False
    
    def process_transcript(self, transcript: str, video_info: Dict = None) -> Dict:
        """
        完整處理逐字稿（優化版 - 單次 LLM 調用）
        
        80/20 優化：合併所有處理為單次 API 調用
        - 講者識別（整合到 prompt）
        - 知識提取
        - 摘要/關鍵字/實體/標籤
        - 逐字稿格式化
        
        Args:
            transcript: 原始逐字稿
            video_info: 影片資訊
            
        Returns:
            處理結果
        """
        print("🔍 開始處理逐字稿...")
        print("   📚 單次 API 調用中（講者+知識+格式化）...")
        
        # 直接調用 extract_knowledge（已包含講者識別指令）
        result = self.extract_knowledge(transcript, video_info)
        
        # 使用格式化後的逐字稿作為標記版本
        result["marked_transcript"] = result.get('formatted_transcript') or transcript
        
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
