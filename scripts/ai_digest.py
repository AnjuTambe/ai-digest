#!/usr/bin/env python3
"""
AI Digest
Pulls: Hacker News (AI-related top stories), GitHub trending repos, arXiv recent papers.
Sends a single HTML email digest.

Run via cron / GitHub Actions on a schedule.
Requires env vars:
  GMAIL_ADDRESS   - your gmail address (sender + recipient, or set RECIPIENT separately)
  GMAIL_APP_PASSWORD - Gmail App Password (not your normal password)
  RECIPIENT (optional) - defaults to GMAIL_ADDRESS
"""

import os
import re
import smtplib
import requests
import feedparser
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "gemini", "anthropic", "openai",
    "machine learning", "neural", "transformer", "agent", "diffusion",
    "rag", "fine-tun", "inference", "model weights", "mistral", "llama"
]

def is_ai_related(text):
    text = text.lower()
    return any(kw in text for kw in AI_KEYWORDS)

# ---------- Hacker News ----------
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

# ---------- GitHub Trending ----------
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

# ---------- arXiv ----------
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

# ---------- Build Email ----------
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

# ---------- Send Email ----------
def send_email(html_body):
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("RECIPIENT", sender)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Digest — {datetime.now().strftime('%b %d, %Y')}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

def main():
    print("Fetching HN...")
    hn_stories = fetch_hn_ai_stories()
    print("Fetching GitHub trending...")
    gh_repos = fetch_github_trending()
    print("Fetching arXiv...")
    papers = fetch_arxiv_papers()

    html = build_html(hn_stories, gh_repos, papers)
    print("Sending email...")
    send_email(html)
    print("Done.")

if __name__ == "__main__":
    main()
