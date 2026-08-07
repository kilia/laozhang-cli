import base64
import mimetypes

import requests

# Configuration
API_KEY = "sk-YOUR_API_KEY"  # Replace with your API Key
API_URL = "https://api2.laozhang.ai/v1beta/models/gemini-3-pro-image:generateContent"

# Request headers
headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Build request payload
# Read and encode reference image


def encode_image(image_path):
    mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return {"mime_type": mime_type, "data": data}


# Reference image 1 (replace with your image path)
ref_image_1 = encode_image("image_1.jpg")
# Reference image 2 (replace with your image path)
ref_image_2 = encode_image("image_2.jpg")

payload = {
    "contents": [
        {
            "parts": [
                {"text": "以图1的内容为准按照图2的排列生成一组新图片"},
                {"inline_data": ref_image_1},
                {"inline_data": ref_image_2},
            ]
        }
    ],
    "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"imageSize": "2K"}},
}

# Send request
print("Generating image...")
response = requests.post(API_URL, headers=headers, json=payload, timeout=180)

if response.status_code != 200:
    print(f"Error: {response.status_code} - {response.text}")
    exit(1)

# Extract and save image
result = response.json()

image_part = None
for candidate in result.get("candidates", []):
    for part in candidate.get("content", {}).get("parts", []):
        inline_data = part.get("inlineData") or part.get("inline_data")
        if inline_data and inline_data.get("data"):
            image_part = inline_data
            break
    if image_part:
        break

if not image_part:
    print("No image data in response")
    print(result)
    exit(1)

mime_type = image_part.get("mimeType") or image_part.get("mime_type") or "image/png"
extension = "jpg" if mime_type == "image/jpeg" else "webp" if mime_type == "image/webp" else "png"
output_path = f"output.{extension}"

with open(output_path, "wb") as f:
    image_data = image_part["data"]
    f.write(base64.b64decode(image_data))

print(f"✅ Image saved: {output_path}")
