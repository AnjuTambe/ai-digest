#!/usr/bin/env python3
"""
AI Digest
Pulls: Hacker News (AI-related top stories), GitHub trending repos, arXiv recent papers.
Sends a single HTML email digest via SendGrid API.

Requires env vars:
  SENDGRID_API_KEY   - SendGrid API key
  FROM_EMAIL         - Verified sender email in SendGrid
  RECIPIENT          - Destination email
"""

import os
import re
import requests
import feedparser
from datetime import datetime

AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "gemini", "anthropic", "openai",
    "machine learning", "neural", "transformer", "agent", "diffusion",
    "rag", "fine-tun", "inference", "model weights", "mistral", "llama"
]

def is_ai_related(text):
    text = text.lower()
    return any(kw in text for kw in AI_KEYWORDS)

def fetch_hn_ai_stories(limit=8):
    top_ids = requests.get(
        "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
    ).json()[:150]

    stories = []
    for story_id in top_ids:
        if len(stories) >= limit:
            break
        item = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=10
        ).json()
        if not item or "title" not in item:
            continue
        if is_ai_related(item["title"]):
            stories.append({
                "title": item["title"],
                "url": item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                "score": item.get("score", 0),
                "comments": f"https://news.ycombinator.com/item?id={story_id}"
            })
    return stories

def fetch_github_trending(languages=("python", "typescript"), limit=5):
    repos = []
    for lang in languages:
        url = f"https://github.com/trending/{lang}?since=weekly"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            matches = re.findall(
                r'<h2[^>]*class="h3[^"]*"[^>]*>\s*<a[^>]*href="/([\w.-]+/[\w.-]+)"', resp.text
            )
            seen = set()
            for repo in matches:
                if repo not in seen:
                    seen.add(repo)
                    repos.append({"name": repo, "url": f"https://github.com/{repo}", "lang": lang})
                if len([r for r in repos if r["lang"] == lang]) >= limit:
                    break
        except Exception as e:
            print(f"GitHub trending fetch failed for {lang}: {e}")
    return repos

def fetch_arxiv_papers(limit=5):
    feed_url = (
        "http://export.arxiv.org/api/query?"
        "search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG&"
        "sortBy=submittedDate&sortOrder=descending&max_results=" + str(limit)
    )
    feed = feedparser.parse(feed_url)
    papers = []
    for entry in feed.entries:
        papers.append({
            "title": entry.title.replace("\n", " ").strip(),
            "url": entry.link,
            "summary": entry.summary[:200].replace("\n", " ").strip() + "..."
        })
    return papers

def build_html(hn_stories, gh_repos, papers):
    date_str = datetime.now().strftime("%B %d, %Y")
    html = f"<h2>🤖 AI Digest — {date_str}</h2>"

    html += "<h3>📰 Hacker News</h3><ul>"
    for s in hn_stories:
        html += f'<li><a href="{s["url"]}">{s["title"]}</a> ({s["score"]} pts) — <a href="{s["comments"]}">comments</a></li>'
    html += "</ul>"

    html += "<h3>🔥 GitHub Trending</h3><ul>"
    for r in gh_repos:
        html += f'<li>[{r["lang"]}] <a href="{r["url"]}">{r["name"]}</a></li>'
    html += "</ul>"

    html += "<h3>📄 arXiv (cs.AI / cs.CL / cs.LG)</h3><ul>"
    for p in papers:
        html += f'<li><a href="{p["url"]}">{p["title"]}</a><br><small>{p["summary"]}</small></li>'
    html += "</ul>"
    return html

def send_email_sendgrid(html_body):
    api_key = os.environ["SENDGRID_API_KEY"]
    from_email = os.environ["FROM_EMAIL"]
    to_email = os.environ["RECIPIENT"]

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
        "subject": f"AI Digest — {datetime.now().strftime('%b %d, %Y')}",
        "content": [{"type": "text/html", "value": html_body}],
    }

    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )

    if resp.status_code >= 300:
        raise RuntimeError(f"SendGrid error {resp.status_code}: {resp.text}")

def main():
    print("Fetching HN...")
    hn_stories = fetch_hn_ai_stories()
    print("Fetching GitHub trending...")
    gh_repos = fetch_github_trending()
    print("Fetching arXiv...")
    papers = fetch_arxiv_papers()

    html = build_html(hn_stories, gh_repos, papers)
    print("Sending email...")
    send_email_sendgrid(html)
    print("Done.")

if __name__ == "__main__":
    main()
