# handlers/groq_handler.py
# Handler for Groq LLM API operations

import os
import requests
from typing import List, Optional


class GroqHandler:
    """Handler for Groq LLM API with multi-key failover"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Groq handler
        
        Args:
            api_key: Single API key or comma-separated multiple keys
        """
        if api_key:
            self.apikeys = api_key.split(",") if isinstance(api_key, str) else api_key
        else:
            env_key = os.getenv("GROQ_API_KEY", "")
            self.apikeys = env_key.split(",") if env_key else []
        
        # Strip whitespace from keys
        self.apikeys = [k.strip() for k in self.apikeys if k.strip()]

    def groqrequest(self, prompt: str, model: str = "llama-3.3-70b-versatile") -> str:
        """
        Send request to Groq API with automatic failover
        
        Args:
            prompt: The prompt to send
            model: Model to use (default: llama-3.3-70b-versatile)
            
        Returns:
            Model response text or error dict
        """
        url = "https://api.groq.com/openai/v1/chat/completions"
        data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,  # Low temperature for more consistent outputs
            "max_tokens": 4096
        }

        # Try each API key
        for idx, key in enumerate(self.apikeys):
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}"
            }
            
            try:
                response = requests.post(url, json=data, headers=headers, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    raw_content = result["choices"][0]["message"]["content"]
                    return raw_content
                    
                elif response.status_code == 401:
                    print(f"API key {idx + 1} unauthorized")
                    continue
                    
                elif response.status_code == 429:
                    print(f"API key {idx + 1} rate limited")
                    continue
                    
                elif response.status_code >= 500:
                    print(f"Server error with API key {idx + 1}: {response.status_code}")
                    continue
                    
                else:
                    print(f"Error {response.status_code}: {response.text}")
                    continue
                    
            except requests.exceptions.Timeout:
                print(f"Request timeout with API key {idx + 1}")
                continue
            except Exception as e:
                print(f"Exception with API key {idx + 1}: {str(e)}")
                continue
        
        # All keys failed
        return '{"error": "All API keys failed or rate limited"}'
    
    def test_connection(self) -> bool:
        """
        Test Groq API connection
        
        Returns:
            True if at least one API key works, False otherwise
        """
        test_prompt = "Say 'OK' if you can read this."
        response = self.groqrequest(test_prompt)
        return not response.startswith('{"error":')