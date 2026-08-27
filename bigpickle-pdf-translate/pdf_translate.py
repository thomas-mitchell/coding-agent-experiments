"""
Offline Japanese to English PDF Translator.

This tool translates Japanese PDF documents to English using 100% local libraries
and offline neural machine translation models (MarianMT via Hugging Face Transformers).
No external or online APIs are invoked.
"""

import argparse
import os
import re
import sys
import time
from typing import List, Dict, Any, Optional

# Suppress Hugging Face symlink and token warnings on Windows
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def check_dependencies(ocr_needed: bool = False):
    """Verify that required local dependencies are installed.

    When *ocr_needed* is True an error is raised if the OCR stack is
    unavailable.  Otherwise a warning is printed.
    """
    missing = []
    try:
        import pymupdf
    except ImportError:
        missing.append("pymupdf")

    try:
        import torch
        import transformers
        import sentencepiece
    except ImportError:
        missing.append("torch transformers sentencepiece sacremoses")

    try:
        import reportlab
    except ImportError:
        missing.append("reportlab")

    if missing:
        print(f"Error: Missing required packages: {', '.join(missing)}")
        print(f"Please install them using: pip install {' '.join(missing)}")
        sys.exit(1)

    # OCR packages are optional unless explicitly required
    ocr_missing = []
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        ocr_missing.append("pytesseract")
    try:
        import PIL  # noqa: F401
    except ImportError:
        ocr_missing.append("Pillow")

    if ocr_missing:
        msg = (
            f"Warning: OCR packages not found ({', '.join(ocr_missing)}). "
            "OCR is required for image-based PDFs (scanned documents). "
            "Install them with: pip install pytesseract Pillow\n"
            "Also ensure Tesseract OCR is installed on your system:\n"
            "  Windows: https://github.com/tesseract-ocr/tesseract/wiki\n"
            "  Linux:   sudo apt install tesseract-ocr tesseract-ocr-jpn\n"
            "  macOS:   brew install tesseract"
        )
        if ocr_needed:
            print(f"Error: {msg}")
            sys.exit(1)
        else:
            print(msg)


