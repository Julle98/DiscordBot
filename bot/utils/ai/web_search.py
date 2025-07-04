import duckduckgo_search
from duckduckgo_search import DDGS

def simple_web_search(query: str) -> str:
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=3):
            results.append(f"{r['title']}\n{r['body']}\n{r['href']}")
    return "\n\n".join(results)
