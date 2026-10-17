import shutil
from pathlib import Path
import alt_text_fixer as atf

def fake(img, mime, prompt):
    return "Image of a diagram showing a client connected to a server"

def test_fixes_missing_and_useless_alt(tmp_path):
    repo = tmp_path / "demo"
    shutil.copytree(Path(__file__).parent.parent / "demo", repo)
    before, after = atf.fix_file(repo / "README.md", repo, fake, False, lambda m: None)
    assert "![](" not in after
    assert "![screenshot]" not in after
    assert '<img alt="A diagram showing a client connected to a server" src=' in after
    assert "![Diagram of client and server]" in after   # good alt left alone
    assert after.count("A diagram showing") == 3

def test_useless_detection():
    assert atf.is_useless("", "a.png")
    assert atf.is_useless("Screenshot", "a.png")
    assert atf.is_useless("install", "img/install.png")
    assert not atf.is_useless("Install command output", "img/install.png")
