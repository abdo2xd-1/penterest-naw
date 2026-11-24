import os
import re
import json
import random
import requests
import cloudinary
import cloudinary.uploader

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
BUFFER_API_KEY = os.environ["BUFFER_API_KEY"]
BUFFER_CHANNEL_ID = os.environ["BUFFER_CHANNEL_ID"]
CLOUDINARY_URL = os.environ["CLOUDINARY_URL"]
PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
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

FALLBACK_QUERIES = [
    "arduino circuit board",
    "electronic circuit board macro",
    "microchip electronics",
    "soldering electronics",
    "robotics electronics",
    "motherboard microchip",
    "electronic components wires"
]

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return {"projects": data, "photo_ids": []}
            return {
                "projects": data.get("projects", []),
                "photo_ids": data.get("photo_ids", [])
            }
    return {"projects": [], "photo_ids": []}

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
                    "- 'pexels_query': 2 to 3 simple English search keywords to find a real electronics/circuit photo on Pexels (e.g. 'arduino circuit', 'electronics board', 'soldering microchip', 'robot electronics')."
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

def fetch_pexels_and_host_image(query, used_photo_ids):
    headers = {"Authorization": PEXELS_API_KEY}
    queries_to_try = [query] + random.sample(FALLBACK_QUERIES, len(FALLBACK_QUERIES))

    selected_photo = None
    for q in queries_to_try:
        print(f"Searching Pexels for: '{q}'...")
        params = {
            "query": q,
            "orientation": "portrait",
            "per_page": 30,
            "page": random.randint(1, 3)
        }
        res = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=30)
        if not res.ok:
            print(f"Pexels API error ({res.status_code}):", res.text)
            continue

        photos = res.json().get("photos", [])
        unused_photos = [p for p in photos if p["id"] not in used_photo_ids]
        if unused_photos:
            selected_photo = random.choice(unused_photos)
            break

    if not selected_photo:
        raise Exception("No unused Pexels photos found!")

    photo_id = selected_photo["id"]
    photo_url = selected_photo["src"].get("portrait") or selected_photo["src"].get("large2x")
    print(f"Selected Pexels Photo ID: {photo_id}")

    img_res = requests.get(photo_url, timeout=60)
    img_res.raise_for_status()
    with open("pin.jpg", "wb") as f:
        f.write(img_res.content)

    print("Uploading image to Cloudinary...")
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)
    upload_res = cloudinary.uploader.upload("pin.jpg", folder="pinterest_pins")
    direct_url = upload_res["secure_url"]
    print("Direct Image URL:", direct_url)
    return direct_url, photo_id

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
    project = generate_project_idea(history["projects"])
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
    direct_image_url, photo_id = fetch_pexels_and_host_image(
        project.get("pexels_query", "arduino circuit board"),
        history["photo_ids"]
    )

    if publish_to_buffer(project["title"], full_pin_text, direct_image_url, board_id):
        history["projects"].append(project["title"])
        history["photo_ids"].append(photo_id)
        save_history(history)
        print("Project & Photo ID saved to history.json!")
    else:
        raise Exception("Failed to publish to Buffer, history not updated.")
