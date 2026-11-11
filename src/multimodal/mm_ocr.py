from pathlib import Path

ENGINE = None                  # tests and demos can plug in a fake OCR engine: fn(path) -> (text, confidence 0-100)


class OcrUnavailable(Exception):
    pass


def set_engine(fn):
    global ENGINE
    ENGINE = fn


def run(path):
    """Returns (text, confidence). Images use Tesseract, PDFs use their text layer."""
    if ENGINE:
        return ENGINE(path)
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise OcrUnavailable("PDF reading needs: pip install pypdf")
        text = "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
        return text, (95.0 if text.strip() else 0.0)
    try:
        import pytesseract
        from PIL import Image
        data = pytesseract.image_to_data(Image.open(path), output_type=pytesseract.Output.DICT)
    except Exception as e:
        raise OcrUnavailable(f"image OCR needs Tesseract: pip install pytesseract pillow ({type(e).__name__})")
    words, confs = [], []
    for word, conf in zip(data["text"], data["conf"]):
        if word.strip():
            words.append(word)
            if float(conf) >= 0:
                confs.append(float(conf))
    return " ".join(words), (sum(confs) / len(confs) if confs else 0.0)


def image_sharpness(path):
    """Returns (sharpness, smallest side in pixels), or None when it cannot be measured. Low sharpness = blurry."""
    if Path(path).suffix.lower() == ".pdf":
        return None
    try:
        from PIL import Image, ImageFilter, ImageStat
        img = Image.open(path).convert("L")
        side = min(img.size)
        img.thumbnail((800, 800))
        laplacian = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)
        return ImageStat.Stat(img.filter(laplacian)).var[0], side
    except Exception:
        return None
