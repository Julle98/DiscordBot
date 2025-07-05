from transformers import pipeline

kaantaja = pipeline("translation", model="Helsinki-NLP/opus-mt-fi-en")

async def suorita_kaannos(teksti: str) -> str:
    try:
        tulos = kaantaja(teksti)
        return tulos[0]["translation_text"]
    except Exception as e:
        return f"Virhe käännöksessä: {e}"
