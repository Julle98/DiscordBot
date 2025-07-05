import subprocess

async def suorita_kysymys(prompt: str) -> str:
    try:
        result = subprocess.run(
            ["ollama", "run", "llama3"],
            input=prompt.encode("utf-8"),
            capture_output=True,
            timeout=30
        )
        if result.returncode != 0:
            virhe = result.stderr.decode(errors="ignore")
            return f"⚠️ Virhe mallin ajossa:\n```{virhe}```"
        vastaus = result.stdout.decode(errors="ignore").strip()
        return vastaus if vastaus else "🤖 Malli ei antanut vastausta."
    except subprocess.TimeoutExpired:
        return "⏱️ Mallin vastaus kesti liian kauan."
    except Exception as e:
        return f"🚫 Odottamaton virhe: {e}"