def _configure_tesseract_path():
    """Auto-detect Tesseract on Windows if it is not already in PATH."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return  # already works
    except Exception:
        pass

    import glob
    common = [
        r"C:\Program Files\Tesseract-OCR",
        r"C:\Program Files (x86)\Tesseract-OCR",
    ]
    for base in common:
        hits = glob.glob(os.path.join(base, "tesseract.exe"))
        if hits:
            os.environ["PATH"] = base + os.pathsep + os.environ.get("PATH", "")
            return


class JapaneseTextProcessor:
    """Handles Japanese text preprocessing, cleaning, and sentence segmentation."""

    # Sentence boundary delimiters in Japanese
    SENTENCE_ENDINGS = re.compile(r'([。！？!?]+[\s\n]*)')

    @staticmethod
    def clean_japanese_text(text: str) -> str:
        """Clean and normalize Japanese text extracted from PDF."""
        if not text:
            return ""
        # Replace non-standard whitespace
        text = text.replace('\u3000', ' ')  # Full-width space
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove hyphenation at line breaks
        text = re.sub(r'-\n', '', text)
        
        # Join Japanese lines broken across line wraps
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return ""

        merged_paragraphs = []
        current_p = []

        for line in lines:
            if not current_p:
                current_p.append(line)
            else:
                last_char = current_p[-1][-1]
                first_char = line[0]
                # Check if both are CJK characters (Hiragana, Katakana, Kanji)
                if JapaneseTextProcessor.is_cjk(last_char) and JapaneseTextProcessor.is_cjk(first_char):
                    current_p[-1] += line
                else:
                    current_p[-1] += " " + line

        return "\n\n".join(current_p)

    @staticmethod
    def is_cjk(char: str) -> bool:
        """Check if character is in CJK / Japanese Unicode ranges."""
        code = ord(char)
        return (
            0x3040 <= code <= 0x309F or  # Hiragana
            0x30A0 <= code <= 0x30FF or  # Katakana
            0x4E00 <= code <= 0x9FFF or  # Kanji (CJK Unified Ideographs)
            0x3400 <= code <= 0x4DBF or  # CJK Extension A
            0x20000 <= code <= 0x2A6DF or # CJK Extension B
            0xF900 <= code <= 0xFAFF or  # CJK Compatibility
            0x3000 <= code <= 0x303F     # CJK Symbols and Punctuation
        )

    @staticmethod
    def split_into_sentences(text: str, max_chars: int = 200) -> List[str]:
        """Split a Japanese text block into manageable sentence chunks."""
        text = text.strip()
        if not text:
            return []

        # Split by Japanese punctuation
        raw_parts = JapaneseTextProcessor.SENTENCE_ENDINGS.split(text)
        sentences = []
        current = ""

        for part in raw_parts:
            if not part:
                continue
            if JapaneseTextProcessor.SENTENCE_ENDINGS.match(part):
                current += part
                if len(current.strip()) > 0:
                    sentences.append(current.strip())
                    current = ""
            else:
                if current:
                    current += part
                else:
                    current = part

        if current.strip():
            sentences.append(current.strip())

        # If any sentence exceeds max_chars, split further by commas or spaces
        final_sentences = []
        for s in sentences:
            if len(s) > max_chars:
                sub_parts = re.split(r'([、,])', s)
                sub_curr = ""
                for sp in sub_parts:
                    if len(sub_curr) + len(sp) > max_chars and sub_curr:
                        final_sentences.append(sub_curr.strip())
                        sub_curr = sp
                    else:
                        sub_curr += sp
                if sub_curr.strip():
                    final_sentences.append(sub_curr.strip())
            else:
                final_sentences.append(s)

        return [s for s in final_sentences if s.strip()]


class LocalTranslator:
    """Local offline translation model using Hugging Face Transformers."""

    def __init__(self, model_name_or_path: str = "Helsinki-NLP/opus-mt-ja-en",
                 device: str = "auto", offline_only: bool = False):
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        self.model_name = model_name_or_path
        self.offline_only = offline_only

        # Determine compute device
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        print(f"Loading local translation model '{model_name_or_path}' on {self.device}...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name_or_path,
                local_files_only=offline_only
            )
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                model_name_or_path,
                local_files_only=offline_only
            ).to(self.device)
            self.model.eval()
            print("Model loaded successfully.")
        except Exception as e:
            print(f"\n[Error] Failed to load model '{model_name_or_path}': {e}")
            if offline_only:
                print("Tip: If running offline for the first time, ensure the model has been pre-downloaded")
                print("or run without '--offline' once to cache the model locally.")
            sys.exit(1)

    def translate_batch(self, texts: List[str], batch_size: int = 8) -> List[str]:
        """Translate a batch of Japanese texts to English locally."""
        if not texts:
            return []

        import torch

        results = []
        total = len(texts)

        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            clean_batch = [t if t.strip() else " " for t in batch]

            inputs = self.tokenizer(
                clean_batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            ).to(self.device)

            with torch.no_grad():
                translated_tokens = self.model.generate(
                    **inputs,
                    max_length=512,
                    num_beams=4,
                    early_stopping=True
                )

            decoded = self.tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)
            results.extend(decoded)

        return results

    def translate_text(self, text: str, batch_size: int = 8) -> str:
        """Translate a multi-sentence Japanese paragraph into English."""
        if not text or not text.strip():
            return ""

        sentences = JapaneseTextProcessor.split_into_sentences(text)
        if not sentences:
            return ""

        translated_sentences = self.translate_batch(sentences, batch_size=batch_size)
        return " ".join(s.strip() for s in translated_sentences if s.strip())


class PDFExtractor:
    """Extracts text and structure from a PDF file using PyMuPDF.

    When *use_ocr* is ``True`` and a page contains no embedded text, the
    page is rendered to an image and OCR'd with Tesseract (via
    ``pytesseract``).  This allows translation of scanned / image-based
    PDFs.
    """

    OCR_DPI = 300  # resolution for OCR rendering

    def __init__(self, pdf_path: str, use_ocr: bool = False):
        import pymupdf
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Input file not found: {pdf_path}")
        self.pdf_path = pdf_path
        self.doc = pymupdf.open(pdf_path)
        self.use_ocr = use_ocr
        self._ocr_checked: set = set()  # pages we already attempted OCR on

    @property
    def total_pages(self) -> int:
        return len(self.doc)

    def parse_page_range(self, pages_str: Optional[str]) -> List[int]:
        """Parse page range string (e.g., '1,3,5-7', 'all'). 1-indexed."""
        total = self.total_pages
        if not pages_str or pages_str.strip().lower() == "all":
            return list(range(1, total + 1))

        selected = set()
        for part in pages_str.split(','):
            part = part.strip()
            if '-' in part:
                start_s, end_s = part.split('-', 1)
                start = max(1, int(start_s))
                end = min(total, int(end_s))
                for p in range(start, end + 1):
                    selected.add(p)
            else:
                p = int(part)
                if 1 <= p <= total:
                    selected.add(p)
        return sorted(list(selected))

    # ------------------------------------------------------------------
    # OCR helpers
    # ------------------------------------------------------------------

    def _render_page_to_image(self, page_num: int):
        """Render a PDF page to a PIL Image at OCR_DPI."""
        import pymupdf
        from PIL import Image

        page = self.doc[page_num - 1]
        zoom = self.OCR_DPI / 72.0
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    def _ocr_page(self, page_num: int) -> str:
        """OCR a single page and return the extracted text."""
        import pytesseract
        img = self._render_page_to_image(page_num)
        # Use Japanese + English for best coverage
        text = pytesseract.image_to_string(img, lang="jpn+eng")
        return text

    def _ocr_page_blocks(self, page_num: int) -> List[Dict[str, Any]]:
        """OCR a page and return structured blocks compatible with
        ``extract_page_data`` output."""
        import pytesseract
        import pymupdf

        page = self.doc[page_num - 1]
        img = self._render_page_to_image(page_num)

        # Get detailed OCR data (bounding boxes + text)
        data = pytesseract.image_to_data(img, lang="jpn+eng", output_type=pytesseract.Output.DICT)

        # Group words into lines, then lines into blocks (paragraph-level)
        n = len(data["text"])
        lines: Dict[tuple, List[Dict]] = {}
        for i in range(n):
            text = data["text"][i].strip()
            if not text:
                continue
            line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(line_key, []).append({
                "text": text,
                "x": data["left"][i],
                "y": data["top"][i],
                "w": data["width"][i],
                "h": data["height"][i],
            })

        if not lines:
            return []

        # Convert pixel coordinates back to PDF points (1 inch = 72 pt)
        zoom = self.OCR_DPI / 72.0

        parsed_blocks: List[Dict[str, Any]] = []
        block_no = 0
        for key in sorted(lines.keys()):
            words = lines[key]
            # Merge the line into a single text string
            line_text = " ".join(w["text"] for w in words)
            cleaned = JapaneseTextProcessor.clean_japanese_text(line_text)
            if not cleaned.strip():
                continue

            # Bounding box of the entire line in PDF coordinates
            x0 = min(w["x"] for w in words) / zoom
            y0 = min(w["y"] for w in words) / zoom
            x1 = max(w["x"] + w["w"] for w in words) / zoom
            y1 = max(w["y"] + w["h"] for w in words) / zoom

            parsed_blocks.append({
                "bbox": (x0, y0, x1, y1),
                "raw_text": line_text,
                "cleaned_text": cleaned,
                "block_no": block_no,
            })
            block_no += 1

        return parsed_blocks

    # ------------------------------------------------------------------
    # Main extraction
    # ------------------------------------------------------------------

    def extract_page_data(self, page_num: int) -> Dict[str, Any]:
        """Extract structured blocks and text from a 1-indexed page.

        If ``use_ocr`` is enabled and the page has no embedded text, an
        OCR pass is performed automatically.
        """
        page = self.doc[page_num - 1]
        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)

        parsed_blocks = []
        for b in blocks:
            # block_type == 0 indicates text
            if b[6] == 0:
                raw_text = b[4]
                cleaned = JapaneseTextProcessor.clean_japanese_text(raw_text)
                if cleaned.strip():
                    parsed_blocks.append({
                        "bbox": (b[0], b[1], b[2], b[3]),
                        "raw_text": raw_text,
                        "cleaned_text": cleaned,
                        "block_no": b[5]
                    })

        # Fallback to OCR when no text was found and OCR is enabled
        if not parsed_blocks and self.use_ocr and page_num not in self._ocr_checked:
            self._ocr_checked.add(page_num)
            try:
                parsed_blocks = self._ocr_page_blocks(page_num)
            except Exception as exc:
                print(f"  [OCR] Failed on page {page_num}: {exc}")

        return {
            "page_num": page_num,
            "rect": (page.rect.width, page.rect.height),
            "blocks": parsed_blocks
        }


class PDFDocumentBuilder:
    """Builds a formatted English PDF document from translated content using ReportLab."""

    @staticmethod
    def build_document_pdf(output_path: str, pages_data: List[Dict[str, Any]], title: str = "Translated Document"):
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable
        )
        from reportlab.pdfgen import canvas

        class NumberedCanvas(canvas.Canvas):
            """Two-pass canvas to add dynamic page counts (Page X of Y)."""
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._saved_page_states = []

            def showPage(self):
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                num_pages = len(self._saved_page_states)
                for state in self._saved_page_states:
                    self.__dict__.update(state)
                    self.draw_page_number(num_pages)
                    super().showPage()
                super().save()

            def draw_page_number(self, page_count: int):
                self.saveState()
                self.setFont("Helvetica", 9)
                self.setFillColor(colors.HexColor("#666666"))
                
                # Header
                self.drawString(54, 11 * 72 - 36, title)
                self.setStrokeColor(colors.HexColor("#E0E0E0"))
                self.setLineWidth(0.5)
                self.line(54, 11 * 72 - 42, 8.5 * 72 - 54, 11 * 72 - 42)
                
                # Footer
                page_str = f"Page {self._pageNumber} of {page_count}"
                self.drawRightString(8.5 * 72 - 54, 36, page_str)
                self.drawString(54, 36, "Translated from Japanese (Local Neural Translation)")
                self.line(54, 48, 8.5 * 72 - 54, 48)
                self.restoreState()

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54
        )

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1A202C"),
            spaceAfter=12
        )

        page_heading_style = ParagraphStyle(
            'PageHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=14,
            spaceAfter=6
        )

        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#2D3748"),
            spaceAfter=8
        )

        story = []

        # Document Header Banner
        story.append(Paragraph(title, title_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2B6CB0"), spaceAfter=14))

        for idx, page in enumerate(pages_data):
            page_num = page["page_num"]
            if idx > 0:
                story.append(PageBreak())

            story.append(Paragraph(f"--- Original Page {page_num} ---", page_heading_style))
            story.append(Spacer(1, 4))

            blocks = page.get("translated_blocks", [])
            if not blocks:
                story.append(Paragraph("<i>[No text content extracted on this page]</i>", body_style))
            else:
                for block_text in blocks:
                    if block_text.strip():
                        # Escape XML special characters for ReportLab Paragraph
                        safe_text = (
                            block_text
                            .replace('&', '&amp;')
                            .replace('<', '&lt;')
                            .replace('>', '&gt;')
                        )
                        story.append(Paragraph(safe_text, body_style))
                        story.append(Spacer(1, 4))

        doc.build(story, canvasmaker=NumberedCanvas)


class PDFOverlayBuilder:
    """Builds an overlay PDF replacing Japanese text on original pages using PyMuPDF."""

    @staticmethod
    def build_overlay_pdf(input_pdf_path: str, output_pdf_path: str, pages_data: List[Dict[str, Any]]):
        import pymupdf

        doc = pymupdf.open(input_pdf_path)
        data_by_page = {p["page_num"]: p for p in pages_data}

        for page_idx, page in enumerate(doc):
            page_num = page_idx + 1
            if page_num not in data_by_page:
                continue

            page_data = data_by_page[page_num]
            blocks = page_data.get("blocks", [])
            translated_blocks = page_data.get("translated_blocks", [])

            for block, translated_text in zip(blocks, translated_blocks):
                if not translated_text.strip():
                    continue

                bbox = pymupdf.Rect(block["bbox"])
                # Redact original text area with white background
                page.draw_rect(bbox, color=None, fill=(1, 1, 1), overlay=True)

                # Insert English translation text inside bounding box
                font_size = 9.0
                page.insert_textbox(
                    bbox,
                    translated_text,
                    fontsize=font_size,
                    fontname="helv",
                    color=(0, 0, 0),
                    align=pymupdf.TEXT_ALIGN_LEFT
                )

        doc.save(output_pdf_path)
        doc.close()


def translate_pdf(
    input_path: str,
    output_path: str,
    model_name: str = "Helsinki-NLP/opus-mt-ja-en",
    mode: str = "document",
    device: str = "auto",
    batch_size: int = 8,
    pages_arg: Optional[str] = "all",
    offline_only: bool = False,
    save_text_path: Optional[str] = None,
    use_ocr: bool = False,
):
    """Main translation pipeline."""
    start_time = time.time()
    if use_ocr:
        _configure_tesseract_path()
    check_dependencies(ocr_needed=use_ocr)

    print("=" * 65)
    print("  Offline Japanese-to-English PDF Translator")
    print("=" * 65)
    print(f"Input PDF:   {input_path}")
    print(f"Output PDF:  {output_path}")
    print(f"Model:       {model_name}")
    print(f"Layout Mode: {mode}")
    print(f"Device:      {device}")
    print(f"Offline:     {offline_only}")
    print(f"OCR:         {use_ocr}")
    print("=" * 65)

    # 1. Initialize Extractor
    extractor = PDFExtractor(input_path, use_ocr=use_ocr)
    page_numbers = extractor.parse_page_range(pages_arg)
    print(f"Total document pages: {extractor.total_pages}")
    print(f"Selected pages to translate: {page_numbers}\n")

    # 2. Extract content from selected pages
    pages_data = []
    total_blocks = 0
    ocr_pages = 0
    print("Extracting text from PDF...")
    for p_num in page_numbers:
        p_data = extractor.extract_page_data(p_num)
        pages_data.append(p_data)
        total_blocks += len(p_data["blocks"])
        if use_ocr and p_data["blocks"] and not extractor.doc[p_num - 1].get_text("blocks"):
            ocr_pages += 1

    print(f"Extracted {total_blocks} text block(s) across {len(pages_data)} page(s).")
    if use_ocr:
        print(f"  (OCR was used on {ocr_pages} image-based page(s))")
    print()

    if total_blocks == 0:
        print("[Warning] No text blocks found in the selected pages.")
        return

    # 3. Load Local Translation Model
    translator = LocalTranslator(
        model_name_or_path=model_name,
        device=device,
        offline_only=offline_only
    )

    # 4. Collect all Japanese blocks for batch translation
    all_texts_to_translate = []
    block_map = []

    for p_idx, page in enumerate(pages_data):
        for b_idx, block in enumerate(page["blocks"]):
            all_texts_to_translate.append(block["cleaned_text"])
            block_map.append((p_idx, b_idx))

    # 5. Translate
    print(f"\nTranslating {len(all_texts_to_translate)} text segments...")
    translated_results = []
    
    for idx, text in enumerate(all_texts_to_translate):
        translated = translator.translate_text(text, batch_size=batch_size)
        translated_results.append(translated)
        
        progress = (idx + 1) / len(all_texts_to_translate) * 100
        print(f"\rProgress: [{idx + 1}/{len(all_texts_to_translate)}] ({progress:.1f}%)", end="", flush=True)

    print("\n\nTranslation complete!")

    # 6. Assign translated texts back to page structure
    for p in pages_data:
        p["translated_blocks"] = []

    for (p_idx, b_idx), trans in zip(block_map, translated_results):
        pages_data[p_idx]["translated_blocks"].append(trans)

    # 7. Generate Output PDF
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    base_title = os.path.splitext(os.path.basename(input_path))[0]
    doc_title = f"Translation of {base_title}"

    print(f"Generating output PDF ({mode} mode) at: {output_path}")
    if mode == "overlay":
        PDFOverlayBuilder.build_overlay_pdf(input_path, output_path, pages_data)
    else:
        PDFDocumentBuilder.build_document_pdf(output_path, pages_data, title=doc_title)

    # 8. Optionally save text transcript
    if save_text_path:
        txt_dir = os.path.dirname(os.path.abspath(save_text_path))
        if txt_dir:
            os.makedirs(txt_dir, exist_ok=True)
        with open(save_text_path, "w", encoding="utf-8") as f:
            f.write(f"# {doc_title}\n\n")
            for page in pages_data:
                f.write(f"## Original Page {page['page_num']}\n\n")
                for block in page.get("translated_blocks", []):
                    f.write(f"{block}\n\n")
        print(f"Text translation saved to: {save_text_path}")

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.2f} seconds.")
    print(f"Output saved to: {os.path.abspath(output_path)}")


def build_cli():
    """Build and parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Translate Japanese PDF documents to English using 100% local, offline neural models.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_translate.py input_ja.pdf output_en.pdf
  python pdf_translate.py -i manual_ja.pdf -o manual_en.pdf --mode document
  python pdf_translate.py input.pdf output.pdf --pages 1-5 --device cuda
  python pdf_translate.py input.pdf output.pdf --mode overlay --save-text output.txt
  python pdf_translate.py input.pdf output.pdf --model /path/to/local/model --offline
        """
    )

    # Support both positional arguments and -i/-o options
    parser.add_argument(
        "pos_input",
        nargs="?",
        help="Path to input Japanese PDF document."
    )
    parser.add_argument(
        "pos_output",
        nargs="?",
        help="Path to output English PDF document."
    )
    parser.add_argument(
        "-i", "--input",
        dest="opt_input",
        help="Path to input Japanese PDF document."
    )
    parser.add_argument(
        "-o", "--output",
        dest="opt_output",
        help="Path to output English PDF document."
    )
    parser.add_argument(
        "-m", "--model",
        default="Helsinki-NLP/opus-mt-ja-en",
        help="Hugging Face model identifier or path to local model directory. (default: Helsinki-NLP/opus-mt-ja-en)"
    )
    parser.add_argument(
        "--mode",
        choices=["document", "overlay"],
        default="document",
        help="Output PDF layout mode: 'document' (clean formatted readable doc) or 'overlay' (replace text on original layout). (default: document)"
    )
    parser.add_argument(
        "-d", "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="Device for neural translation: 'auto', 'cpu', or 'cuda'. (default: auto)"
    )
    parser.add_argument(
        "-b", "--batch-size",
        type=int,
        default=8,
        help="Batch size for sentence translation. (default: 8)"
    )
    parser.add_argument(
        "-p", "--pages",
        default="all",
        help="Pages to translate, e.g. '1,2,5-10' or 'all'. (default: all)"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Strict offline mode: ensures only local cached files are used without checking Hugging Face Hub."
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Enable OCR fallback for image-based / scanned PDFs. "
             "Requires Tesseract and pytesseract (pip install pytesseract Pillow)."
    )
    parser.add_argument(
        "--save-text",
        dest="save_text",
        help="Optional path to also save translated text as a .txt or .md file."
    )

    return parser


def main():
    parser = build_cli()
    args = parser.parse_args()

    input_file = args.opt_input or args.pos_input
    output_file = args.opt_output or args.pos_output

    if not input_file:
        parser.error("Input PDF file is required (provide as first positional argument or with -i / --input).")
    if not output_file:
        parser.error("Output PDF file is required (provide as second positional argument or with -o / --output).")

    if not os.path.exists(input_file):
        print(f"Error: Input file does not exist: {input_file}", file=sys.stderr)
        sys.exit(1)

    translate_pdf(
        input_path=input_file,
        output_path=output_file,
        model_name=args.model,
        mode=args.mode,
        device=args.device,
        batch_size=args.batch_size,
        pages_arg=args.pages,
        offline_only=args.offline,
        save_text_path=args.save_text,
        use_ocr=args.ocr,
    )


if __name__ == "__main__":
    main()
