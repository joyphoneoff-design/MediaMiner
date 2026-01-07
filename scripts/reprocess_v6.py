#!/usr/bin/env python3
"""
MediaMiner MD 重新處理腳本 v6 - 預掃描去重版
核心改進：
1. 預掃描所有檔案，建立 hash → 第一個檔案 的映射
2. 只把唯一的檔案送入處理佇列（從源頭杜絕重複）
3. 多線程處理 API 調用（無競態條件風險）
"""

import os
import re
import json
import yaml
import sys
import time
import threading
import random
import hashlib
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

print("=" * 70, flush=True)
print("MediaMiner 重新處理腳本 v6 - 預掃描去重版", flush=True)
print("=" * 70, flush=True)

# 添加 MediaMiner 路徑
sys.path.insert(0, str(Path.home() / "MediaMiner"))

# 配置
INPUT_DIR = Path.home() / "Documents/MediaMiner_Data/processed"
OUTPUT_DIR = Path.home() / "Documents/MediaMiner_Data/reprocessed"
PROGRESS_FILE = OUTPUT_DIR / ".progress.json"
MAX_THREADS = 10
MIN_THREADS = 1

# 自適應控制參數
INITIAL_DELAY = 1.0
MAX_DELAY = 60.0
BACKOFF_FACTOR = 1.5
ERROR_THRESHOLD = 3
SUCCESS_THRESHOLD = 10

# API 密鑰載入
def load_cerebras_keys():
    keys = []
    config_file = Path.home() / "MediaMiner/config/api_keys.env"
    if config_file.exists():
        with open(config_file, 'r') as f:
            for line in f:
                if line.startswith('CEREBRAS_API_KEY'):
                    parts = line.strip().split('=')
                    if len(parts) == 2 and parts[1]:
                        keys.append(parts[1])
    print(f"DEBUG: Loaded {len(keys)} API keys", flush=True)
    return keys

CEREBRAS_KEYS = load_cerebras_keys()

# ============================================================
# 階段 1: 預掃描去重 (單線程，無競態條件)
# ============================================================

