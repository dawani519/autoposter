import requests
from config import OPENAI_URL, OPENAI_API_KEY

def generate_post_content(niche):
    API_URL = OPENAI_URL
    API_KEY = OPENAI_API_KEY

    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "user", "content": f"Write a short social media post about {niche} under 280 characters."}
        ]
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "AutoPosterApp"
    }

    try:
        r = requests.post(API_URL, headers=headers, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print("Error generating content:", e)
        return "default generated post for now"
