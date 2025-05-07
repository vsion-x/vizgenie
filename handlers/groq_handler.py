import os
import requests
import streamlit as st
import json

class GroqHandler:
    def __init__(self, api_key=None):

        self.apikeys = api_key if api_key else os.getenv("GROQ_API_KEY", "").split(",")

    def groqrequest(self, prompt):
        """Send a request to the Groq API using multiple API keys until successful or all fail."""
        url = "https://api.groq.com/openai/v1/chat/completions"
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        for key in self.apikeys:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key.strip()}"
            }

            
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                result = response.json()
                st.write(result)
                raw_content = result["choices"][0]["message"]["content"]
                return raw_content
            elif response.status_code == 401:
                st.warning(f"API key failed (unauthorized): {key.strip()}")
                continue  # Try next key
            elif response.status_code == 429:
                st.warning(f"Rate limit reached for API key: {key.strip()}")
                continue  # Try next key
            elif response.status_code == 500:
                st.warning(f"Server error for API key: {key.strip()}")
                continue  # Try next key
            elif response.status_code == 503:
                st.warning(f"Service unavailable for API key: {key.strip()}")
                continue  # Try next key
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
                return {"error": "API request failed"}