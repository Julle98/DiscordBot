import discord

FAQ_DATA = {
    "yleinen": {
        "title": "ℹ️ Yleinen tieto",
        "description": "Tämä botti tarjoaa monipuolisia toimintoja yhteisön arjen helpottamiseksi. Voit käyttää komentoja ja ominaisuuksia eri tarkoituksiin. Paremmin saat tietoa kaikesta mitä botti tarjoaa käyttämällä /komennot komentoa.",
        "color": discord.Color.blue()
    },
    "moderointi": {
        "title": "🛡️ Moderointi",
        "description": "Botti tukee moderointia: warn, mute, kick, ban. Jokainen tapahtuma tallennetaan lokiin. Moderaattorit voivat käyttää näitä komentoja pitääkseen yhteisön turvallisena.",
        "color": discord.Color.red()
    },
    "gdpr": {
        "title": "📜 GDPR & tietosuoja",
        "description": "Käyttäjä voi nähdä, ladata ja poistaa omat tietonsa. Kaikki toiminnot noudattavat GDPR:ää. Katso omat tietosi /tiedot komennolla.",
        "color": discord.Color.green()
    },
    "fun": {
        "title": "📲 Komennot",
        "description": "Pystyt käyttämään Esim. hauskoja komentoja, kuten /meemi, /vitsi ja muita viihdyttäviä toimintoja. Sekä hyöhdyllisiä, kuten /ruoka, /sää, /ruokailuvuorot, /kalenteri jne. Kokeile /komennot nähdäksesi kaikki viihdekomennot ja kaikki muutkin komennot.",
        "color": discord.Color.purple()
    },
    "xp": {
        "title": "⭐ XP systeemi",
        "description": "Botti palkitsee aktiivisuudesta XP-pisteillä. Pisteet kertyvät viesteistä, puhekanavalta ja komentojen käytöstä. Kerää pisteitä ja nouse eri tasoille! Jokaisella tasolla uniikkeja etuja. Tarkista tasosi /taso komennolla. Samalla voit nähdä muut edut tasoista <#1339855946759016519> kanavalla.",
        "color": discord.Color.gold()
    },
    "kehitys": {
        "title": "⚙️ Kehitys",
        "description": "Botti on jatkuvassa kehityksessä. Uusia ominaisuuksia lisätään ja bugit korjataan säännöllisesti. Pysyt ajan tasalla seuraamalla <#1395025181310849084> kanavaa, jossa ilmoitetaan päivityksistä ja uusista ominaisuuksista. Voit myös ehdottaa uusia ominaisuuksia tai raportoida ongelmia ottamalla yhteyttä ylläpitoon.",
        "color": discord.Color.orange()
    },
    "yhteydenotto": {
        "title": "📬 Yhteydenotto",
        "description": "Jos sinulla on kysyttävää tai ehdotuksia, ota yhteyttä ylläpitoon tai käytä /help komentoa. Mikä tahansa kanavakin käy, mutta suosittelemme käyttämään yksityisviestejä selkeyden vuoksi.",
        "color": discord.Color.teal()
    },
    "tilastot": {
        "title": "📊 Tilastot & Ranking",
        "description": "Näet omat XP pisteesi, aktiivisuustilastot ja sijoitukset /tiedot komennossa. Myöskin /taso komento on hyödyllinen nähdäksesi oman tason ja edut. Kilpaile muiden kanssa ja nouse sijoituksissa aktiivisuudellasi!",
        "color": discord.Color.dark_blue()
    },
    "integraatiot": {
        "title": "🧩 Integraatiot",
        "description": "Botti tukee integraatioita esim. Tilun lukuvuosikalenteria Google Calendarin kanssa. Voit tarkistaa tulevia tapahtumia ja muistutuksia suoraan botin kautta /kalenteri komennolla.",
        "color": discord.Color.dark_magenta()
    },
    "vinkit": {
        "title": "💡 Vinkit parhaaseen käyttöön",
        "description": "Kokeile kaikkea botin tarjoamia komentoja ja ominaisuuksia. Käytä /komennot nähdäksesi kaikki mahdollisuudet. Pidä botti ajan tasalla ja osallistu aktiivisesti yhteisöön saadaksesi parhaan kokemuksen.",
        "color": discord.Color.light_grey()
    }
}

def get_embed(key: str) -> discord.Embed:
    data = FAQ_DATA.get(key)
    if not data:
        return discord.Embed(title="❓ Tuntematon aihe", description="Tätä aihetta ei löytynyt.", color=discord.Color.greyple())
    return discord.Embed(title=data["title"], description=data["description"], color=data["color"])