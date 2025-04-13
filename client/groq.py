import requests
import os
import streamlit as st
import json


apikeys = os.getenv("GROQ_API_KEY", "").split(",")


def groqrequest(prompt):
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

    for key in apikeys:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key.strip()}"
        }

        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                result = response.json()
                st.write(result)
                raw_content = result["choices"][0]["message"]["content"]

                # Strip markdown code block (```json ... ```)
                if raw_content.startswith("```"):
                    raw_content = raw_content.strip("`").strip()
                    if raw_content.lower().startswith("json"):
                        raw_content = raw_content[4:].strip()

                return json.loads(raw_content)

            elif response.status_code == 401:
                st.warning(f"API key failed (unauthorized): {key.strip()}")
                continue  # Try next key
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
                return {"error": "API request failed"}
        except (KeyError, json.JSONDecodeError) as e:
            st.error(f"Failed to parse response: {str(e)}")
            return {"error": "Invalid API response format"}
        except Exception as e:
            st.error(f"Request failed: {str(e)}")
            return {"error": "Request exception"}

    st.error("Daily limit reached or all API keys are invalid.")
    return {"error": "All API keys failed or rate limit reached"}