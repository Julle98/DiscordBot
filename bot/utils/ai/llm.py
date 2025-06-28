import subprocess

def generate_reply(prompt: str) -> str:
    result = subprocess.run(["ollama", "run", "llama3"], input=prompt.encode(), capture_output=True)
    return result.stdout.decode(errors="ignore")
