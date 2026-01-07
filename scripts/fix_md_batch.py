#!/usr/bin/env python3
"""
MD 檔案批次修正腳本
修正項目：
1. 移除 <!-- GUEST: --> 殘留標記
2. 清理 Kind: captions 等元數據行
3. (content_year 缺失無法補，因原始數據未提供)
4. (逐字稿語言問題需重新抓取，無法事後修正)
"""

import re
from pathlib import Path

PROCESSED_DIR = Path.home() / "Documents/MediaMiner_Data/processed"

def fix_md_file(filepath: Path) -> dict:
    """修正單個 MD 檔案"""
    content = filepath.read_text(encoding='utf-8')
    original = content
    fixes = []
    
    # 1. 移除 <!-- GUEST: --> 殘留
    if re.search(r'<!--\s*GUEST:', content):
        content = re.sub(r'\n*<!--\s*GUEST:.*?-->\n*', '\n', content)
        fixes.append('removed_guest_comment')
    
    # 2. 清理 Kind: captions 行
    if 'Kind: captions' in content or 'Language: zh' in content:
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            if re.match(r'^Kind:\s*', line, re.IGNORECASE):
                continue
            if re.match(r'^Language:\s*', line, re.IGNORECASE):
                continue
            cleaned_lines.append(line)
        content = '\n'.join(cleaned_lines)
        fixes.append('removed_metadata_lines')
    
    # 3. 移除多餘空行 (超過 2 行連續空行)
    content = re.sub(r'\n{4,}', '\n\n\n', content)
    
    # 只有有變更才寫入
    if content != original:
        filepath.write_text(content, encoding='utf-8')
        return {'file': filepath.name, 'fixes': fixes}
    
    return None

def main():
    print("🔧 MD 批次修正腳本")
    print("=" * 50)
    
    files = list(PROCESSED_DIR.glob('*.md'))
    print(f"處理 {len(files)} 個檔案...\n")
    
    fixed_count = 0
    for f in files:
        result = fix_md_file(f)
        if result:
            fixed_count += 1
            print(f"✅ {result['file'][:40]}...")
            print(f"   修正: {', '.join(result['fixes'])}")
    
    print("\n" + "=" * 50)
    print(f"修正完成: {fixed_count}/{len(files)} 個檔案")

if __name__ == "__main__":
    main()
