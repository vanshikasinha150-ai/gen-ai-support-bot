import re
from pathlib import Path

SIGNATURES = {"png": [b"\x89PNG\r\n\x1a\n"], "jpg": [b"\xff\xd8\xff"], "jpeg": [b"\xff\xd8\xff"], "pdf": [b"%PDF"]}
DANGEROUS_HEADERS = [b"MZ", b"\x7fELF", b"#!", b"PK\x03\x04"]            # executables, scripts, archives
PDF_ACTIVE = [b"/JavaScript", b"/JS", b"/Launch", b"/OpenAction", b"/EmbeddedFile"]

INJECTION = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
    r"disregard .{0,30}(instructions|rules|polic)",
    r"reveal .{0,40}(admin|secret|password|system prompt|api key)",
    r"system prompt",
    r"you are now",
    r"pretend (to be|you are)",
    r"act as .{0,20}(admin|root)",
    r"override .{0,20}(policy|rules|instructions)",
    r"do not tell the (user|customer)",
]
INJECTION_RX = [re.compile(p, re.I) for p in INJECTION]


def check_file(path, c):
    """Returns None if the file is safe to process, otherwise the reason it was refused."""
    p = Path(path)
    if not p.exists():
        return "file not found"
    ext = p.suffix.lower().lstrip(".")
    if ext not in c["allowed_types"]:
        return f"file type '.{ext}' is not allowed"
    size = p.stat().st_size
    if size == 0:
        return "file is empty"
    if size > c["max_mb"] * 1024 * 1024:
        return "file is too large"
    raw = p.read_bytes()
    if any(raw.startswith(h) for h in DANGEROUS_HEADERS):
        return "executable, script or archive content is not allowed"
    signatures = SIGNATURES.get(ext)
    if signatures and not any(raw.startswith(s) for s in signatures):
        return "file content does not match its type"
    if ext == "pdf" and any(tok in raw for tok in PDF_ACTIVE):
        return "PDF contains active content"
    return None


def scan_text(text):
    """Instructions hidden inside an image or PDF show up in its OCR text."""
    return [rx.pattern for rx in INJECTION_RX if rx.search(text)]
