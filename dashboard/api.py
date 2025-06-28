from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer
from dashboard.metadata import push_role_connection
from bot.main import bot
import os, httpx, jinja2
from .xp_format import parse_xp_content, make_xp_content, calculate_level

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET"))

oauth = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://discord.com/api/oauth2/authorize",
    tokenUrl="https://discord.com/api/oauth2/token",
    scopes={
        "identify": "Perustiedot",
        "role_connections.write": "Päivitä metatiedot"
    }
)

template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("dashboard/templates"),
    enable_async=True
)

@app.get("/")
async def index(request: Request):
    return RedirectResponse("/login")

@app.get("/login")
async def login():
    url = (
        "https://discord.com/api/oauth2/authorize?"
        f"client_id={os.getenv('CLIENT_ID')}"
        f"&redirect_uri={os.getenv('REDIRECT_URI')}"
        "&response_type=code"
        "&scope=identify role_connections.write"
    )
    return RedirectResponse(url)

@app.get("/callback")
async def callback(code: str, request: Request):
    data = {
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.getenv("REDIRECT_URI")
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        token_res = await client.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
        token = token_res.json()["access_token"]

        user_res = await client.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {token}"})
        user = user_res.json()

    # XP-tiedot käyttäjälle
    xp_channel_id = int(os.getenv("XP_CHANNEL_ID"))
    xp_channel = bot.get_channel(xp_channel_id)

    xp, level, viestit = 0, 0, 0

    if xp_channel:
        async for msg in xp_channel.history(limit=1000):
            if msg.author.bot and msg.content.startswith(f"{user['id']}:"):
                xp_parsed, level_parsed = parse_xp_content(msg.content)
                xp, level = xp_parsed, level_parsed
                viestit = xp // 10  # Jos 10 XP = 1 viesti
                break

    await push_role_connection(token, viestit, xp, level)

    tpl = template_env.get_template("index.html")
    rendered = await tpl.render_async(
        username=user["username"],
        avatar=f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png",
        msgs=viestit,
        xp=xp,
        level=level
    )
    return HTMLResponse(rendered)
