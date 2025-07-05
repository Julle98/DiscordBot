import base64
import requests

def generate_image(prompt: str):
    response = requests.post("http://127.0.0.1:7860/sdapi/v1/txt2img", json={
        "prompt": prompt,
        "steps": 20
    })
    img_data = response.json()["images"][0]
    image_bytes = base64.b64decode(img_data)
    with open("output.png", "wb") as f:
        f.write(image_bytes)
