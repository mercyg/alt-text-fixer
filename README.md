# ♿ Alt Text Fixer

**Make any repo's docs readable by screen readers, in one command, with open-weight Gemma 4.**

Thousands of READMEs and docs sites are full of images like `![](diagram.png)` or `alt="screenshot"`. A blind developer hears "image" and nothing else: the architecture diagram, the install screenshot, the UI walkthrough are all invisible. Maintainers know it's a problem but rarely have time to fix it.

Alt Text Fixer scans a repo, finds images with missing or useless alt text, sends each image **plus the surrounding docs text** to Gemma 4, and writes real, context-aware descriptions. You review a diff and open a PR.

Built at Hacktoberfest Hack Day Silver Spring × AI Collective, Oct 17, 2026.

## Before → after
```diff
-![](docs/img/architecture.png)
+![Diagram of a client box connected to a server box by a single line](docs/img/architecture.png)

-![screenshot](docs/img/install.png)
+![Terminal running npm install my-lib, showing 12 packages added](docs/img/install.png)

-<img src="docs/img/architecture.png" width="300">
+<img alt="Diagram of a client connected to a server" src="docs/img/architecture.png" width="300">
```

## Features
- Finds Markdown (`![]()`) and HTML (`<img>`) images with **empty or generic alt** (`image`, `screenshot`, the filename…)
- Leaves good alt text alone
- **Context-aware**: the model sees the docs around the image, so it explains *why* the image is there
- `--dry-run` shows a unified diff before touching anything
- Runs **fully local and offline** with Gemma 4 via Ollama, or via the Gemini API
- Ships as an **Agent Skill** ([`skills/alt-text-fixer/SKILL.md`](skills/alt-text-fixer/SKILL.md)) so coding agents can "make this repo accessible" on request

## Quick start
```bash
pip install -r requirements.txt

# Option A: fully open + local
ollama pull gemma4          # use the exact Gemma 4 tag from `ollama list`
python alt_text_fixer.py path/to/repo --dry-run
python alt_text_fixer.py path/to/repo

# Option B: Gemma 4 via the Gemini API
export ALT_BACKEND=gemini GEMINI_API_KEY=your_key
python alt_text_fixer.py path/to/repo --dry-run
```

Try it on the included demo: `python alt_text_fixer.py demo --dry-run`

| Variable | Default | Purpose |
|---|---|---|
| `ALT_BACKEND` | `ollama` | `ollama` or `gemini` |
| `ALT_MODEL` | `gemma4` | Ollama model tag |
| `ALT_GEMINI_MODEL` | `gemma-4` | Gemini API model id |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server |

Flags: `--dry-run`, `--include-remote` (also describe images hosted at URLs), `--backend`.

## Use it in any repo (GitHub Action)
Add a repo secret `GEMINI_API_KEY`, then create `.github/workflows/alt-text.yml`:
```yaml
name: Alt text
on: [workflow_dispatch]
permissions: { contents: write, pull-requests: write }
jobs:
  alt-text:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: mercyg/alt-text-fixer@master
        with:
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
```
Run it from the Actions tab and it opens a PR with the new alt text. Set `open-pr: false` to only report the diff in the job summary. Full example: [`examples/alt-text.yml`](examples/alt-text.yml).

## How it works
1. Walk the repo (skipping `node_modules`, `.git`, build output) for `.md`, `.mdx` and `.html` files.
2. Regex out every image; keep only ones whose alt is empty, generic, or just the filename.
3. Send the image + ~600 characters of surrounding text to Gemma 4 with an accessibility-focused prompt.
4. Clean the result (no "Image of…", no characters that break Markdown) and write it back.

## Good first issues
- Support `.rst` and AsciiDoc
- GitHub Action that comments suggested alt text on PRs that add images
- Describe SVG diagrams by rendering them to PNG first
- Translate alt text for multilingual docs

## Tests
```bash
pytest -q
```

## License
MIT

