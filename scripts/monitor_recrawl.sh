#!/bin/bash
# MediaMiner 重新抓取監控腳本
# 此腳本在背景監控 processed 目錄的變化，並驗證無重複

WATCH_DIR="$HOME/Documents/MediaMiner_Data/processed"
LOG_FILE="$HOME/Documents/MediaMiner_Data/monitor_log.txt"

echo "=== MediaMiner 監控腳本啟動 ===" | tee -a "$LOG_FILE"
echo "監控目錄: $WATCH_DIR" | tee -a "$LOG_FILE"
echo "開始時間: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

prev_count=0
while true; do
    count=$(find "$WATCH_DIR" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    
    if [ "$count" -ne "$prev_count" ]; then
        echo "[$(date '+%H:%M:%S')] 檔案數: $count (新增 $((count - prev_count)))" | tee -a "$LOG_FILE"
        prev_count=$count
        
        # 每 10 個檔案做一次重複檢測
        if [ $((count % 10)) -eq 0 ] && [ "$count" -gt 0 ]; then
            echo "[$(date '+%H:%M:%S')] 執行重複檢測..." | tee -a "$LOG_FILE"
            
            # 計算所有逐字稿的 MD5
            dup_count=$(find "$WATCH_DIR" -name "*.md" -exec grep -l "^##\|逐字稿" {} \; 2>/dev/null | while read f; do
                grep -A 9999 "## 逐字稿" "$f" 2>/dev/null | head -100 | md5
            done | sort | uniq -d | wc -l | tr -d ' ')
            
            if [ "$dup_count" -gt 0 ]; then
                echo "[$(date '+%H:%M:%S')] ⚠️ 發現 $dup_count 個潛在重複!" | tee -a "$LOG_FILE"
            else
                echo "[$(date '+%H:%M:%S')] ✅ 無重複" | tee -a "$LOG_FILE"
            fi
        fi
    fi
    
    sleep 5
done
