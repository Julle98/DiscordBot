from transformers import pipeline

tiivistaja = pipeline("summarization", model="facebook/mbart-large-cc25")

async def suorita_tiivistys(teksti: str) -> str:
    try:
        if len(teksti.split()) < 10:
            return "Teksti on liian lyhyt tiivistettäväksi."

        tulos = tiivistaja(teksti, max_length=100, min_length=30, do_sample=False)
        return tulos[0]["summary_text"]
    except Exception as e:
        return f"Virhe tiivistyksessä: {e}"
