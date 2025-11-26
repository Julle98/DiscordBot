import re
import json
import os
import gdown
import hashlib
import chardet
from datetime import datetime
import discord 
from discord import app_commands

def lue_tiedosto_turvallisesti(polku: str) -> str:
    try:
        with open(polku, "rb") as f:
            raw_bytes = f.read()
            detected = chardet.detect(raw_bytes)
            encoding = detected["encoding"] or "utf-8"
            return raw_bytes.decode(encoding, errors="replace")
    except Exception as e:
        return f"📛 Virhe tiedoston lukemisessa: {e}"

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

    weekdays = ["MAANANTAI", "TIISTAI", "KESKIVIIKKO", "TORSTAI", "PERJANTAI"]
    current_weekday = None
    current_vuoro = None
    current_ruokailu = None
    current_oppitunti = None
    current_palkki = None

    for line in lines:
        line = line.strip()

        if line in weekdays:
            current_weekday = line
            continue

        if re.match(r"^\d+\.\s*PALKKI$", line):
            current_palkki = line
            continue

        if re.match(r"^\d+\. VUORO$", line):
            current_vuoro = line
            current_ruokailu = None
            current_oppitunti = None
            continue

        m_opp = re.search(r"(\d{1,2}\.\d{2}\s*-\s*\d{1,2}\.\d{2}).*Oppitunti", line)
        m_ruoka = re.search(r"(\d{1,2}\.\d{2}\s*-\s*\d{1,2}\.\d{2}).*Ruokailu", line)

        if m_opp:
            current_oppitunti = m_opp.group(1)
        if m_ruoka:
            current_ruokailu = m_ruoka.group(1)

        possible = re.findall(r"\b[A-Za-zÅÄÖåäö]+[0-9][A-Za-zÅÄÖåäö0-9.+]*\b", line)
        codes = [c for c in possible if not re.match(r"^\d", c)]

        if codes and current_weekday and current_vuoro:
            for code in codes:
                code = code.strip().upper()
                if code not in schedule:
                    schedule[code] = {}
                schedule[code][current_weekday] = {
                    "palkki": current_palkki,
                    "vuoro": current_vuoro,
                    "ruokailu": current_ruokailu,
                    "oppitunti": current_oppitunti
                }

    return schedule

async def ruokailuvuorot_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    raw_path = os.getenv("RAW_SCHEDULE_PATH")
    text = lue_tiedosto_turvallisesti(raw_path)
    if text.startswith("📛 Virhe"):
        return []

    schedule = parse_schedule(text)

    weekdays = ["MAANANTAI", "TIISTAI", "KESKIVIIKKO", "TORSTAI", "PERJANTAI"]
    weekday = weekdays[datetime.today().weekday()] if datetime.today().weekday() < 5 else "MAANANTAI"

    ehdotukset = [
        app_commands.Choice(name=code, value=code)
        for code in schedule
        if weekday in schedule[code] and current.upper() in code
    ]

    return ehdotukset[:25]

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