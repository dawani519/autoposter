import requests

def generate_post_content(niche):
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    API_KEY = ""

    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "user", "content": f"#insert your prompt here."}
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
