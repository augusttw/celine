from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any

import httpx

from celine.tools.registry import tool

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"


def _clean_html_to_markdown(html_text: str) -> str:
    """Convert HTML text into clean readable markdown/plain text."""
    # Remove script, style, svg, noscript, header, footer, nav
    clean = re.sub(r"<(script|style|svg|noscript|header|footer|nav)[^>]*>.*?</\1>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace headings
    clean = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<h[4-6][^>]*>(.*?)</h[4-6]>", r"\n#### \1\n", clean, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace paragraphs and linebreaks
    clean = re.sub(r"<br\s*/?>", "\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", clean, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace links
    clean = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r"[\2](\1)", clean, flags=re.DOTALL | re.IGNORECASE)
    
    # Strip remaining HTML tags
    clean = re.sub(r"<[^>]+>", " ", clean)
    
    # Decode HTML entities
    clean = html.unescape(clean)
    
    # Clean whitespace
    lines = [line.strip() for line in clean.splitlines()]
    clean = "\n".join(line for line in lines if line)
    return re.sub(r"\n{3,}", "\n\n", clean)


@tool(
    name="web_search",
    description="Pesquisa na web por informações atualizadas, documentações, notícias e dados gerais.",
)
def web_search(query: str, num_results: int = 5) -> str:
    """Realiza uma busca na web.

    Args:
        query: Consulta de busca.
        num_results: Quantidade de resultados desejados (máximo: 10).
    """
    if not query.strip():
        return "Consulta vazia."

    limit = min(max(1, num_results), 10)
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html_content = resp.text

        # Extract search results from DuckDuckGo HTML
        # Typical structure: <a class="result__url" href="...">, <a class="result__snippet" ...>
        results: list[dict[str, str]] = []
        
        # Regex extraction of result blocks
        blocks = re.findall(r'<div class="result__body">.*?</div>\s*</div>', html_content, re.DOTALL)
        if not blocks:
            # Fallback pattern
            blocks = re.findall(r'<a class="result__snippet[^>]*>.*?</a>', html_content, re.DOTALL)

        for block in blocks[:limit]:
            title_match = re.search(r'<a class="result__snippet"[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, re.DOTALL)
            snippet_match = re.search(r'<a class="result__snippet[^>]*>(.*?)</a>', block, re.DOTALL)
            url_match = re.search(r'href=["\'](//duckduckgo\.com/l/\?uddg=([^"\'&]+)|https?://[^"\']+)["\']', block)

            title = html.unescape(re.sub(r"<[^>]+>", "", title_match.group(2))) if title_match else ""
            snippet = html.unescape(re.sub(r"<[^>]+>", "", snippet_match.group(1))) if snippet_match else ""
            
            link = ""
            if url_match:
                raw_link = url_match.group(1)
                if "uddg=" in raw_link:
                    encoded = url_match.group(2)
                    link = urllib.parse.unquote(encoded)
                else:
                    link = raw_link

            if title or snippet:
                results.append({"title": title.strip(), "link": link.strip(), "snippet": snippet.strip()})

        if not results:
            # General fallback extract
            text = _clean_html_to_markdown(html_content)
            return f"Resultados para '{query}':\n\n{text[:2000]}"

        output = [f"Resultados de busca para: '{query}'\n"]
        for i, res in enumerate(results, 1):
            output.append(f"{i}. **{res['title'] or 'Sem título'}**")
            if res["link"]:
                output.append(f"   URL: {res['link']}")
            if res["snippet"]:
                output.append(f"   {res['snippet']}")
            output.append("")

        return "\n".join(output)

    except Exception as exc:
        return f"Falha na busca web: {exc}"


@tool(
    name="read_web_page",
    description="Lê o conteúdo em texto limpo / markdown de uma URL da web.",
)
def read_web_page(url: str, max_chars: int = 15000) -> str:
    """Lê uma página web e extrai o conteúdo principal.

    Args:
        url: Endereço web (HTTP/HTTPS).
        max_chars: Limite de caracteres do conteúdo extraído.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    headers = {"User-Agent": USER_AGENT}

    try:
        with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            text = _clean_html_to_markdown(resp.text)

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[... conteúdo truncado em {max_chars} caracteres ...]"

        return f"Conteúdo de [{url}]:\n\n{text}"
    except Exception as exc:
        return f"Erro ao acessar {url}: {exc}"
