import re
import json
import requests
import os

LINK_ID_FILE = "./data/drive_link_id.txt"

def get_drive_file_id(url: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None

def paivita_ruokailuvuorot_json():
    drive_url = os.getenv("RUOKAILU_DRIVE_LINK")
    if not drive_url:
        print("Drive-linkkiä ei löytynyt .env-tiedostosta.")
        return

    file_id = get_drive_file_id(drive_url)
    if not file_id:
        print("Virheellinen Drive-linkki.")
        return

    previous_id = None
    if os.path.exists(LINK_ID_FILE):
        with open(LINK_ID_FILE, "r") as f:
            previous_id = f.read().strip()

    if previous_id == file_id:
        print("Drive-linkki ei ole muuttunut. Ei päivitetä.")
        return

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        response = requests.get(download_url)
        response.raise_for_status()
        text = response.text
    except Exception as e:
        print(f"Virhe ladattaessa tiedostoa: {e}")
        return

    vuoro_pattern = re.compile(r"(\d\. VUORO)\n([\d:. -]+ Ruokailu)\n([\d:. -]+ Oppitunti)", re.MULTILINE)
    code_pattern = re.compile(r"\b[A-ZÄÖ]{2,}[0-9]{2,}(?:\+[A-Z0-9.]+)?(?:\.[0-9]+)?\b")

    vuorot = [(m.group(1), m.group(2), m.group(3), m.end()) for m in vuoro_pattern.finditer(text)]
    schedule = {}

    for i, (vuoro, ruokailu, oppitunti, end_pos) in enumerate(vuorot):
        next_start = vuorot[i + 1][3] if i + 1 < len(vuorot) else len(text)
        block_text = text[end_pos:next_start]
        codes = code_pattern.findall(block_text)

        for code in codes:
            schedule[code] = {
                "vuoro": vuoro,
                "ruokailu": ruokailu,
                "oppitunti": oppitunti
            }

    json_path = os.getenv("SCHEDULE_JSON_PATH", "./data/ruokailuvuorot.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
        with open(LINK_ID_FILE, "w") as f:
            f.write(file_id)
        print(f"Päivitetty {len(schedule)} tuntikoodia tiedostoon.")
    except Exception as e:
        print(f"Virhe tallennettaessa tiedostoa: {e}")
