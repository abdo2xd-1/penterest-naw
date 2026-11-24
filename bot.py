import os
import json
import requests
import cloudinary
import cloudinary.uploader

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
BUFFER_CHANNEL_ID = os.environ["BUFFER_CHANNEL_ID"]
CLOUDINARY_URL = os.environ["CLOUDINARY_URL"]
HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def generate_project_idea(past_projects):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    avoid_list = ", ".join(past_projects[-50:]) if past_projects else "None"

    payload = {
        "model": "openai/gpt-oss-120b",
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a Pinterest SEO specialist and DIY electronics expert. "
                    "Always respond with valid JSON only. Focus on high-search-volume keywords "
                    "like Arduino, ESP32, DIY electronics, circuit, robotics, smart home, and gadgets."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Generate 1 unique, viral DIY electronics project idea for a Pinterest Pin. "
                    f"DO NOT repeat or make anything similar to these past projects: [{avoid_list}].\n\n"
                    "Return JSON with exact keys:\n"
                    "- 'title': SEO-optimized catchy title with strong keywords (max 85 chars).\n"
                    "- 'hook': 1-2 engaging SEO-rich sentences explaining what the project does and why it's awesome.\n"
                    "- 'components': An array of 4 to 6 exact electronic components needed (e.g. 'ESP32 Board', 'HC-SR04 Ultrasonic Sensor').\n"
                    "- 'cta': A friendly, engaging sentence encouraging the viewer to Save this pin and Follow the profile for daily DIY electronics ideas.\n"
                    "- 'hashtags': A string of 5 to 7 high-ranking Pinterest hashtags (e.g. '#DIYElectronics #ArduinoProjects #ESP32').\n"
                    "- 'image_prompt': Detailed visual description for a vertical 2:3 aesthetic Pinterest photo of the finished electronics project on a clean workbench, studio lighting, photorealistic, no text."
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

def generate_and_host_image(image_prompt):
    prompt_encoded = requests.utils.quote(image_prompt)
    pollinations_url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1000&height=1500&nologo=true"
    
    print("Downloading generated image...")
    headers = {"User-Agent": "Mozilla/5.0"}
    img_res = requests.get(pollinations_url, headers=headers, timeout=60)
    img_res.raise_for_status()

    content_type = img_res.headers.get("Content-Type", "")
    if "image" not in content_type:
        raise Exception(f"Pollinations did not return an image! Content-Type: {content_type}")

    with open("pin.jpg", "wb") as f:
        f.write(img_res.content)

    print("Uploading image to Cloudinary...")
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)
    upload_res = cloudinary.uploader.upload("pin.jpg", folder="pinterest_pins")
    direct_url = upload_res["secure_url"]
    print("Direct Image URL:", direct_url)
    return direct_url

def publish_to_buffer(full_text, image_url):
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
            "text": full_text,
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
    
    data = res.json()
    print("Buffer Response:", json.dumps(data, ensure_ascii=False, indent=2))
    
    post_result = data.get("data", {}).get("createPost", {})
    if "post" in post_result:
        return True
    return False

if __name__ == "__main__":
    history = load_history()
    project = generate_project_idea(history)
    print("Generated Project:", project["title"])

    components_text = "\n".join([f"• {item}" for item in project["components"]])
    full_pin_text = (
        f"{project['title']}\n\n"
        f"{project['hook']}\n\n"
        f"🔧 Components Needed:\n"
        f"{components_text}\n\n"
        f"👉 {project['cta']}\n\n"
        f"{project['hashtags']}"
    )

    direct_image_url = generate_and_host_image(project["image_prompt"])

    if publish_to_buffer(full_pin_text, direct_image_url):
        history.append(project["title"])
        save_history(history)
        print("Project saved to history.json!")
    else:
        raise Exception("Failed to publish to Buffer, history not updated.")
