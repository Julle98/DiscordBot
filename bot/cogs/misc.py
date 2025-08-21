import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import pytz
import requests
import random
from discord.ui import Modal
import re
import math
import asyncio
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event
from bot.utils.error_handler import CommandErrorHandler
from discord.ui import View, Button
from discord import ButtonStyle, Embed

UTC_CITIES = {
    -12: "Baker Island",
    -11: "Pago Pago",
    -10: "Honolulu",
    -9: "Anchorage",
    -8: "Los Angeles",
    -7: "Denver",
    -6: "Mexico City",
    -5: "New York",
    -4: "Santiago",
    -3: "Buenos Aires",
    -2: "South Georgia",
    -1: "Azores",
    0: "London",
    1: "Berlin",
    2: "Helsinki",
    3: "Moscow",
    4: "Dubai",
    5: "Karachi",
    6: "Dhaka",
    7: "Bangkok",
    8: "Beijing",
    9: "Tokyo",
    10: "Sydney",
    11: "Nouméa",
    12: "Auckland",
    13: "Samoa",
    14: "Kiritimati"
}

class AikaModal(discord.ui.Modal, title="Aikakysely"):
    kysymys = discord.ui.TextInput(label="UTC aika? (Esim. 2, -5, 0, 3)", placeholder="Kirjoita UTC aika", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.kysymys.value.strip()
        try:
            offset = int(user_input)
            timezone = pytz.FixedOffset(offset * 60)
            city = UTC_CITIES.get(offset, "Tuntematon kaupunki")
        except:
            timezone = pytz.timezone("Europe/Helsinki")
            city = "Helsinki"
        time = datetime.now(timezone).strftime("%H:%M:%S")
        await interaction.response.send_message(f"Kello on nyt **{time}** kaupungissa **{city}** (UTC {offset:+d})")

async def calculate_steps(lasku_parsittu, selitys):
    steps = []
    lasku_vaiheessa = lasku_parsittu

    while "(" in lasku_vaiheessa or "**" in lasku_vaiheessa or "math.sqrt" in lasku_vaiheessa:
        while "(" in lasku_vaiheessa:
            bracket_match = re.search(r'\(([^()]+)\)', lasku_vaiheessa)
            if bracket_match:
                inner_expression = bracket_match.group(1)
                result = eval(inner_expression, {"__builtins__": None, "math": math})
                lasku_vaiheessa = lasku_vaiheessa.replace(f"({inner_expression})", str(result), 1)
                steps.append(f"Laskettiin sulkeet: ({inner_expression}) = {result}")

        while "**" in lasku_vaiheessa:
            power_match = re.search(r'(\d+)\s*\*\*\s*(\d+)', lasku_vaiheessa)
            if power_match:
                base, exponent = power_match.groups()
                result = math.pow(float(base), float(exponent))
                lasku_vaiheessa = lasku_vaiheessa.replace(f"{base}**{exponent}", str(result), 1)
                steps.append(f"Laskettiin potenssi: {base}**{exponent} = {result}")

        while "math.sqrt" in lasku_vaiheessa:
            sqrt_match = re.search(r'math\.sqrt\((\d+)\)', lasku_vaiheessa)
            if sqrt_match:
                value = sqrt_match.group(1)
                result = math.sqrt(float(value))
                lasku_vaiheessa = lasku_vaiheessa.replace(f"math.sqrt({value})", str(result), 1)
                steps.append(f"Laskettiin neliöjuuri: math.sqrt({value}) = {result}")

    tulos = eval(lasku_vaiheessa, {"__builtins__": None, "math": math})
    steps.append(f"Laskun lopputulos: {tulos}")

    if selitys.lower() in ["kyllä", "kylla", "yes"]:
        return f"Lasku: `{lasku_parsittu}`\nTulos: **{tulos}**\nSelitys:\n" + "\n".join(steps)
    else:
        return f"Lasku: `{lasku_parsittu}`\nTulos: **{tulos}**"

def latex_to_python(expr: str) -> str:
    expr = expr.replace(" ", "")

    expr = expr.replace(r"\cdot", "*")
    expr = expr.replace(r"\times", "*")

    expr = expr.replace(r"\div", "/")

    expr = re.sub(r'\\sqrt{([^{}]+)}', r'math.sqrt(\1)', expr)
    expr = re.sub(
        r"""\\sqrt
        

\[(\d+)\]


        {([^{}]+)}""",
        r"math.pow(\2, 1/\1)",
        expr,
        flags=re.VERBOSE
    )

    expr = re.sub(r'\\frac{([^{}]+)}{([^{}]+)}', r'(\1/\2)', expr)

    expr = re.sub(r'(\d+)\^\{([^{}]+)\}', r'\1**(\2)', expr)
    expr = re.sub(r'(\d+)\^(\d+)', r'\1**\2', expr)

    expr = re.sub(r'\\sin\(([^()]+)\)', r'math.sin(\1)', expr)
    expr = re.sub(r'\\cos\(([^()]+)\)', r'math.cos(\1)', expr)
    expr = re.sub(r'\\tan\(([^()]+)\)', r'math.tan(\1)', expr)

    expr = re.sub(r'\\exp\(([^()]+)\)', r'math.exp(\1)', expr)

    return expr

ajastin_aktiiviset = {}

async def ajastin_odotus(interaction: discord.Interaction, sekunnit: int):
    try:
        await asyncio.sleep(sekunnit)
        await interaction.user.send(f"Hei {interaction.user.mention}, aikasi on kulunut!")
    except asyncio.CancelledError:
        try:
            await interaction.user.send("Ajastimesi keskeytettiin, koska botti sammutettiin.")
        except discord.Forbidden:
            pass

lomapaivat = {
    datetime(2025, 1, 1): "Uudenvuodenpäivä",
    datetime(2025, 1, 6): "Loppiainen",
    datetime(2025, 4, 18): "Pitkäperjantai",
    datetime(2025, 4, 20): "Pääsiäispäivä",
    datetime(2025, 4, 21): "Toinen pääsiäispäivä",
    datetime(2025, 5, 1): "Vapunpäivä",
    datetime(2025, 5, 18): "Helluntaipäivä",
    datetime(2025, 6, 21): "Juhannuspäivä",
    datetime(2025, 11, 1): "Pyhäinpäivä",
    datetime(2025, 12, 6): "Itsenäisyyspäivä",
    datetime(2025, 12, 25): "Joulupäivä",
    datetime(2025, 12, 26): "Tapaninpäivä",
    datetime(2025, 10, 13): "Syysloma alkaa",
    datetime(2025, 10, 17): "Syysloma päättyy",
    datetime(2025, 12, 22): "Joululoma alkaa",
    datetime(2026, 1, 6): "Joululoma päättyy",
    datetime(2026, 2, 16): "Talviloma alkaa",
    datetime(2026, 2, 20): "Talviloma päättyy"
}

meme_urls = [
    "https://cdn.discordapp.com/attachments/1345757292469157899/1359196202670887082/Screenshot_20240623_123654_X.jpg",
    "https://cdn.discordapp.com/attachments/1339859287739994112/1357396501357138162/Nayttokuva_2024-12-21_154031.png",
    "https://cdn.discordapp.com/attachments/1339859287739994112/1345778294934732953/QEnsrCsL-rswDyJ1bwqG8899LWKYgRoJGLDs5X042uA.webp",
    "https://tenor.com/view/xqc-arabfunny-arabic-saudi-arabia-projared-gif-18306091",
    "https://tenor.com/view/white-woman-jumpscare-fnaf-security-breach-security-breach-vanessa-white-woman-gif-24205880",
    "https://imgur.com/gallery/apple-pay-mLeN2RK",
    "https://tenor.com/view/nalog-gif-25906765",
    "https://tenor.com/view/foss-no-bitches-no-hoes-0bitches-no-gif-24529727",
    "https://tenor.com/view/flashbang-scran-gif-24856116",
    "https://media.discordapp.net/attachments/1126787140450258965/1185281224105803908/l0ft70gpry411.gif",
    "https://cdn.discordapp.com/attachments/1339846062281588777/1365359507546439861/niggawizard.png?ex=680d05a1&is=680bb421&hm=4350e5d43b4d3ffe8403ae0c035eb0b719d0fc4974012d00c25145f197bd2b50&",
    "https://cdn.discordapp.com/attachments/1345757292469157899/1366454743299260656/what-happened-here-v0-jwrupykb1bve1.webp?ex=681101a6&is=680fb026&hm=30eb96f246a9bcb1eb128058dfbad966c6a8d9998c427f4161bb45a293f4c532&",
    "https://cdn.discordapp.com/attachments/1345757292469157899/1366454826753589339/post-minecraft-movie-v0-yl1kqwo4e8we1.webp?ex=681101ba&is=680fb03a&hm=66222829db697cc7df413d6d3815f48c26c67226aab38d981d8982eeac661a3e&",
    "https://cdn.discordapp.com/attachments/1345757292469157899/1366454826287894721/ronald-crash-out-v0-he22opx91bve1.webp?ex=681101ba&is=680fb03a&hm=efc97669dba1aa51dcf47635a72e366e04f89a5f1955ce0f2594d806cf2d4006&",
    "https://cdn.discordapp.com/attachments/1345757292469157899/1366454745149083729/what-did-he-do-to-deserve-this-v0-4saxnd7dypue1.webp?ex=681101a6&is=680fb026&hm=fc895319cdd5fd4d5922d560697aa227db39c51e7cadc9973dfc2894e1a4862f&",
    "https://cdn.discordapp.com/attachments/1345757292469157899/1366454742032580711/due-to-the-rich-destroying-our-resources-steve-resulted-to-v0-zb5imkjtd4xe1.webp?ex=681101a6&is=680fb026&hm=e1884e0974f4ed02ead025210947e70359ae7241a15f28be37a6a32d5dc7a423&",
    "https://cdn.discordapp.com/attachments/1345757292469157899/1366454745644138516/would-you-open-the-door-v0-ayry3e2qdvue1.webp?ex=681101a6&is=680fb026&hm=7a57d67513a49008f42040325f51c8606391fe576396a5b0f44be8989931c8d2&",
    "https://cdn.discordapp.com/attachments/1345757292469157899/1366454746184941578/whopper-whopper-v0-i0o8s9v3r3ve1.webp?ex=681101a6&is=680fb026&hm=bd42a7f8bb4e796b3c2377a3f564f6fe3f483e1c94785a309981af965e9a6223&",
    "https://cdn.discordapp.com/attachments/1345757292469157899/1366454827210637363/what-did-she-eat-v0-pi5pa531l2ue1.webp?ex=681101ba&is=680fb03a&hm=2fd6d0c67ffada8d024d5a5f6b92ecc99236b91855d7d9cbe19c974c31a71de3&",
    "https://cdn.discordapp.com/attachments/1345757292469157899/1366454827768479824/zwntbleyk2ve1.webp?ex=681101ba&is=680fb03a&hm=6789a93a71f612d32a8378705f1fcb2440e9e971b527783ad503186936ab5fdd&",
    "https://cdn.discordapp.com/attachments/1345757292469157899/1372593521625927761/image.png?ex=682756d5&is=68260555&hm=1fcd5d5ee0c89bde02a989e2a7e7d6767e6e96cf8f74b54483888e1c518788e3&"
]

last_meme_url = None  

general_jokes = [
    "Miksi kana ylitti tien? Päästäkseen toiselle puolelle!",
    "Mitä tapahtuu, kun norsu astuu muurahaispesään? Muurahaiset muuttavat.",
    "Miksi banaani meni lääkäriin? Koska se ei kuorinut hyvin.",
    "Mitä kello sanoi toiselle kellolle? 'Tule mukaan, mennään ajassa!'",
    "Miksi kirahvilla ei ole salaisuuksia? Koska kaikki näkee sen kaulan yli.",
    "Miksi leipä ei voinut mennä kouluun? Se oli jo viipaloitu.",
    "Mitä tapahtuu, kun laittaa kellon uuniin? Aika lentää.",
    "Miksi lumiukko meni rannalle? Se halusi sulaa pois stressistä.",
    "Miksi kala ei käy netissä? Se pelkää verkkoja.",
    "Miksi kirja oli surullinen? Koska sillä oli liian monta lukua.",
    "Miksi tietokone meni kahvilaan? Se tarvitsi vähän kahvia ja päivityksen.",
    "Miksi appelsiini pysähtyi? Se oli mehukas tilanne.",
    "Miksi kengät eivät koskaan valehtele? Koska ne seuraavat aina oikeaa polkua.",
    "Miksi puhelin ei vastannut? Se oli lentotilassa.",
    "Miksi lamppu ei toiminut? Se oli valaistunut liikaa.",
    "Miksi kissa ei osaa käyttää tietokonetta? Koska se painaa aina hiirtä.",
    "Miksi jääkaappi on hyvä ystävä? Se ei koskaan petä – se pysyy viileänä.",
    "Miksi kirahvi ei pelaa piilosta? Se jää aina kiinni.",
    "Miksi sieni oli juhlien tähti? Koska se oli fun guy (fungi)!"
]

class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="aika", description="Näytä nykyinen aika haluamassasi UTC-ajassa.")
    @app_commands.checks.has_role("24G")
    async def aika(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AikaModal())
        try:
            await kirjaa_komento_lokiin(self.bot, interaction, "/aika")
            await kirjaa_ga_event(self.bot, interaction.user.id, "aika_komento")
        except Exception as e:
            await interaction.response.send_message(f"Virhe: {e}", ephemeral=True)

    @app_commands.command(name="moikka", description="Moikkaa takaisin.")
    async def moikka(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/moikka")
        await kirjaa_ga_event(self.bot, interaction.user.id, "moikka_komento")
        await interaction.response.send_message("Moikka!")

    @app_commands.command(name="esittely", description="Sannamaijan esittely.")
    @app_commands.checks.has_role("24G")
    async def esittely(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/esittely")
        await kirjaa_ga_event(self.bot, interaction.user.id, "esittely_komento")

        embed = Embed(
            title="✨ Hei, olen Sannamaija Pyrrö!",
            description=(
                "Olen tämän palvelimen oma botti, joka auttaa sinua XP-järjestelmässä, moderoinnissa, tapahtumissa ja paljon muussakin! Jos et ole varma komennoista, kokeile ``/komennot``. Sieltä saat hyvin tietoa.\n\n"
                "Alta löydät hyödyllisiä linkkejä:"
            ),
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1339916663344074782/1391362772729725028/unnamed.png?ex=686b9f0f&is=686a4d8f&hm=3c31051a0ed55f2ee253f8eed83064bd367b1ebcebadd0d217051beb1877aaaa&")  
        embed.set_footer(text="Sannamaija • Tehty 24G ryhmäläisille ❤️")

        view = View()
        view.add_item(Button(label="🌐 Viralliset sivut", url="https://sites.google.com/view/sannamaijadiscordbot/", style=ButtonStyle.link))
        view.add_item(Button(label="📜 Käyttöehdot", url="https://sites.google.com/view/sannamaijadiscordbot/t%C3%A4rke%C3%A4%C3%A4/k%C3%A4ytt%C3%B6ehdot?authuser=0", style=ButtonStyle.link))
        view.add_item(Button(label="🔒 Tietosuojakäytäntö", url="https://sites.google.com/view/sannamaijadiscordbot/t%C3%A4rke%C3%A4%C3%A4/tietosuojak%C3%A4yt%C3%A4nt%C3%B6?authuser=0", style=ButtonStyle.link))
        view.add_item(Button(label="📘 Säännöt", url="https://sites.google.com/view/sannamaijadiscordbot/t%C3%A4rke%C3%A4%C3%A4/s%C3%A4%C3%A4nn%C3%B6t?authuser=0", style=ButtonStyle.link))
        view.add_item(Button(label="🛠️ Kehitysprosessi", url="https://trello.com/b/hVY1U881", style=ButtonStyle.link))

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="nofal", description="Sannamaijan mielipide Nofalista.")
    @app_commands.checks.has_role("24G")
    @app_commands.describe(mielipide="Valitse mielipide")
    @app_commands.choices(
        mielipide=[
            app_commands.Choice(name="Myönteinen", value="positiivinen"),
            app_commands.Choice(name="Kielteinen", value="negatiivinen"),
            app_commands.Choice(name="Nofal itse", value="nofal")
        ]
    )
    async def nofal(self, interaction: discord.Interaction, mielipide: app_commands.Choice[str]):
        await kirjaa_komento_lokiin(self.bot, interaction, "/nofal")
        await kirjaa_ga_event(self.bot, interaction.user.id, "nofal_komento")
        if mielipide.value == "positiivinen":
            teksti = "Minun lempioppilaani. Hän on aina ystävällinen ja auttaa muita. Nofal on loistava esimerkki siitä, miten oppilas voi olla aktiivinen ja positiivinen jäsen yhteisössä!"
        elif mielipide.value == "negatiivinen":
            teksti = "En ole ihan varma Nofalista. Hän on joskus hieman epäkohtelias ja voisi parantaa käytöstään. Toivon, että hän oppii olemaan ystävällisempi muille oppilaille."
        elif mielipide.value == "nofal":
            teksti = "Nofal on kuningas. T. Nofal itse."
        await interaction.response.send_message(teksti)

    @app_commands.command(name="kutsumalinkki", description="Luo kutsulinkin tai anna valmis.")
    @app_commands.describe(käyttökerrat="Linkin käyttömäärä (valinnainen)")
    @app_commands.checks.has_role("24G")
    async def kutsumalinkki(self, interaction: discord.Interaction, käyttökerrat: int = None):
        await kirjaa_komento_lokiin(self.bot, interaction, "/kutsumalinkki")
        await kirjaa_ga_event(self.bot, interaction.user.id, "kutsumalinkki_komento")
        if käyttökerrat is None:
            await interaction.response.send_message("https://discord.com/invite/xpu7cdGESg", ephemeral=True)
        else:
            try:
                invite = await interaction.channel.create_invite(max_uses=käyttökerrat, unique=True)
                await interaction.response.send_message(f"Kutsulinkki ({käyttökerrat}x): {invite.url}", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"Virhe: {e}", ephemeral=True)

    @app_commands.command(name="arvosanalaskuri", description="Laskee arvosanan pisteistä.")
    @app_commands.describe(
        pisteet="Saadut pisteet",
        maksimi="Maksimipisteet",
        lapipääsyprosentti="Läpipääsy %",
        piilota_vastaus="Näytä vastaus vain sinulle?"
    )
    async def arvosanalaskuri(
        self,
        interaction: discord.Interaction,
        pisteet: float,
        maksimi: float,
        lapipääsyprosentti: float,
        piilota_vastaus: bool = False
    ):
        try:
            await interaction.response.defer(ephemeral=piilota_vastaus)
            await kirjaa_komento_lokiin(self.bot, interaction, "/arvosanalaskuri")
            await kirjaa_ga_event(self.bot, interaction.user.id, "arvosanalaskuri_komento")

            lapiraja = (lapipääsyprosentti / 100) * maksimi
            if pisteet < lapiraja:
                arvosana = 0
            else:
                skaala = (pisteet - lapiraja) / (maksimi - lapiraja) if maksimi != lapiraja else 1
                arvosana = round(4 + 6 * skaala)
                arvosana = min(max(arvosana, 4), 10)

            await interaction.followup.send(
                f"Pisteet: {pisteet}/{maksimi} → Arvosana: **{arvosana}**",
                ephemeral=piilota_vastaus
            )

        except Exception as e:
            await interaction.followup.send(
                f"Virhe arvosanalaskurissa: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="laskin", description="Laskee laskun ja näyttää välivaiheet.")
    @app_commands.describe(
        lasku="Anna lasku esim. 8*5(4+4) tai LaTeX-muodossa kuten \\frac{4}{2} + \\sin(0)",
        selitys="Haluatko selityksen? kyllä/ei"
    )
    async def laskin(self, interaction: discord.Interaction, lasku: str, selitys: str = "ei"):
        await kirjaa_komento_lokiin(self.bot, interaction, "/laskin")
        await kirjaa_ga_event(self.bot, interaction.user.id, "laskin_komento")

        try:
            lasku_parsittu = latex_to_python(lasku)

            lasku_parsittu = lasku_parsittu.replace("^", "**").replace("sqrt", "math.sqrt")
            lasku_parsittu = lasku_parsittu.replace(")(", ")*(")
            lasku_parsittu = re.sub(r'(\d)\(', r'\1*(', lasku_parsittu)

            if not re.fullmatch(r'^[\d\s\.\+\-\*/\(\)\^mathsqrtmath\.sinmath\.cosmath\.tanmath\.exp]+$', lasku_parsittu):
                await interaction.response.send_message("Virhe: laskussa on tuntemattomia merkkejä. Käytä vain matemaattisia funktioita ja operaatioita.", ephemeral=True)
                return

            result = await asyncio.wait_for(calculate_steps(lasku_parsittu, selitys), timeout=3)
            await interaction.response.send_message(result)

        except asyncio.TimeoutError:
            await interaction.response.send_message("Lasku kesti liian kauan. Yritä lyhyemmissä osissa.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Virhe laskussa: {str(e)}", ephemeral=True)

    @app_commands.command(name="kulppi", description="Laskee kuinka monta kulppia annetusta ajasta.")
    @app_commands.describe(aika="Aika muodossa esim. 1h2m30s, 2m, 45s")
    @app_commands.checks.has_role("24G")
    async def kulppi(self, interaction: discord.Interaction, aika: str):
        await kirjaa_komento_lokiin(self.bot, interaction, "/kulppi")
        await kirjaa_ga_event(self.bot, interaction.user.id, "kulppi_komento")
        aika = aika.lower().replace(" ", "")
        match = re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', aika)

        if not match:
            await interaction.response.send_message("Anna aika muodossa esim. `1h2m30s`.", ephemeral=True)
            return

        h = int(match.group(1)) if match.group(1) else 0
        m = int(match.group(2)) if match.group(2) else 0
        s = int(match.group(3)) if match.group(3) else 0
        total = h * 3600 + m * 60 + s

        if total == 0:
            await interaction.response.send_message("Aika ei voi olla nolla!", ephemeral=True)
            return

        kulppeja = total / 90
        await interaction.response.send_message(
            f"Aika: **{total} sekuntia**\n1 kulppi = 90s\nVastaa noin **{kulppeja:.2f} kulppia**"
        )


    @app_commands.command(name="seuraava_lomapaivä", description="Näyttää seuraavan lomapäivän.")
    @app_commands.checks.has_role("24G")
    async def seuraava_lomapaiva(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/seuraava_lomapaiva")
        await kirjaa_ga_event(self.bot, interaction.user.id, "seuraava_lomapäivä_komento")
        nyt = datetime.now()
        for paiva, nimi in sorted(lomapaivat.items()):
            if paiva > nyt:
                pvm = paiva.strftime("%A %d.%m.%Y")
                await interaction.response.send_message(f"Seuraava lomapäivä on: {nimi} {pvm}")
                return
        await interaction.response.send_message("Ei tulevia lomapäiviä.", ephemeral=True)


    @app_commands.command(name="meme", description="Lähetä satunnainen meemi.")
    @app_commands.checks.has_role("24G")
    async def meme(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/meme")
        await kirjaa_ga_event(self.bot, interaction.user.id, "meme_komento")
        global last_meme_url

        if not meme_urls:
            await interaction.response.send_message("Meemilistassa ei ole kuvia.", ephemeral=True)
            return

        valittavat = [url for url in meme_urls if url != last_meme_url] or meme_urls
        valinta = random.choice(valittavat)
        last_meme_url = valinta
        await interaction.response.send_message(valinta)


    @app_commands.command(name="vitsi", description="Kertoo satunnaisen vitsin.")
    @app_commands.checks.has_role("24G")
    async def vitsi(self, interaction: discord.Interaction):
        await kirjaa_komento_lokiin(self.bot, interaction, "/vitsi")
        await kirjaa_ga_event(self.bot, interaction.user.id, "vitsi_komento")
        joke = random.choice(general_jokes)
        await interaction.response.send_message(joke)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction, error):
        await CommandErrorHandler(self.bot, interaction, error)

async def setup(bot: commands.Bot):
    cog = Misc(bot)
    await bot.add_cog(cog)

