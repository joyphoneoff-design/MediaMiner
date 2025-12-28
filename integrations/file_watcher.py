#!/usr/bin/env python3
"""
檔案監控服務
監控處理目錄並自動觸發 R2R ingest
"""

import os
import time
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.r2r_connector import R2RConnector


class R2RFileHandler(FileSystemEventHandler):
    """R2R 檔案事件處理器"""
    
    def __init__(self, 
                 r2r_connector: R2RConnector,
                 callback: Optional[Callable] = None):
        self.connector = r2r_connector
        self.callback = callback
        self.processed_files = set()
    
    def on_created(self, event: FileCreatedEvent):
        """處理新建檔案"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # 只處理 .md 檔案
        if file_path.suffix.lower() != '.md':
            return
        
        # 防止重複處理
        if str(file_path) in self.processed_files:
            return
        
        # 等待檔案寫入完成
        time.sleep(1)
        
        print(f"📄 檢測到新檔案: {file_path.name}")
        
        # 執行 ingest
        result = self.connector.ingest_file(str(file_path))
        
        if result['success']:
            print(f"   ✅ 已 ingest 到 R2R")
            self.processed_files.add(str(file_path))
        else:
            print(f"   ❌ Ingest 失敗: {result.get('error', '')}")
        
        # 回調
        if self.callback:
            self.callback(file_path, result)


class FileWatcher:
    """檔案監控服務"""
    
    def __init__(self, 
                 watch_dir: str = "~/Documents/Crawl_R2R_Data/processed",
                 collection_name: str = "crawl_r2r_dev"):
        self.watch_dir = Path(watch_dir).expanduser()
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        
        self.connector = R2RConnector(collection_name=collection_name)
        self.observer = None
        self.running = False
    
    def start(self, callback: Callable = None):
        """
        啟動監控
        
        Args:
            callback: 處理完成後的回調函數
        """
        if self.running:
            print("⚠️ 監控已在運行")
            return
        
        handler = R2RFileHandler(self.connector, callback)
        self.observer = Observer()
        self.observer.schedule(handler, str(self.watch_dir), recursive=True)
        
        self.observer.start()
        self.running = True
        
        print(f"👁️ 開始監控目錄: {self.watch_dir}")
        print("   按 Ctrl+C 停止...")
    
    def stop(self):
        """停止監控"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.running = False
            print("🛑 監控已停止")
    
    def run_forever(self, callback: Callable = None):
        """持續運行"""
        self.start(callback)
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n收到中斷信號...")
        finally:
            self.stop()


if __name__ == "__main__":
    print("👁️ Crawl_R2R File Watcher")
    print("=" * 50)
    
    watcher = FileWatcher()
    
    def on_processed(file_path, result):
        print(f"📊 處理完成: {file_path.name}")
        print(f"   結果: {'成功' if result['success'] else '失敗'}")
    
    watcher.run_forever(callback=on_processed)
