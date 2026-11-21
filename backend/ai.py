"""AI logic: intent detection, prompt building, Tavily web search and Groq streaming."""
import os
import re
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv(Path(__file__).parent / ".env")

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class SearchError(Exception):
    pass


# ---------------------------------------------------------------- intent
PDF_WORDS = re.compile(
    r"\b(pdf|document|notes|lecture|slides?|uploaded|file|chapter|mcqs?|summar\w+|key points)\b", re.I
)
ASSIGN_WORDS = re.compile(
    r"\b(assignment|essay|report|introduction|conclusion|question\s*\d+|q\s*\d+|discuss|"
    r"differentiate|compare and contrast|short note|long question|explain in detail)\b", re.I
)
CODE_WORDS = re.compile(
    r"\b(code|program|function|algorithm|python|java|javascript|typescript|c\+\+|html|css|sql|"
    r"debug|error|bug|script|compile|class|loop|array|recursion|react|api|assembly|masm|"
    r"pointer|linked list|stack|queue)\b", re.I
)


def detect_intent(message: str, has_docs: bool) -> str:
    """Return one of: pdf, assignment, code, academic."""
    if has_docs and PDF_WORDS.search(message):
        return "pdf"
    if ASSIGN_WORDS.search(message):
        return "assignment"
    if CODE_WORDS.search(message):
        return "code"
    return "academic"


# ---------------------------------------------------------------- prompts
BASE_PROMPT = """You are Iqra LMS Assistant, a friendly and highly capable academic helper for university students.

Rules:
- Reply in the same language the student writes in. If they write Roman Urdu (Urdu in English letters), reply in natural Roman Urdu and keep technical terms in English.
- Explain in simple language first, then add depth. Use short paragraphs, Markdown headings, bullet lists and tables where they help.
- Put all code in fenced code blocks with the language name and helpful comments, then explain it briefly.
- Be accurate. If you are not sure, say so instead of guessing. Never invent facts, references, page numbers or links.
- Today's date is {today}."""

INTENT_HINTS = {
    "academic": "The student asked an academic question. Answer clearly, with a simple example when useful.",
    "code": (
        "The student asked a programming question. Give complete, working code first, "
        "then explain how it works step by step, and mention time complexity or common mistakes when relevant."
    ),
    "assignment": (
        "The student wants an assignment answer. Write it in a professional academic structure: "
        "a short Introduction, a clear Explanation (use headings and bullet points), a concrete Example, "
        "and a Conclusion. If the question needs code, include complete code in fenced blocks."
    ),
    "pdf": (
        "The student is asking about an uploaded document. Answer ONLY from the document excerpts below. "
        "If asked to summarize, give an overview followed by key points. If asked for MCQs, write the requested "
        "number (default 10) of questions with options A-D, then an 'Answer key' listing the correct letter with a "
        "one-line explanation for each. If the answer is not in the excerpts, say so."
    ),
}

STYLE_HINTS = {
    "short": "Keep the answer short: a few sentences or a compact list. No extra sections.",
    "detailed": "Give a detailed, well-structured answer.",
}

def build_system_prompt(intent, style, doc_context="", sources=None, lms_context=""):
    parts = [
        BASE_PROMPT.format(today=date.today().strftime("%B %d, %Y")),
        INTENT_HINTS[intent],
        STYLE_HINTS[style],
    ]

    if doc_context:
        parts.append(
            "UPLOADED DOCUMENT EXCERPTS (mention page numbers like (p. 3) when you use them):\\n"
            + doc_context
        )

    if lms_context:
        parts.append(
            "IQRA UNIVERSITY LMS DATA:\\n"
            "Answer questions about courses, assignments, deadlines and announcements "
            "using this data. Do not invent missing information. If information is "
            "not available, clearly say so.\\n\\n"
            + lms_context
        )

    if sources:
        lines = [
            f"[{i}] {s['title']} ({s['url']})\\n{s['snippet']}"
            for i, s in enumerate(sources, 1)
        ]
        parts.append(
            "WEB SEARCH RESULTS. Use them for current or factual details and cite with [1], [2] matching these "
            "numbers. Cite only what these results actually say. Do not write URLs or a reference list; the app "
            "shows the sources automatically. If the results do not answer the question, say so and answer from "
            "general knowledge, clearly marked as such.\\n\\n" + "\\n\\n".join(lines)
        )

    return "\\n\\n".join(parts)


