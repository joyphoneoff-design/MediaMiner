#!/usr/bin/env python3
"""
R2R 連接器
與 R2R 向量資料庫整合
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# 載入環境變數
env_path = Path(__file__).parent.parent / "config" / "api_keys.env"
load_dotenv(env_path)


class R2RConnector:
    """R2R 向量資料庫連接器"""
    
    def __init__(self, 
                 collection_name: str = "crawl_r2r_dev",
                 config_path: str = None):
        self.collection_name = collection_name
        self.r2r_home = Path.home() / "R2R"
        
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self.r2r_home / "r2r_config.toml"
    
    def check_r2r_status(self) -> Dict:
        """
        檢查 R2R 服務狀態
        
        Returns:
            {'running': bool, 'version': str, 'collections': [...]}
        """
        status = {
            'running': False,
            'version': None,
            'collections': [],
            'error': None
        }
        
        try:
            # 檢查 R2R CLI
            result = subprocess.run(
                ["r2r", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                status['version'] = result.stdout.strip()
            
            # 檢查服務狀態
            result = subprocess.run(
                ["r2r", "health"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and "healthy" in result.stdout.lower():
                status['running'] = True
                
        except FileNotFoundError:
            status['error'] = "R2R CLI not found"
        except subprocess.TimeoutExpired:
            status['error'] = "R2R service timeout"
        except Exception as e:
            status['error'] = str(e)
        
        return status
    
    def ingest_file(self, file_path: str) -> Dict:
        """
        將文件 ingest 到 R2R
        
        Args:
            file_path: MD 文件路徑
            
        Returns:
            {'success': bool, 'document_id': str, 'error': str}
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {'success': False, 'error': f"File not found: {file_path}"}
        
        if not file_path.suffix.lower() == '.md':
            return {'success': False, 'error': "Only .md files supported"}
        
        try:
            cmd = [
                "r2r",
                "ingest-files",
                str(file_path),
                "--collection", self.collection_name
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'document_id': self._extract_doc_id(result.stdout),
                    'message': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr or result.stdout
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def batch_ingest(self, file_paths: List[str]) -> List[Dict]:
        """
        批次 ingest 多個文件
        
        Args:
            file_paths: 文件路徑列表
            
        Returns:
            結果列表
        """
        results = []
        for i, path in enumerate(file_paths, 1):
            print(f"📥 [{i}/{len(file_paths)}] Ingesting: {Path(path).name}")
            result = self.ingest_file(path)
            result['file'] = path
            results.append(result)
            
            if result['success']:
                print(f"   ✅ 成功")
            else:
                print(f"   ❌ 失敗: {result.get('error', 'Unknown error')}")
        
        success_count = sum(1 for r in results if r['success'])
        print(f"\n📊 完成: {success_count}/{len(file_paths)} 成功")
        
        return results
    
    def search(self, query: str, top_k: int = 5) -> Dict:
        """
        搜索向量資料庫
        
        Args:
            query: 查詢文字
            top_k: 返回結果數量
            
        Returns:
            搜索結果
        """
        try:
            cmd = [
                "r2r",
                "search",
                query,
                "--collection", self.collection_name,
                "--limit", str(top_k)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'results': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def rag_query(self, query: str) -> Dict:
        """
        RAG 查詢
        
        Args:
            query: 問題
            
        Returns:
            RAG 回答
        """
        try:
            cmd = [
                "r2r",
                "rag",
                query,
                "--collection", self.collection_name
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'answer': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _extract_doc_id(self, output: str) -> Optional[str]:
        """從輸出中提取文檔 ID"""
        import re
        match = re.search(r'document[_-]?id[:\s]+([a-zA-Z0-9-]+)', output, re.IGNORECASE)
        if match:
            return match.group(1)
        return None


if __name__ == "__main__":
    print("🔗 Crawl_R2R R2R Connector")
    print("=" * 50)
    
    connector = R2RConnector()
    
    # 檢查狀態
    status = connector.check_r2r_status()
    print(f"R2R Version: {status.get('version', 'N/A')}")
    print(f"Running: {status.get('running', False)}")
    if status.get('error'):
        print(f"Error: {status['error']}")
