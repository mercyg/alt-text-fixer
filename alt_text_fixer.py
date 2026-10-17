#!/usr/bin/env python3
"""Alt Text Fixer: find images with missing or useless alt text in a repo and
write real descriptions using the open-weight Gemma 4 model.

Backends:
  ollama (default)  Gemma 4 running locally via Ollama. Fully open, offline.
  gemini            Gemma 4 via the Gemini API (set GEMINI_API_KEY).

Usage:
  python alt_text_fixer.py <repo_path> [--dry-run] [--backend ollama|gemini] [--include-remote]
"""
import argparse
import base64
import difflib
import mimetypes
import os
import re
import sys
from pathlib import Path

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("ALT_MODEL", "gemma4")              # check `ollama list` for your exact tag
GEMINI_MODEL = os.getenv("ALT_GEMINI_MODEL", "gemma-4")       # check AI Studio for the exact model id

DOC_EXTS = {".md", ".markdown", ".mdx", ".html", ".htm"}
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv", "__pycache__"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
# Alt text that technically exists but tells a screen reader user nothing.
USELESS_ALT = {"", "image", "img", "picture", "photo", "screenshot", "screen shot",
               "logo", "icon", "alt", "alt text", "untitled", "figure", "diagram", "graph"}

MD_IMG = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)(?P<title>\s+\"[^\"]*\")?\)")
HTML_IMG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ATTR = lambda name: re.compile(rf"""\b{name}\s*=\s*(["'])(.*?)\1""", re.IGNORECASE | re.DOTALL)
SRC_ATTR, ALT_ATTR = ATTR("src"), ATTR("alt")

PROMPT = """You are writing alt text for an image in software documentation, for blind and
low-vision readers using a screen reader.

Context from the document around the image:
---
{context}
---
Image file name: {name}

Write the alt text. Rules:
- One or two sentences, ideally under 125 characters.
- Describe what matters for understanding the docs: what the image shows and its purpose.
- If it is a screenshot of UI or code, say what it shows and any key text.
- If it is a diagram or chart, state the main relationship or takeaway.
- If it is a badge or logo, just name it (e.g. "Build passing badge").
- Do NOT start with "Image of" or "Picture of". No quotes, no markdown.
Return only the alt text."""


def is_useless(alt: str, src: str) -> bool:
    a = alt.strip().lower()
    stem = Path(src.split("?")[0]).stem.lower()
    return a in USELESS_ALT or a == stem or a == Path(src.split("?")[0]).name.lower()


def load_image(src: str, doc_path: Path, repo: Path, include_remote: bool):
    clean = src.split("?")[0].split("#")[0]
    if clean.startswith(("http://", "https://")):
        if not include_remote:
            return None, None
        if "shields.io" in clean or "badge" in clean:
            return None, None  # badges are SVGs; skip rather than guess
        r = requests.get(clean, timeout=20)
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "image/png").split(";")[0]
    if clean.startswith("data:"):
        return None, None
    path = (repo / clean.lstrip("/")) if clean.startswith("/") else (doc_path.parent / clean)
    path = path.resolve()
    if not path.exists() or path.suffix.lower() not in IMAGE_EXTS:
        return None, None
    return path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/png"


def describe_ollama(img: bytes, mime: str, prompt: str) -> str:
    r = requests.post(f"{OLLAMA_URL}/api/chat", timeout=300, json={
        "model": OLLAMA_MODEL, "stream": False, "options": {"temperature": 0.2},
        "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(img).decode()]}],
    })
    r.raise_for_status()
    return r.json()["message"]["content"]


def describe_gemini(img: bytes, mime: str, prompt: str) -> str:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    res = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=img, mime_type=mime), prompt],
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return res.text


def clean_alt(text: str) -> str:
    text = text.strip().strip('"\'`').splitlines()[0].strip()
    text = re.sub(r"^alt text:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^((an?|the)\s+)?(image|picture|photo)\s+of\s+", "", text, flags=re.IGNORECASE)
    text = text.replace("]", ")").replace("[", "(").replace('"', "'")
    return text[:1].upper() + text[1:] if text else text


