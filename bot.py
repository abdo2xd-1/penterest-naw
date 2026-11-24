import os
import re
import time
import json
import random
import urllib.parse
import requests
import cloudinary
import cloudinary.uploader
from PIL import Image

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
BUFFER_CHANNEL_ID = os.environ["BUFFER_CHANNEL_ID"]
CLOUDINARY_URL = os.environ["CLOUDINARY_URL"]
HISTORY_FILE = "history.json"

CATEGORIES = [
    "Mini Robotics & RC Cars",
    "Smart Home Automation & Relays",
    "RGB LED Matrix & Audio Visualizers",
    "RFID & Fingerprint Security Locks",
    "OLED Mini Weather & Clock Stations",
    "DIY Power Bank & Solar Chargers",
    "Ultrasonic Radar & Motion Alarms",
    "Retro Mini Gaming Consoles",
    "Bluetooth Audio & DIY Amplifiers",
    "Gesture-Controlled Gadgets"
]

PHOTO_STYLES = [
    "placed on a vibrant solid yellow studio background, bright even studio lighting, clean commercial product photography",
    "placed on a warm wooden workbench, natural bright daylight, soft blurred background bokeh, authentic maker photography",
    "placed on a clean minimalist teal matte desk, crisp bright studio lighting, macro product photography"
]

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
    
    selected_category = random.choice(CATEGORIES)
    selected_style = random.choice(PHOTO_STYLES)
    avoid_list = ", ".join(past_projects[-50:]) if past_projects else "None"

    payload = {
        "model": "openai/gpt-oss-120b",
        "temperature": 0.7,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a Pinterest SEO specialist and DIY electronics expert. "
                    "Respond ONLY with a single raw valid JSON object (no markdown, no extra text). "
                    "Keep all text concise so the total description stays strictly under 450 characters."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Generate 1 unique, viral DIY electronics project idea specifically in the category: '{selected_category}'.\n"
                    f"DO NOT repeat or make anything similar to these past projects: [{avoid_list}].\n\n"
                    "Return JSON with exact keys:\n"
                    "- 'title': SEO-optimized catchy title with strong keywords (max 80 chars).\n"
                    "- 'hook': 1 short SEO-rich sentence explaining the project (max 110 chars).\n"
                    "- 'components': An array of 4 short electronic components (e.g. 'Arduino Uno', 'OLED Display', 'Ultrasonic Sensor', 'Jumper Wires').\n"
                    "- 'cta': 1 short sentence encouraging to Save & Follow for daily DIY electronics (max 70 chars).\n"
                    "- 'hashtags': 4 high-ranking hashtags (e.g. '#DIYElectronics #Arduino #ESP32 #Robotics').\n"
                    f"- 'image_prompt': Write a sharp, realistic macro DSLR photograph prompt (shot on 85mm lens, shallow depth of field) of the real DIY electronics project featuring a blue Arduino Uno or ESP32 circuit board, green PCB sensor modules, colorful rainbow jumper wires, and a tiny glowing red indicator LED, {selected_style}. Ultra-sharp focus on the electronic pins and chips, photorealistic, no text, no watermark. Do not use forward slashes."
                )
            }
        ]
    }

    for attempt in range(3):
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.ok:
            content = res.json()["choices"][0]["message"]["content"].strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError as e:
                    print(f"JSON parse error on attempt {attempt + 1}:", e)
            else:
                print(f"No JSON found on attempt {attempt + 1}:", content)
        else:
            print(f"Groq Attempt {attempt + 1} failed:", res.text)
    raise Exception("Failed to generate valid project JSON from Groq after 3 attempts.")

def generate_and_host_image(image_prompt):
    # تنظيف البرومبت وتشفير كل الرموز بما فيها "/"
    clean_prompt = image_prompt.replace("/", " ").strip()
    prompt_encoded = urllib.parse.quote(clean_prompt, safe="")
    headers = {"User-Agent": "Mozilla/5.0"}

    img_res = None
    for attempt in range(4):
        seed = random.randint(1, 999999)
        model_param = "&model=flux" if attempt < 3 else ""
        pollinations_url = (
            f"https://image.pollinations.ai/prompt/{prompt_encoded}"
            f"?width=768&height=1216{model_param}&seed={seed}&nologo=true"
        )
        print(f"Downloading image from Pollinations (Attempt {attempt + 1})...")
        try:
            res = requests.get(pollinations_url, headers=headers, timeout=90)
            content_type = res.headers.get("Content-Type", "")
            if res.ok and "image" in content_type:
                img_res = res
                break
            print(f"Pollinations returned {res.status_code} ({content_type}), retrying...")
        except Exception as e:
            print(f"Pollinations error on attempt {attempt + 1}: {e}")
        time.sleep(6)

    if img_res is None:
        raise Exception("Failed to download image from Pollinations after 4 attempts.")

    with open("raw_pin.jpg", "wb") as f:
        f.write(img_res.content)

    # قص آخر 64 بكسل من أسفل الصورة لإزالة العلامة المائية نهائياً
    with Image.open("raw_pin.jpg") as img:
        width, height = img.size
        cropped = img.crop((0, 0, width, height - 64))
        cropped.save("pin.jpg", "JPEG", quality=95)

    print("Uploading image to Cloudinary...")
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)
    upload_res = cloudinary.uploader.upload("pin.jpg", folder="pinterest_pins")
    direct_url = upload_res["secure_url"]
    print("Direct Image URL:", direct_url)
    return direct_url

def get_pinterest_board_id():
    url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {BUFFER_API_KEY}",
        "Content-Type": "application/json"
    }
    query = f"""
    query {{
      channel(input: {{ id: "{BUFFER_CHANNEL_ID}" }}) {{
        metadata {{
          ... on PinterestMetadata {{
            boards {{
              serviceId
            }}
          }}
        }}
      }}
    }}
    """
    res = requests.post(url, headers=headers, json={"query": query}, timeout=30)
    res.raise_for_status()
    data = res.json()
    boards = data.get("data", {}).get("channel", {}).get("metadata", {}).get("boards", [])
    if not boards:
        raise Exception(f"No Pinterest boards found in Buffer! Response: {data}")
    board_id = boards[0]["serviceId"]
    print("Selected Pinterest Board ID:", board_id)
    return board_id

def publish_to_buffer(title, full_text, image_url, board_id):
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
            "text": full_text[:495],
            "schedulingType": "automatic",
            "mode": "shareNow",
            "metadata": {
                "pinterest": {
                    "boardServiceId": board_id,
                    "title": title[:100]
                }
            },
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
        f"{project['hook']}\n\n"
        f"🔧 Parts:\n"
        f"{components_text}\n\n"
        f"👉 {project['cta']}\n\n"
        f"{project['hashtags']}"
    )

    board_id = get_pinterest_board_id()
    direct_image_url = generate_and_host_image(project["image_prompt"])

    if publish_to_buffer(project["title"], full_pin_text, direct_image_url, board_id):
        history.append(project["title"])
        save_history(history)
        print("Project saved to history.json!")
    else:
        raise Exception("Failed to publish to Buffer, history not updated.")
