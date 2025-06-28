import requests

def generate_image(prompt: str):
    response = requests.post("http://127.0.0.1:7860/sdapi/v1/txt2img", json={
        "prompt": prompt,
        "steps": 20
    })
    img_data = response.json()["images"][0]
    with open("output.png", "wb") as f:
        f.write(bytes.fromhex(img_data))