def context_around(text: str, start: int, end: int, chars: int = 600) -> str:
    return text[max(0, start - chars):min(len(text), end + chars)]


def fix_file(doc: Path, repo: Path, describe, include_remote: bool, log):
    original = doc.read_text(encoding="utf-8", errors="ignore")
    edits = []  # (start, end, replacement)

    for m in MD_IMG.finditer(original):
        alt, src = m.group("alt"), m.group("src")
        if not is_useless(alt, src):
            continue
        new_alt = generate(original, m, src, doc, repo, describe, include_remote, log)
        if new_alt:
            edits.append((m.start(), m.end(), f"![{new_alt}]({src}{m.group('title') or ''})"))

    for m in HTML_IMG.finditer(original):
        tag = m.group(0)
        src_m = SRC_ATTR.search(tag)
        if not src_m:
            continue
        alt_m = ALT_ATTR.search(tag)
        if alt_m and not is_useless(alt_m.group(2), src_m.group(2)):
            continue
        new_alt = generate(original, m, src_m.group(2), doc, repo, describe, include_remote, log)
        if not new_alt:
            continue
        if alt_m:
            new_tag = tag[:alt_m.start()] + f'alt="{new_alt}"' + tag[alt_m.end():]
        else:
            new_tag = re.sub(r"^<img\b", f'<img alt="{new_alt}"', tag, flags=re.IGNORECASE)
        edits.append((m.start(), m.end(), new_tag))

    if not edits:
        return original, original
    updated = original
    for start, end, rep in sorted(edits, reverse=True):
        updated = updated[:start] + rep + updated[end:]
    return original, updated


def generate(text, match, src, doc, repo, describe, include_remote, log):
    try:
        img, mime = load_image(src, doc, repo, include_remote)
    except Exception as e:
        log(f"  ! could not load {src}: {e}")
        return None
    if img is None:
        log(f"  - skipped {src} (remote, missing, or not a raster image)")
        return None
    prompt = PROMPT.format(context=context_around(text, match.start(), match.end()), name=Path(src).name)
    try:
        alt = clean_alt(describe(img, mime, prompt))
    except Exception as e:
        log(f"  ! model error on {src}: {e}")
        return None
    log(f"  + {src} -> {alt}")
    return alt


def find_docs(repo: Path):
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if Path(f).suffix.lower() in DOC_EXTS:
                yield Path(root) / f


def main(argv=None):
    p = argparse.ArgumentParser(description="Write real alt text for images in a repo using Gemma 4.")
    p.add_argument("repo", type=Path)
    p.add_argument("--dry-run", action="store_true", help="show the diff, don't write files")
    p.add_argument("--backend", choices=["ollama", "gemini"], default=os.getenv("ALT_BACKEND", "ollama"))
    p.add_argument("--include-remote", action="store_true", help="also download and describe remote images")
    a = p.parse_args(argv)

    repo = a.repo.resolve()
    describe = describe_gemini if a.backend == "gemini" else describe_ollama
    log = lambda msg: print(msg, file=sys.stderr)
    changed, fixed = 0, 0

    for doc in find_docs(repo):
        rel = doc.relative_to(repo)
        before, after = fix_file(doc, repo, describe, a.include_remote, log)
        if before == after:
            continue
        changed += 1
        fixed += len([1 for _ in difflib.ndiff(before.splitlines(), after.splitlines()) if _.startswith("+ ")])
        sys.stdout.writelines(difflib.unified_diff(
            before.splitlines(True), after.splitlines(True), f"a/{rel}", f"b/{rel}"))
        if not a.dry_run:
            doc.write_text(after, encoding="utf-8")

    verb = "would update" if a.dry_run else "updated"
    log(f"\nDone: {verb} {changed} file(s), ~{fixed} line(s) with new alt text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
