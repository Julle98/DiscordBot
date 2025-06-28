import requests
from bs4 import BeautifulSoup

def simple_web_search(query: str) -> str:
    url = f"https://www.google.com/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    snippets = soup.find_all("div", class_="BNeawe")
    return "\n".join(t.text for t in snippets[:3])
