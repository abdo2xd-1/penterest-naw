import os
import json
import requests

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
BUFFER_CHANNEL_ID = os.environ["BUFFER_CHANNEL_ID"]

def generate_project_idea():
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-oss-120b",
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You are a DIY electronics expert. Always respond with valid JSON only."
            },
            {
                "role": "user",
                "content": (
                    "Generate 1 cool DIY electronics project idea for a Pinterest Pin. "
                    "Return JSON with exact keys: "
                    "'title' (catchy, max 80 chars), "
                    "'description' (engaging with hashtags and brief steps, max 400 chars), "
                    "'image_prompt' (detailed visual description for a vertical 2:3 Pinterest photo of the electronics project on a workbench)."
                )
            }
        ]
    }
    res = requests.post(url, headers=headers, json=payload, timeout=30)
    if not res.ok:
        print("Groq API Error:", res.text)
    res.raise_for_status()
    content = res.json()["choices"][0]["message"]["content"]
    return json.loads(content)

def publish_to_buffer(title, description, image_url):
    url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {BUFFER_API_KEY}",
        "Content-Type": "application/json"
    }
    query = """
    mutation CreatePin($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id
            status
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """
    variables = {
        "input": {
            "channelId": BUFFER_CHANNEL_ID,
            "text": f"{title}\n\n{description}",
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "assets": [
                {
                    "image": {
                        "url": image_url
                    }
                }
            ]
        }
    }
    res = requests.post(url, headers=headers, json={"query": query, "variables": variables}, timeout=30)
    if not res.ok:
        print("Buffer API Error:", res.text)
    res.raise_for_status()
    print("Buffer Response:", json.dumps(res.json(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    project = generate_project_idea()
    print("Generated Project:", project["title"])

    prompt_encoded = requests.utils.quote(project["image_prompt"])
    image_url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1000&height=1500&nologo=true"

    publish_to_buffer(
        title=project["title"],
        description=project["description"],
        image_url=image_url
    )
