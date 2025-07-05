import subprocess

def generate_reply(prompt: str) -> str:
    try:
        result = subprocess.run(
            ["ollama", "run", "llama3"],
            input=prompt.encode(),
            capture_output=True,
            timeout=30  
        )
        if result.returncode != 0:
            return f"Virhe: {result.stderr.decode(errors='ignore')}"
        return result.stdout.decode(errors="ignore")
    except subprocess.TimeoutExpired:
        return "⏱️ Mallin vastaus kesti liian kauan."
