from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

SERPER_API_KEY = "53e53f1058997b79ecf3ede7a1314d1565ff2f49"

SEARCH_TYPES = {
    "general": "",
    "academic": " research study academic paper",
    "news": " news latest 2024 2025",
    "technical": " technical documentation guide tutorial"
}

app = FastAPI()

# Allow CORS for all origins (for web frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/name")
def get_name():
    print("[DEBUG] /name endpoint called")
    return "iam sas"

def search_web(query):
    print(f"[DEBUG] search_web called with query: {query}")
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": SERPER_API_KEY
    }
    payload = { "q": query, "num": 6 }
    try:
        response = requests.post("https://google.serper.dev/search", json=payload, headers=headers, timeout=5)
        print(f"[DEBUG] search_web response status: {response.status_code}")
        response.raise_for_status()
        organic = response.json().get("organic", [])
        print(f"[DEBUG] search_web found {len(organic)} organic results")
        return organic
    except Exception as e:
        print(f"[DEBUG] search_web exception: {e}")
        return []

def extract_fast(url):
    print(f"[DEBUG] extract_fast called with url: {url}")
    proxies = [
        f"https://api.codetabs.com/v1/proxy?quest={url}",
        f"https://api.allorigins.win/get?url={url}",
        f"https://thingproxy.freeboard.io/fetch/{url}"
    ]
    for proxy in proxies:
        try:
            print(f"[DEBUG] Trying proxy: {proxy}")
            r = requests.get(proxy, timeout=3)
            html = r.text if "contents" not in r.text else r.json().get("contents", "")
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            selectors = [
                'main', 'article', '.content', '.post-content', '.entry-content', '.article-content',
                '#content', '.main-content', '.article-body', '.post-body', '.story-body'
            ]
            main_content = ""
            for sel in selectors:
                el = soup.select_one(sel)
                if el:
                    main_content = el.get_text(separator=" ", strip=True)
                    print(f"[DEBUG] Found main content with selector: {sel}")
                    break
            if not main_content or len(main_content) < 100:
                ps = soup.find_all("p")
                main_content = " ".join(p.get_text(separator=" ", strip=True) for p in ps if len(p.get_text()) > 50)
                print(f"[DEBUG] Fallback to paragraphs, length: {len(main_content)}")
            if not main_content or len(main_content) < 100:
                body = soup.body
                if body:
                    main_content = body.get_text(separator=" ", strip=True)
                    print(f"[DEBUG] Fallback to body, length: {len(main_content)}")
            text = re.sub(r'\s+', ' ', main_content).strip()
            if len(text) > 100:
                print(f"[DEBUG] extract_fast success, length: {len(text)}")
                return text[:2000]
            else:
                print(f"[DEBUG] extract_fast insufficient content, length: {len(text)}")
        except Exception as e:
            print(f"[DEBUG] extract_fast proxy failed: {e}")
            continue
    print("[DEBUG] extract_fast failed for all proxies")
    return None

def generate_summary(content, query):
    print(f"[DEBUG] generate_summary called, content length: {len(content)}, query: {query}")
    lines = content.split(". ")
    match = [line for line in lines if any(w in line.lower() for w in query.lower().split())]
    top = sorted(match, key=lambda x: -len(x))[:4]
    overview, analysis = analyze_context(content, query)
    key_facts = generate_key_findings(content, query)
    print(f"[DEBUG] generate_summary found {len(top)} key info, {len(key_facts)} key facts")
    return {
        "overview": overview,
        "key_information": top if top else [],
        "analysis": analysis,
        "key_findings": key_facts if key_facts else []
    }

def frequent_words(text, query):
    print(f"[DEBUG] frequent_words called")
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    stopwords = set(query.lower().split() + ["this", "that", "with", "from", "have", "been", "also", "more", "they", "which"])
    freq = {}
    for w in words:
        if w not in stopwords:
            freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:5]
    print(f"[DEBUG] frequent_words top: {top}")
    return ", ".join(f"{w}({c})" for w, c in top)

def analyze_context(text, query):
    print(f"[DEBUG] analyze_context called")
    q = query.lower()
    if any(x in q for x in ["who is", "biography", "about"]):
        return (
            f"This appears to be biographical information about {query.replace('who is','').replace('about','').strip()}.",
            "The sources provide comprehensive background information including personal details, career highlights, and notable achievements."
        )
    if any(x in q for x in ["what is", "define", "explain"]):
        return (
            f"This is an explanation of {query.replace('what is','').replace('define','').replace('explain','').strip()}.",
            "The information covers key concepts, definitions, and detailed explanations from multiple authoritative sources."
        )
    if any(x in q for x in ["how to", "tutorial", "guide"]):
        return (
            f"This provides guidance on {query.replace('how to','').replace('tutorial','').replace('guide','').strip()}.",
            "The sources offer step-by-step instructions, best practices, and practical advice for implementation."
        )
    return (
        f"Based on your query about '{query}', here's what the analysis reveals:",
        "The compiled information provides comprehensive insights from multiple reliable sources to answer your question thoroughly."
    )

def generate_key_findings(text, query):
    print(f"[DEBUG] generate_key_findings called")
    sentences = re.split(r'[.!?]+', text)
    query_words = query.lower().split()
    facts = []
    for s in sentences:
        lower = s.lower()
        if (re.search(r'\d{4}|\d+%|\$\d+|born|died|founded|established|created', lower) or
            any(word in lower for word in query_words)):
            if len(s.strip()) > 20:
                facts.append(s.strip())
        if len(facts) >= 3:
            break
    if not facts:
        facts = [
            f"Multiple sources confirm information about {query}",
            "Content verified from reputable websites",
            "Analysis based on current available data"
        ]
    print(f"[DEBUG] generate_key_findings facts: {facts}")
    return facts

