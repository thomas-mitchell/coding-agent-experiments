# Offline Japanese-to-English PDF Translator

A Python tool that translates Japanese PDF documents to English entirely using local machine translation models (MarianMT via Hugging Face Transformers) and local PDF libraries (`PyMuPDF` & `ReportLab`).

**100% Offline & Private:** Does not send data to or call any online translation APIs (no Google Translate API, DeepL API, OpenAI API, etc.). All model inference runs on your local CPU or GPU.

---

## Features

- **Entirely Local & Private**: Translations are generated locally via pre-trained neural sequence-to-sequence models (`Helsinki-NLP/opus-mt-ja-en` or `staka/fugumt-ja-en`).
- **CLI Interface**: Flexible command-line arguments for input/output files and options.
- **Smart Japanese Segmentation**: Handles CJK sentence boundaries (`。`, `！`, `？`, newlines) and merges broken PDF line breaks.
- **Dual PDF Layout Modes**:
  - `document` (Default): Generates a cleanly styled, multi-page English document with headers, page breaks, and running page numbers.
  - `overlay`: Replaces Japanese text in-place on top of the original PDF layout and bounding boxes.
- **Hardware Acceleration**: Automatic GPU (`cuda`) detection with CPU fallback (`--device cpu` / `--device cuda`).
- **Selective Page Translation**: Specify page ranges (e.g. `--pages 1-5,8`).
- **Sidecar Text Export**: Optionally export translated plain text / markdown using `--save-text`.
- **Strict Offline Mode**: Pass `--offline` to ensure no network checks are performed against Hugging Face.

---

## Installation

Install required dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

### Basic Translation

Both input and output filenames can be provided as positional arguments:

```bash
python pdf_translate.py input_japanese.pdf output_english.pdf
```

Or using explicit flags:

```bash
python pdf_translate.py -i input_japanese.pdf -o output_english.pdf
```

---

### Advanced Options

#### 1. Layout Modes (`--mode`)

- **Document Mode** (Default): Creates a clean, formatted English PDF document:
  ```bash
  python pdf_translate.py input.pdf output.pdf --mode document
  ```

- **Overlay Mode**: Overlays English translations onto the original PDF page layout:
  ```bash
  python pdf_translate.py input.pdf output.pdf --mode overlay
  ```

#### 2. Page Range Selection (`-p` / `--pages`)

Translate specific pages (1-indexed):
```bash
python pdf_translate.py input.pdf output.pdf --pages 1-3,5
```

#### 3. Device Selection (`-d` / `--device`)

Choose compute device:
```bash
python pdf_translate.py input.pdf output.pdf --device cuda  # GPU
python pdf_translate.py input.pdf output.pdf --device cpu   # CPU
```

#### 4. Custom Model or Local Model Directory (`-m` / `--model`)

Use another local MarianMT model or local directory:
```bash
python pdf_translate.py input.pdf output.pdf --model staka/fugumt-ja-en
python pdf_translate.py input.pdf output.pdf --model C:/models/opus-mt-ja-en --offline
```

#### 5. Save Translation as Plain Text (`--save-text`)

```bash
python pdf_translate.py input.pdf output.pdf --save-text output.txt
```

---

## Command-Line Reference

| Argument | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `input` | `-i`, `--input` | Path to input Japanese PDF file | *(Required)* |
| `output` | `-o`, `--output` | Path to output English PDF file | *(Required)* |
| `--mode` | | Output mode: `document` or `overlay` | `document` |
| `--model` | `-m` | Local model name or directory path | `Helsinki-NLP/opus-mt-ja-en` |
| `--device` | `-d` | Computation device (`auto`, `cpu`, `cuda`) | `auto` |
| `--batch-size` | `-b` | Sentence batch size for translation | `8` |
| `--pages` | `-p` | Specific pages to translate (`1-5`, `all`) | `all` |
| `--save-text` | | Optional path to export text translation | `None` |
| `--offline` | | Strict offline mode (only use local cache) | `False` |