# ---------------------------------------------------------------- PDF context
def build_doc_context(docs, query, max_chars=12000):
    """Whole text if it fits, otherwise the most relevant chunks (simple keyword scoring)."""
    if not docs:
        return ""
    if sum(len(d["text"]) for d in docs) <= max_chars:
        return "\n\n".join(f"=== {d['filename']} ===\n{d['text']}" for d in docs)

    chunks = []  # (order, filename, text)
    for d in docs:
        text, size = d["text"], 1500
        for start in range(0, len(text), size):
            chunks.append((len(chunks), d["filename"], text[start:start + size]))

    words = {w for w in re.findall(r"[a-zA-Z0-9]{4,}", query.lower())}
    scored = [(sum(c[2].lower().count(w) for w in words), c) for c in chunks]

    if any(score > 0 for score, _ in scored) and not re.search(r"summar|mcq|key points|overview", query, re.I):
        picked = [c for _, c in sorted(scored, key=lambda x: -x[0])]
    else:  # generic request: sample evenly across the whole document
        step = max(1, len(chunks) // max(1, max_chars // 1500))
        picked = chunks[::step]

    chosen, used = [], 0
    for c in picked:
        if used + len(c[2]) > max_chars:
            break
        chosen.append(c)
        used += len(c[2])
    chosen.sort(key=lambda c: c[0])
    return "\n\n".join(f"=== {c[1]} ===\n{c[2]}" for c in chosen)


# ---------------------------------------------------------------- web search (Tavily)
async def web_search(query: str, max_results: int = 5):
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key or key.startswith("your_"):
        raise SearchError("Web search is off because TAVILY_API_KEY is not set in backend/.env.")
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            res = await client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {key}"},
                json={"query": query[:400], "search_depth": "basic", "max_results": max_results},
            )
        if res.status_code in (401, 403):
            raise SearchError("Tavily rejected the API key. Check TAVILY_API_KEY in backend/.env.")
        res.raise_for_status()
    except SearchError:
        raise
    except httpx.HTTPError:
        raise SearchError("Web search failed. Answering without it.")
    results = res.json().get("results", [])
    return [
        {"title": r.get("title") or r["url"], "url": r["url"], "snippet": (r.get("content") or "")[:800]}
        for r in results
        if r.get("url")
    ]


# ---------------------------------------------------------------- Groq streaming
_client = None


def _get_client():
    global _client
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key or key.startswith("your_"):
        raise RuntimeError("GROQ_API_KEY is not set. Add it to backend/.env and restart the backend.")
    if _client is None:
        _client = AsyncGroq(api_key=key)
    return _client


async def stream_answer(system_prompt, history):
    client = _get_client()
    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in history
    ]
    stream = await client.chat.completions.create(
        model=GROQ_MODEL, messages=messages, temperature=0.4, max_tokens=4096, stream=True
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    text = str(exc)
    if isinstance(exc, RuntimeError):
        return text
    if name == "AuthenticationError":
        return "Groq rejected the API key. Check GROQ_API_KEY in backend/.env."
    if name == "RateLimitError":
        return "Groq rate limit reached. Wait a minute and try again, or choose a smaller model in GROQ_MODEL."
    if name == "NotFoundError":
        return f"The model '{GROQ_MODEL}' was not found. Check GROQ_MODEL in backend/.env."
    if name in ("APIConnectionError", "APITimeoutError"):
        return "Could not reach Groq. Check your internet connection."
    return f"The AI service returned an error: {text[:200]}"