def extract_transcript(content: str) -> str:
    """提取逐字稿內容用於 hash 計算"""
    # 嘗試多種逐字稿標題格式
    patterns = [
        r'##\s*原始逐字稿\s*\n(.+?)(?=\n##|\Z)',
        r'##\s*完整逐字稿\s*\n(.+?)(?=\n##|\Z)',
        r'##\s*Transcript\s*\n(.+?)(?=\n##|\Z)',
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    # 嘗試知識提取區塊
    knowledge_match = re.search(r'## 商業知識提取\s*```markdown\s*(.+?)```', content, re.DOTALL)
    if knowledge_match:
        return knowledge_match.group(1).strip()
    return ""

def prescan_files(input_dir: Path) -> list:
    """
    預掃描所有檔案，返回唯一內容的檔案列表
    同時標記被跳過的重複檔案
    """
    print("\n📊 階段 1: 預掃描去重...", flush=True)
    
    all_files = list(input_dir.rglob("*.md"))
    print(f"   發現 {len(all_files)} 個 MD 檔案", flush=True)
    
    hash_to_file = {}  # hash -> (file_path, transcript_length)
    unique_files = []
    duplicate_count = 0
    skipped_new_format = 0
    skipped_empty = 0
    
    for i, file_path in enumerate(all_files):
        if (i + 1) % 100 == 0:
            print(f"   掃描進度: {i+1}/{len(all_files)}", flush=True)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 跳過已是新格式的檔案
            if content.strip().startswith('---'):
                first_end = content.find('---', 3)
                if first_end > 0 and 'entities:' in content[:first_end]:
                    skipped_new_format += 1
                    continue
            
            # 提取逐字稿
            transcript = extract_transcript(content)
            if not transcript or len(transcript) < 50:
                skipped_empty += 1
                continue
            
            # 計算 hash
            content_hash = hashlib.md5(transcript.encode('utf-8')).hexdigest()
            
            if content_hash in hash_to_file:
                # 重複：選擇逐字稿更長的那個
                existing_file, existing_len = hash_to_file[content_hash]
                if len(transcript) > existing_len:
                    # 替換
                    hash_to_file[content_hash] = (file_path, len(transcript))
                duplicate_count += 1
            else:
                hash_to_file[content_hash] = (file_path, len(transcript))
                
        except Exception as e:
            print(f"   ⚠️ 掃描錯誤: {file_path.name} - {e}", flush=True)
    
    unique_files = [fp for fp, _ in hash_to_file.values()]
    
    print(f"\n   📈 掃描結果:", flush=True)
    print(f"      唯一內容: {len(unique_files)} 個", flush=True)
    print(f"      重複跳過: {duplicate_count} 個", flush=True)
    print(f"      已處理格式: {skipped_new_format} 個", flush=True)
    print(f"      空/無效: {skipped_empty} 個", flush=True)
    
    return unique_files

# ============================================================
# 階段 2: 處理邏輯 (與之前類似)
# ============================================================

def parse_old_format(content: str) -> dict:
    result = {
        'title': '', 'source': 'youtube', 'author': '', 
        'url': '', 'duration': '', 'process_date': '', 
        'knowledge_zh': '', 'transcript_en': ''
    }
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    if title_match: result['title'] = title_match.group(1).strip()
    source_match = re.search(r'\*\*來源\*\*:\s*(.+)', content)
    if source_match:
        parts = source_match.group(1).split('/')
        if len(parts) >= 2: result['author'] = parts[-1].strip()
    url_match = re.search(r'\*\*URL\*\*:\s*(https?://[^\s]+)', content)
    if url_match: result['url'] = url_match.group(1).strip()
    duration_match = re.search(r'\*\*時長\*\*:\s*(\d+:\d+)', content)
    if duration_match: result['duration'] = duration_match.group(1).strip()
    date_match = re.search(r'\*\*處理日期\*\*:\s*(\d{4}-\d{2}-\d{2})', content)
    if date_match: result['process_date'] = date_match.group(1).strip()
    
    transcript_match = re.search(r'##\s*(原始逐字稿|完整逐字稿|Transcript)\s*\n(.+?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
    if transcript_match: result['transcript_en'] = transcript_match.group(2).strip()
    
    knowledge_match = re.search(r'## 商業知識提取\s*```markdown\s*(.+?)```', content, re.DOTALL)
    if knowledge_match: result['knowledge_zh'] = knowledge_match.group(1).strip()
    return result

def create_new_format(old_data: dict, knowledge_result: dict) -> str:
    yaml_lines = [
        "---",
        f"title: \"{old_data['title']}\"",
        "source: youtube",
        f"author: {old_data['author']}",
    ]
    if knowledge_result.get('guest'): yaml_lines.append(f"guest: {knowledge_result['guest']}")
    if old_data['url']: yaml_lines.append(f"url: {old_data['url']}")
    if old_data['duration']: yaml_lines.append(f"duration: \"{old_data['duration']}\"")
    if old_data['process_date']: 
        year = old_data['process_date'].split('-')[0]
        yaml_lines.append(f"content_year: {year}")
    
    yaml_lines.append(f"processed_at: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}")
    
    keywords = knowledge_result.get('keywords', [])
    if keywords: yaml_lines.append(f"keywords: [{', '.join(keywords[:10])}]")
    
    summary = knowledge_result.get('summary', '')
    if summary: yaml_lines.append(f'summary: "{summary.replace(chr(10), " ").replace(chr(34), chr(39))[:200]}"')
    
    entities = knowledge_result.get('entities', [])
    if entities: yaml_lines.append(f"entities: [{', '.join(entities[:8])}]")
    
    tags = knowledge_result.get('tags', [])
    if tags: yaml_lines.append(f"tags: [{', '.join(tags[:5])}]")
    
    yaml_lines.append("---")
    
    md_parts = [
        "\n".join(yaml_lines),
        "", "## 逐字稿全文", "",
        old_data['transcript_en'] or "_（無英文逐字稿）_",
        "", "---", "", "## AI 知識提取", "",
        knowledge_result.get('knowledge', old_data['knowledge_zh']) or "_（無知識提取結果）_",
    ]
    return '\n'.join(md_parts)

def call_cerebras_api(text: str, video_info: dict, api_key: str) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.cerebras.ai/v1")
    
    ontology_path = Path.home() / "R2R/config/ontology/solo_entrepreneur_synonyms.json"
    tags_path = Path.home() / "R2R/config/ontology/solo_entrepreneur_tags.yaml"
    
    entities_hint, tags_hint = "", ""
    try:
        with open(ontology_path, 'r') as f:
            entities_hint = ", ".join(list(json.load(f).keys())[:80])
    except: pass
    try:
        with open(tags_path, 'r') as f:
            dims = yaml.safe_load(f).get('dimensions', {}).values()
            cats = [c for d in dims for c in d.get('categories', {}).values()]
            tags_hint = ", ".join([t for c in cats for t in c.get('tags', [])][:40])
    except: pass
    
    prompt = f"""分析以下內容，提取一人公司創業相關的知識。

標題：{video_info.get('title', '')}
頻道：{video_info.get('channel', '')}

內容：
{text[:6000]}

請使用繁體中文（台灣用語）回答，並嚴格遵循以下格式：

[KEYWORDS]
列出 5-8 個關鍵字，逗號分隔

[SUMMARY]
一段 150 字以內的摘要

[ENTITIES]
從以下預設清單中選擇 5-8 個最相關的實體（嚴禁創建新項目）：
{entities_hint}

[TAGS]
從以下預設清單中選擇 3-5 個最相關的標籤（嚴禁創建新項目）：
{tags_hint}

[GUEST]
訪談嘉賓姓名（若無則留空）

[KNOWLEDGE]
提取的核心知識內容（markdown格式，使用繁體中文）"""

    response = client.chat.completions.create(
        model="qwen-3-235b-a22b-instruct-2507",
        messages=[
            {"role": "system", "content": "你是一人公司創業知識提取專家，使用繁體中文（台灣用語）回答。"},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2500,
        temperature=0.3
    )
    result_text = response.choices[0].message.content
    result = {}
    
    for k in ['KEYWORDS', 'SUMMARY', 'ENTITIES', 'TAGS', 'GUEST']:
        m = re.search(fr'\[{k}\]\s*(.+?)(?=\[|\Z)', result_text, re.DOTALL)
        if m: result[k.lower()] = m.group(1).strip()
    
    m_kn = re.search(r'\[KNOWLEDGE\]\s*(.+?)(?=\Z)', result_text, re.DOTALL)
    if m_kn: result['knowledge'] = m_kn.group(1).strip()
    
    if 'keywords' in result: result['keywords'] = [x.strip() for x in result['keywords'].split(',')]
    if 'entities' in result: result['entities'] = [x.strip() for x in result['entities'].split(',')]
    if 'tags' in result: result['tags'] = [x.strip() for x in result['tags'].split(',')]
    
    return result

# ============================================================
# 階段 3: 自適應控制 & 處理
# ============================================================

class AdaptiveController:
    def __init__(self):
        self.lock = threading.Lock()
        self.current_delay = INITIAL_DELAY
        self.api_key_index = 0
        self.exhausted_keys = set()
        self.success_count = 0
        self.error_count = 0
        
    def get_api_key(self):
        with self.lock:
            available = [k for k in CEREBRAS_KEYS if k not in self.exhausted_keys]
            if not available: return None
            key = available[self.api_key_index % len(available)]
            self.api_key_index += 1
            return key
            
    def report_success(self):
        with self.lock:
            self.success_count += 1
            self.error_count = 0
            if self.success_count > SUCCESS_THRESHOLD:
                self.current_delay = max(INITIAL_DELAY, self.current_delay / BACKOFF_FACTOR)
                self.success_count = 0
                
    def report_error(self, is_rate_limit: bool):
        with self.lock:
            self.error_count += 1
            self.current_delay = min(MAX_DELAY, self.current_delay * BACKOFF_FACTOR)
                
    def mark_key_exhausted(self, key):
        with self.lock:
            self.exhausted_keys.add(key)
            print(f"❌ API Key 耗盡: {key[:8]}...", flush=True)

    def wait(self):
        time.sleep(self.current_delay + random.uniform(0, 0.5))

class ProgressTracker:
    def __init__(self, progress_file: Path):
        self.progress_file = progress_file
        self.lock = threading.Lock()
        self.processed = set()
        self.load()
    
    def load(self):
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    self.processed = set(data.get('processed', []))
            except: pass
            
    def save(self):
        with self.lock:
            with open(self.progress_file, 'w') as f:
                json.dump({
                    'processed': list(self.processed),
                    'last_update': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
                
    def mark_done(self, file_path: str):
        with self.lock:
            self.processed.add(file_path)
            if len(self.processed) % 10 == 0:
                self.save()
                
    def is_done(self, file_path: str) -> bool:
        return file_path in self.processed

def process_file(file_path: Path, controller: AdaptiveController, progress: ProgressTracker) -> bool:
    file_key = str(file_path)
    if progress.is_done(file_key): 
        return None
    
    controller.wait()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
                
        old_data = parse_old_format(content)
        text = old_data['transcript_en'] or old_data['knowledge_zh']
        
        if not text:
            progress.mark_done(file_key)
            return None
            
        video_info = {'title': old_data['title'], 'channel': old_data['author'], 'url': old_data['url']}
        
        max_retries = 5
        for attempt in range(max_retries):
            api_key = controller.get_api_key()
            if not api_key: return False
            
            try:
                result = call_cerebras_api(text, video_info, api_key)
                if old_data['knowledge_zh'] and not result.get('knowledge'):
                    result['knowledge'] = old_data['knowledge_zh']
                    
                new_content = create_new_format(old_data, result)
                
                rel_path = file_path.relative_to(INPUT_DIR)
                out_path = OUTPUT_DIR / rel_path
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                    
                progress.mark_done(file_key)
                controller.report_success()
                print(f"  ✅ {file_path.name[:40]}...", flush=True)
                return True
                
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = '429' in err_msg or 'rate limit' in err_msg or 'quota' in err_msg
                
                if is_rate_limit:
                    controller.report_error(True)
                    controller.mark_key_exhausted(api_key)
                    if not controller.get_api_key():
                        print("❌ 所有 API Keys 耗盡", flush=True)
                        return False
                else:
                    controller.report_error(False)
                    print(f"  ⚠️ 錯誤 ({attempt+1}/{max_retries}): {e}", flush=True)
                    
                time.sleep(controller.current_delay * (attempt + 1))
                
        return False
    except Exception as e:
        print(f"  ❌ 嚴重錯誤: {file_path.name} - {e}", flush=True)
        return False

def main():
    if not CEREBRAS_KEYS:
        print("❌ 無可用 API Keys", flush=True)
        return
    
    # 清除舊的進度檔案以確保全新開始
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        print("🗑️ 已清除舊進度檔案", flush=True)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
    # 階段 1: 預掃描去重
    unique_files = prescan_files(INPUT_DIR)
    
    if not unique_files:
        print("❌ 無可處理的檔案", flush=True)
        return
    
    # 階段 2: 多線程處理
    print(f"\n📊 階段 2: 多線程處理 ({MAX_THREADS} 線程)...", flush=True)
    
    progress = ProgressTracker(PROGRESS_FILE)
    controller = AdaptiveController()
    
    pending_files = [f for f in unique_files if not progress.is_done(str(f))]
    print(f"   待處理: {len(pending_files)} 個唯一內容檔案", flush=True)
    
    success_count = 0
    error_count = 0
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(process_file, f, controller, progress): f for f in pending_files}
        
        for future in as_completed(futures):
            result = future.result()
            if result is True:
                success_count += 1
            elif result is False:
                error_count += 1
            
            if not controller.get_api_key():
                print("🏁 停止：無可用 API Keys", flush=True)
                break

    progress.save()
    
    print("\n" + "=" * 70, flush=True)
    print("✅ 處理完成", flush=True)
    print(f"   成功: {success_count}", flush=True)
    print(f"   錯誤: {error_count}", flush=True)
    print(f"   輸出目錄: {OUTPUT_DIR}", flush=True)
    print("=" * 70, flush=True)

if __name__ == "__main__":
    main()
