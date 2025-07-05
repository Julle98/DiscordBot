import requests
from io import BytesIO
from discord import File
import os

HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")

async def suorita_kuvagenerointi(prompt: str) -> File:
    try:
        response = requests.post(
            "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2",
            headers={"Authorization": HUGGINGFACE_API_TOKEN},
            json={"inputs": prompt}
        )
        response.raise_for_status()
        image_bytes = response.content
        return File(BytesIO(image_bytes), filename="kuva.png")
    except Exception as e:
        raise RuntimeError(f"Kuvan generointi epäonnistui: {e}")
