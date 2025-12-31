#!/usr/bin/env python3
"""
LLM 客戶端
支持多提供商自動切換 (80/20 法則 - 免費優先)
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict, List, Generator
from dotenv import load_dotenv

# 載入 API 密鑰
env_path = Path(__file__).parent.parent / "config" / "api_keys.env"
load_dotenv(env_path)


class LLMClient:
    """多提供商 LLM 客戶端"""
    
    PROVIDERS = [
        {
            "name": "cerebras",
            "priority": 1,
            "model": "qwen-3-235b-a22b-instruct-2507",  # Qwen 235B - 免費穩定
            "env_keys": ["CEREBRAS_API_KEY"],
            "base_url": "https://api.cerebras.ai/v1"
        },
        {
            "name": "openrouter",
            "priority": 2,
            "model": "google/gemini-2.0-flash-exp:free",  # 16 req/min 限制
            "env_keys": ["OPENROUTER_API_KEY"],
            "base_url": "https://openrouter.ai/api/v1"
        },
        {
            "name": "gemini",
            "priority": 3,
            "model": "gemini-2.5-flash-lite",  # API key 需更新
            "env_keys": ["GEMINI_API_KEY", "GEMINI_API_KEY_BACKUP"]
        },
        {
            "name": "cerebras_glm",
            "priority": 4,
            "model": "zai-glm-4.6",  # GLM 4.6 備用
            "env_keys": ["CEREBRAS_API_KEY"],
            "base_url": "https://api.cerebras.ai/v1"
        },
        {
            "name": "lmstudio",
            "priority": 5,
            "model": "qwen3-30b-a3b",
            "base_url": "http://localhost:1234/v1"
        },
        {
            "name": "openai",
            "priority": 6,
            "model": "gpt-4o-mini",
            "env_keys": ["OPENAI_API_KEY"]
        }
    ]
    
    def __init__(self):
        self.current_provider = None
        self.retry_count = 0
        self.max_retries = 3
        
    def _get_gemini_client(self, api_key: str):
        """初始化 Gemini 客戶端"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            return genai
        except ImportError:
            print("❌ google-generativeai not installed")
            return None
    
    def _get_openai_compatible_client(self, base_url: str, api_key: str):
        """初始化 OpenAI 兼容客戶端"""
        try:
            from openai import OpenAI
            return OpenAI(base_url=base_url, api_key=api_key)
        except ImportError:
            print("❌ openai not installed")
            return None
    
    def generate(self, prompt: str, system_prompt: str = None, 
                 max_tokens: int = 4096, temperature: float = 0.7) -> Optional[str]:
        """
        生成文本 (自動切換提供商)
        
        Args:
            prompt: 用戶提示
            system_prompt: 系統提示
            max_tokens: 最大 token 數
            temperature: 生成溫度
            
        Returns:
            生成的文本
        """
        for provider in self.PROVIDERS:
            result = self._try_provider(provider, prompt, system_prompt, 
                                        max_tokens, temperature)
            if result:
                return result
        
        print("❌ 所有 LLM 提供商都失敗")
        return None
    
    def _try_provider(self, provider: Dict, prompt: str, 
                      system_prompt: str, max_tokens: int, 
                      temperature: float) -> Optional[str]:
        """嘗試單個提供商"""
        name = provider["name"]
        model = provider["model"]
        
        # 獲取 API 密鑰
        api_key = None
        if "env_keys" in provider:
            for key_name in provider["env_keys"]:
                api_key = os.getenv(key_name)
                if api_key:
                    break
        
        if name != "lmstudio" and not api_key:
            return None
        
        print(f"🔄 嘗試 {name} ({model})...")
        
        try:
            if name == "gemini":
                return self._call_gemini(api_key, model, prompt, 
                                        system_prompt, max_tokens, temperature)
            elif name == "lmstudio":
                return self._call_openai_compatible(
                    provider.get("base_url", "http://localhost:1234/v1"),
                    "lm-studio", model, prompt, system_prompt, 
                    max_tokens, temperature
                )
            else:
                return self._call_openai_compatible(
                    provider.get("base_url", "https://api.openai.com/v1"),
                    api_key, model, prompt, system_prompt,
                    max_tokens, temperature
                )
        except Exception as e:
            print(f"   ⚠️ {name} 失敗: {e}")
            # 429 限速時等待 2 秒再嘗試下一個提供商
            if "429" in str(e) or "rate limit" in str(e).lower():
                print(f"   ⏳ 等待 2 秒...")
                time.sleep(2)
            return None
    
    def _call_gemini(self, api_key: str, model: str, prompt: str,
                     system_prompt: str, max_tokens: int, 
                     temperature: float) -> Optional[str]:
        """調用 Gemini API"""
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        
        model_instance = genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config,
            system_instruction=system_prompt if system_prompt else None
        )
        
        response = model_instance.generate_content(prompt)
        
        if response.text:
            print(f"   ✅ Gemini 成功")
            self.current_provider = "gemini"
            return response.text
        
        return None
    
    def _call_openai_compatible(self, base_url: str, api_key: str, 
                                model: str, prompt: str, system_prompt: str,
                                max_tokens: int, temperature: float) -> Optional[str]:
        """調用 OpenAI 兼容 API"""
        from openai import OpenAI
        
        client = OpenAI(base_url=base_url, api_key=api_key)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        if response.choices and response.choices[0].message.content:
            provider_name = "openai" if "openai.com" in base_url else \
                           "lmstudio" if "localhost" in base_url else \
                           base_url.split("//")[1].split(".")[0]
            print(f"   ✅ {provider_name} 成功")
            self.current_provider = provider_name
            return response.choices[0].message.content
        
        return None


# 單例
_llm_client = None

def get_llm_client() -> LLMClient:
    """獲取 LLM 客戶端單例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


if __name__ == "__main__":
    print("🤖 MediaMiner LLM Client")
    print("=" * 50)
    
    client = get_llm_client()
    
    # 測試
    response = client.generate(
        prompt="請用繁體中文簡單介紹什麼是商業模式畫布？",
        system_prompt="你是一位商業顧問，請用簡潔的語言回答。",
        max_tokens=500
    )
    
    if response:
        print("\n📝 回應:")
        print(response)
