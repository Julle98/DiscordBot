import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
LANGSEARCH_API_KEY = os.getenv("LANGSEARCH_API_KEY")

async def suorita_haku(kysely: str) -> str:
    try:
        headers = {
            "Authorization": f"Bearer {LANGSEARCH_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "query": kysely,
            "lang": "fi",
            "summary": True,
            "count": 3
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.langsearch.com/v1/web-search",
                headers=headers,
                json=data
            ) as response:
                if response.status != 200:
                    return f"⚠️ Haku epäonnistui (status {response.status})"

                json_response = await response.json()

                if "data" in json_response and "webPages" in json_response["data"]:
                    tulokset = json_response["data"]["webPages"]["value"]
                    if not tulokset:
                        return "🔍 Ei löytynyt tuloksia."

                    vastaus = ""
                    for i, tulos in enumerate(tulokset, start=1):
                        otsikko = tulos.get("name", "Ei otsikkoa")
                        url = tulos.get("url", "")
                        yhteenveto = tulos.get("summary", "")
                        vastaus += f"**{i}. [{otsikko}]({url})**\n{yhteenveto}\n\n"

                    return vastaus.strip()

                return "🤷‍♂️ Ei löytynyt vastauksia."

    except Exception as e:
        return f"🚫 Virhe haussa: {e}"
