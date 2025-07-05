import re

def tulkitse_tekoalykieli(kysymys: str):
    kysymys = kysymys.strip().lower()

    komentokartta = {
        "HAE": ["hae", "etsi", "etsi tietoa", "selvitä"],
        "KYSY": ["kysy", "kerro", "mikä on", "mitä tarkoittaa"],
        "GENEROI": ["generoi", "luo kuva", "piirrä", "tee kuva"],
        "TIIVISTÄ": ["tiivistä", "lyhennä", "yhteenveto"],
        "KÄÄNNÄ": ["käännä", "translate", "muuta kielelle"]
    }

    for komento, avainsanat in komentokartta.items():
        for sana in avainsanat:
            if kysymys.startswith(sana):
                argumentti = kysymys[len(sana):].strip()
                return komento, argumentti

    raise ValueError("Komentoa ei tunnistettu. Käytä esim. 'KYSY mikä on tekoäly?'")
