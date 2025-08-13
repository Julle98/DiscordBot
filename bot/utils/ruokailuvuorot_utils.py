import re
import json
import os
import gdown
import hashlib

def get_drive_file_id(url_or_id: str) -> str:
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", url_or_id):
        return url_or_id
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url_or_id)
    return match.group(1) if match else None

def laske_tiedoston_hash(polku: str) -> str:
    try:
        with open(polku, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return None

def parse_schedule(text: str) -> dict:
    schedule = {}
    lines = text.strip().split("\n")

    current_vuoro = None
    current_ruokailu = None
    current_oppitunti = None

    for line in lines:
        line = line.strip()

        if re.match(r"^\d+\. VUORO$", line):
            current_vuoro = line
            current_ruokailu = None
            current_oppitunti = None

        elif "Ruokailu" in line:
            match = re.search(r"(\d{1,2}\.\d{2} - \d{1,2}\.\d{2}) Oppitunti (\d{1,2}\.\d{2} - \d{1,2}\.\d{2}) Ruokailu", line)
            if match:
                current_oppitunti = match.group(1)
                current_ruokailu = match.group(2)
                continue

            match = re.search(r"(\d{1,2}\.\d{2} -) Ruokailu", line)
            if match:
                current_ruokailu = match.group(1).strip()
                current_oppitunti = None
                continue

            match = re.search(r"(\d{1,2}\.\d{2} - \d{1,2}\.\d{2}) Ruokailu (\d{1,2}\.\d{2} - \d{1,2}\.\d{2}) Oppitunti", line)
            if match:
                current_ruokailu = match.group(1)
                current_oppitunti = match.group(2)
                continue

        elif re.match(r"\b[A-ZÄÖ]{2,}[0-9]{2,}(?:\+[A-Z0-9.]+)?(?:\.[0-9]+)?\b", line):
            codes = re.findall(r"\b[A-ZÄÖ]{2,}[0-9]{2,}(?:\+[A-Z0-9.]+)?(?:\.[0-9]+)?\b", line)
            for code in codes:
                schedule[code] = {
                    "vuoro": current_vuoro,
                    "ruokailu": current_ruokailu,
                    "oppitunti": current_oppitunti
                }

    return schedule

def paivita_ruokailuvuorot():
    drive_url = os.getenv("RUOKAILU_DRIVE_LINK")
    raw_path = os.getenv("RAW_SCHEDULE_PATH")
    hash_path = os.getenv("LINK_ID_FILE")

    if not drive_url:
        print("Drive-linkkiä ei löytynyt .env-tiedostosta.")
        return

    file_id = get_drive_file_id(drive_url)
    if not file_id:
        print("Virheellinen Drive-linkki.")
        return

    download_url = f"https://drive.google.com/uc?id={file_id}"

    try:
        gdown.download(url=download_url, output=raw_path, quiet=False, use_cookies=False)
    except Exception as e:
        print(f"Virhe ladattaessa tiedostoa: {e}")
        return

    new_hash = laske_tiedoston_hash(raw_path)
    previous_hash = None
    if os.path.exists(hash_path):
        with open(hash_path, "r") as f:
            previous_hash = f.read().strip()

    if previous_hash == new_hash:
        print("Tiedosto ei ole muuttunut. Ei päivitetä.")
        return

    try:
        with open(raw_path, "r", encoding="utf-8") as f:
            text = f.read()
        print("Tiedosto ladattu ja päivitetty.")
        print(f"Tiedoston koko: {len(text)} merkkiä")
    except Exception as e:
        print(f"Virhe luettaessa ladattua tiedostoa: {e}")
        return

    try:
        with open(hash_path, "w") as f:
            f.write(new_hash)
        print("Hash tallennettu.")
    except Exception as e:
        print(f"Virhe tallennettaessa hashia: {e}")