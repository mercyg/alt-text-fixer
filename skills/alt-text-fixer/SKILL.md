---
name: alt-text-fixer
description: Find images with missing or meaningless alt text in a repository's Markdown and HTML docs and write real, context-aware descriptions using the open-weight Gemma 4 model. Use when asked to make docs or a README accessible, fix alt text, or improve screen reader support.
license: MIT
---

# Alt Text Fixer

Makes a repo's documentation accessible to blind and low-vision readers by replacing empty or useless alt text (`![](x.png)`, `alt="screenshot"`, `<img>` with no alt) with real descriptions written by Gemma 4.

## Steps
1. Check a Gemma 4 backend is available:
   - Local (default, fully open): `ollama list` shows a Gemma 4 tag. Set `ALT_MODEL` if the tag isn't `gemma4`.
   - Or set `ALT_BACKEND=gemini` and `GEMINI_API_KEY`.
2. Preview first, from the tool's folder:
   ```bash
   python alt_text_fixer.py <repo_path> --dry-run
   ```
3. Show the user the diff. Point out any alt text that looks wrong or vague.
4. Once the user approves, run it without `--dry-run` to write the changes. Add `--include-remote` to also describe images hosted at URLs.
5. Suggest committing on a branch, e.g. `git checkout -b docs/alt-text`, and opening a PR titled "docs: add descriptive alt text for screen readers".

## Rules
- Never overwrite alt text that is already descriptive. The tool only touches empty or generic alt.
- Always do a dry run and get approval before writing files.
- Generated alt text is a draft. A human should skim it before merging.