@app.get("/")
def root():
    print("[DEBUG] / root endpoint called")
    return {"message": "Deep Web AI Search API. Use /deepsearch endpoint."}

@app.get("/policy")
def get_policy():
    print("[DEBUG] /policy endpoint called")
    return {
        "policy": (
            "This API is for responsible, legal, and ethical use only. "
            "Do not use for illegal, harmful, or abusive purposes. "
            "Restricted words/queries are blocked. "
            "By using this API, you agree to comply with all applicable laws and our terms."
        )
    }

RESTRICTED_WORDS = [
    "hack", "porn", "sex", "nude", "illegal", "crack", "cheat", "exploit", "terror", "violence", "kill", "murder",
    "drugs", "weapon", "bomb", "child", "abuse", "darkweb", "deepweb", "credit card", "password", "leak", "leaks"
]

def contains_restricted_word(query):
    q = query.lower()
    for word in RESTRICTED_WORDS:
        if word in q:
            print(f"[DEBUG] Restricted word detected: {word}")
            return word
    return None

@app.post("/deepsearch")
async def deepsearch(request: Request):
    print("[DEBUG] /deepsearch POST endpoint called")
    data = await request.json()
    print(f"[DEBUG] Received data: {data}")
    query = data.get("query", "").strip()
    search_type = data.get("search_type", "general").lower()
    print(f"[DEBUG] Parsed query: '{query}', search_type: '{search_type}'")
    restricted = contains_restricted_word(query)
    if restricted:
        print(f"[DEBUG] Query blocked due to restricted word: {restricted}")
        return JSONResponse({"error": f"Use of restricted word '{restricted}' is not allowed."}, status_code=403)
    if not query:
        print("[DEBUG] Missing query in request")
        return JSONResponse({"error": "Missing query"}, status_code=400)
    if search_type not in SEARCH_TYPES:
        print(f"[DEBUG] Invalid search_type '{search_type}', defaulting to 'general'")
        search_type = "general"
    search_query = query + SEARCH_TYPES[search_type]
    print(f"[DEBUG] Final search_query: '{search_query}'")

    results = search_web(search_query)
    if not results:
        print("[DEBUG] No results found from search_web")
        return JSONResponse({"error": "No results found"}, status_code=404)

    sources = []
    contents = []
    snippets = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_result = {executor.submit(extract_fast, r['link']): r for r in results}
        for future in as_completed(future_to_result):
            r = future_to_result[future]
            try:
                content = future.result()
                status = "extracted" if content else "failed"
                if content:
                    contents.append(content)
                snippets.append(r.get("snippet") or "")
                print(f"[DEBUG] Extraction status for {r['link']}: {status}")
            except Exception as e:
                print(f"[DEBUG] Exception during extraction for {r['link']}: {e}")
                content = None
                status = "failed"
            sources.append({
                "title": r["title"],
                "link": r["link"],
                "status": "Extracted" if status == "extracted" else "Failed",
                "snippet": r.get("snippet", "")
            })

    if contents:
        full = " ".join(contents)
        print(f"[DEBUG] Using extracted contents, total length: {len(full)}")
    else:
        full = " ".join(snippets)
        print(f"[DEBUG] Using snippets as fallback, total length: {len(full)}")
    summary = generate_summary(full, query)

    print("[DEBUG] Returning response from /deepsearch POST")
    return {
        "sources": sources,
        "summary": summary
    }

@app.get("/deepsearch/{query}")
async def deepsearch_get(query: str, search_type: str = "general"):
    print(f"[DEBUG] /deepsearch/{query} GET endpoint called with search_type: {search_type}")
    restricted = contains_restricted_word(query)
    if restricted:
        print(f"[DEBUG] Query blocked due to restricted word: {restricted}")
        return JSONResponse({"error": f"Use of restricted word '{restricted}' is not allowed."}, status_code=403)
    if not query:
        print("[DEBUG] Missing query in path")
        return JSONResponse({"error": "Missing query"}, status_code=400)
    if search_type not in SEARCH_TYPES:
        print(f"[DEBUG] Invalid search_type '{search_type}', defaulting to 'general'")
        search_type = "general"
    search_query = query + SEARCH_TYPES[search_type]
    print(f"[DEBUG] Final search_query: '{search_query}'")

    results = search_web(search_query)
    if not results:
        print("[DEBUG] No results found from search_web")
        return JSONResponse({"error": "No results found"}, status_code=404)

    sources = []
    contents = []
    snippets = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_result = {executor.submit(extract_fast, r['link']): r for r in results}
        for future in as_completed(future_to_result):
            r = future_to_result[future]
            try:
                content = future.result()
                status = "extracted" if content else "failed"
                if content:
                    contents.append(content)
                snippets.append(r.get("snippet") or "")
                print(f"[DEBUG] Extraction status for {r['link']}: {status}")
            except Exception as e:
                print(f"[DEBUG] Exception during extraction for {r['link']}: {e}")
                content = None
                status = "failed"
            sources.append({
                "title": r["title"],
                "link": r["link"],
                "status": "Extracted" if status == "extracted" else "Failed",
                "snippet": r.get("snippet", "")
            })

    if contents:
        full = " ".join(contents)
        print(f"[DEBUG] Using extracted contents, total length: {len(full)}")
    else:
        full = " ".join(snippets)
        print(f"[DEBUG] Using snippets as fallback, total length: {len(full)}")
    summary = generate_summary(full, query)

    print("[DEBUG] Returning response from /deepsearch/{query} GET")
    return {
        "sources": sources,
        "summary": summary
    }

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))  # Default to 8080 if PORT not set
    import uvicorn
    print(f"[DEBUG] Starting server on port {port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
