import base64
import mimetypes

import requests

# Configuration
API_KEY = "sk-YOUR_API_KEY"  # Replace with your API Key
API_URL = "https://api2.laozhang.ai/v1/images/edits"

# Request headers
headers = {"Authorization": f"Bearer {API_KEY}"}

# Edit request
data = {
    "model": "gpt-image-2-vip",
    "prompt": "以图1的内容为准按照图2的排列生成一组新图片",
    "size": "2048x2048",
    "quality": "high",
}

opened_files = []
files = []
image_1_path = "image_1.jpg"  # Replace with your reference image path
image_1_mime = mimetypes.guess_type(image_1_path)[0] or "image/jpeg"
image_1_file = open(image_1_path, "rb")
opened_files.append(image_1_file)
files.append(("image", (image_1_path, image_1_file, image_1_mime)))
image_2_path = "image_2.jpg"  # Replace with your reference image path
image_2_mime = mimetypes.guess_type(image_2_path)[0] or "image/jpeg"
image_2_file = open(image_2_path, "rb")
opened_files.append(image_2_file)
files.append(("image", (image_2_path, image_2_file, image_2_mime)))

try:
    print("Editing image...")
    response = requests.post(API_URL, headers=headers, data=data, files=files, timeout=180)
finally:
    for file in opened_files:
        file.close()

if response.status_code != 200:
    print(f"Error: {response.status_code} - {response.text}")
    exit(1)

result = response.json()
image_base64 = result.get("data", [{}])[0].get("b64_json")
image_url = result.get("data", [{}])[0].get("url")

if not image_base64 and image_url:
    image_response = requests.get(image_url, timeout=60)
    image_response.raise_for_status()
    image_base64 = base64.b64encode(image_response.content).decode("utf-8")

if not image_base64:
    print("No image data in response")
    print(result)
    exit(1)

with open("output.png", "wb") as f:
    f.write(base64.b64decode(image_base64))

print("Image saved: output.png")
