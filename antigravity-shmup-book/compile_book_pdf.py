#!/usr/bin/env python3
"""
compile_book_pdf.py
===================
Compiles all markdown files of 'Architecting the 2D Shmup' into a beautifully styled,
publication-grade PDF document.

Features:
- Auto-detects and orders all chapters (README, SUMMARY, ch01..ch10).
- Distinct, theme-highlighted code blocks with language pills and monospace typography.
- Clean page breaks before each chapter and major section.
- GitHub-style callout alerts ([!NOTE], [!TIP], [!IMPORTANT], [!WARNING], [!CAUTION]).
- Professional book typography, title page, headers, footers, and page numbers.
- Math rendering support via MathJax / KaTeX.
- Uses Edge/Chrome headless PDF engine for pixel-perfect printing.
"""

import os
import re
import sys
import subprocess
import argparse
from pathlib import Path

try:
    from markdown_it import MarkdownIt
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import HtmlFormatter
except ImportError as e:
    print(f"Error: Missing required Python packages ({e}).")
    print("Please install them via: pip install markdown-it-py pygments")
    sys.exit(1)


# ----------------------------------------------------------------------
# Syntax Highlighting and Markdown Parser
# ----------------------------------------------------------------------

PYGMENTS_STYLE = "monokai"
formatter = HtmlFormatter(style=PYGMENTS_STYLE, nowrap=True)

def highlight_code(code: str, lang: str, attrs: str) -> str:
    lang = lang.strip().lower() if lang else ""
    # Map common pseudocode or alias tags
    lexer_map = {
        "rust": "rust",
        "glsl": "glsl",
        "hlsl": "hlsl",
        "cpp": "cpp",
        "c": "c",
        "csharp": "csharp",
        "cs": "csharp",
        "python": "python",
        "py": "python",
        "javascript": "javascript",
        "js": "javascript",
        "json": "json",
        "mermaid": "text",
        "pseudocode": "rust", # Rust lexer colors typed pseudocode excellently
        "pseudo": "rust",
        "bash": "bash",
        "sh": "bash",
    }
    
    lexer_name = lexer_map.get(lang, lang)
    try:
        if lexer_name:
            lexer = get_lexer_by_name(lexer_name)
        else:
            lexer = guess_lexer(code)
    except Exception:
        lexer = get_lexer_by_name("text")

    highlighted = highlight(code, lexer, formatter)
    display_lang = (lang if lang else "code").upper()
    
    return f"""<div class="code-container">
    <div class="code-header">
        <span class="code-lang-pill">{display_lang}</span>
        <span class="code-dot red"></span>
        <span class="code-dot yellow"></span>
        <span class="code-dot green"></span>
    </div>
    <pre class="code-body"><code>{highlighted}</code></pre>
</div>"""

md_parser = MarkdownIt("gfm-like", {
    "highlight": highlight_code,
    "linkify": False,
    "html": True,
    "typographer": True
})


# ----------------------------------------------------------------------
# Post-Processing: Callouts, Clean Links, and Math Protection
# ----------------------------------------------------------------------

def transform_github_alerts(html: str) -> str:
    """Transforms blockquote GitHub alerts (> [!NOTE], etc.) into styled callout divs."""
    alert_types = {
        "NOTE": ("note", "📘", "Note"),
        "TIP": ("tip", "💡", "Tip"),
        "IMPORTANT": ("important", "📌", "Important"),
        "WARNING": ("warning", "⚠️", "Warning"),
        "CAUTION": ("caution", "🛑", "Caution"),
    }
    
    for tag, (css_class, icon, title) in alert_types.items():
        pattern = re.compile(
            rf'<blockquote>\s*<p>\s*\[!{tag}\]\s*(?:<br\s*/?>)?\s*(.*?)\s*</p>\s*</blockquote>',
            re.DOTALL | re.IGNORECASE
        )
        def repl(match):
            content = match.group(1)
            return f"""<div class="callout callout-{css_class}">
                <div class="callout-title"><span class="callout-icon">{icon}</span> {title}</div>
                <div class="callout-content">{content}</div>
            </div>"""
        html = pattern.sub(repl, html)
        
    return html

def sanitize_links(html: str) -> str:
    """Converts file:// and local markdown links into internal anchor links."""
    # Convert file:///.../ch0X_...md#anchor -> #anchor
    html = re.sub(r'href="file:///[^"]*?#(.*?)"', r'href="#\1"', html)
    # Convert file:///.../ch0X_...md -> #ch0X
    def repl_file(match):
        path = match.group(1)
        fname = Path(path).stem
        return f'href="#{fname}"'
    html = re.sub(r'href="file:///[^"]*?/([a-zA-Z0-9_\-]+)\.md"', repl_file, html)
    # Convert relative ch0X.md links
    html = re.sub(r'href="([a-zA-Z0-9_\-]+)\.md#(.*?)"', r'href="#\2"', html)
    html = re.sub(r'href="([a-zA-Z0-9_\-]+)\.md"', r'href="#\1"', html)
    return html


# ----------------------------------------------------------------------
# CSS Styling & HTML Template
# ----------------------------------------------------------------------

def get_css() -> str:
    pygments_css = formatter.get_style_defs('.code-body')
    return f"""
/* ==========================================================================
   CSS PRINT & BOOK STYLING FOR "ARCHITECTING THE 2D SHMUP"
   ========================================================================== */

@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@300;400;500;600;700;800&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&display=swap');

@page {{
    size: A4 portrait;
    margin: 24mm 18mm 24mm 18mm;
    @bottom-center {{
        content: counter(page);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 9pt;
        font-weight: 500;
        color: #718096;
    }}
    @top-right {{
        content: "Architecting the 2D Shmup";
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 8pt;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #a0aec0;
    }}
}}

@page:first {{
    margin: 0;
    @bottom-center {{ content: none; }}
    @top-right {{ content: none; }}
}}

:root {{
    --primary: #4f46e5;
    --primary-light: #eef2ff;
    --primary-dark: #3730a3;
    --accent: #06b6d4;
    --text: #1e293b;
    --text-muted: #64748b;
    --bg: #ffffff;
    --card-bg: #f8fafc;
    --border: #e2e8f0;
    --code-bg: #181825;
    --code-header-bg: #11111b;
}}

* {{
    box-sizing: border-box;
}}

body {{
    font-family: 'Newsreader', Georgia, 'Times New Roman', serif;
    font-size: 11pt;
    line-height: 1.68;
    color: var(--text);
    background-color: var(--bg);
    margin: 0;
    padding: 0;
    -webkit-font-smoothing: antialiased;
}}

/* Headings */
h1, h2, h3, h4, h5, h6 {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #0f172a;
    font-weight: 700;
    line-height: 1.25;
    margin-top: 1.6em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    break-after: avoid;
}}

h1 {{
    font-size: 22pt;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #1e1b4b;
    border-bottom: 2.5px solid var(--primary);
    padding-bottom: 8px;
    margin-top: 0;
}}

h2 {{
    font-size: 15pt;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: #312e81;
    border-bottom: 1px solid var(--border);
    padding-bottom: 4px;
    margin-top: 1.8em;
}}

h3 {{
    font-size: 12.5pt;
    font-weight: 600;
    color: #4338ca;
    margin-top: 1.4em;
}}

h4 {{
    font-size: 11pt;
    font-weight: 600;
    color: #475569;
}}

p {{
    margin-top: 0;
    margin-bottom: 1em;
    text-align: justify;
    text-justify: inter-word;
}}

a {{
    color: var(--primary);
    text-decoration: none;
}}

a:hover {{
    text-decoration: underline;
}}

/* Chapter & Section Page Breaks */
.chapter {{
    page-break-before: always;
    break-before: page;
    padding-top: 10px;
}}

.no-break {{
    page-break-inside: avoid;
    break-inside: avoid;
}}

/* Cover Page */
.cover-page {{
    page-break-before: avoid;
    page-break-after: always;
    break-after: page;
    height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 60mm 25mm 40mm 25mm;
    background: linear-gradient(145deg, #0f172a 0%, #1e1b4b 60%, #312e81 100%);
    color: #ffffff;
    text-align: left;
}}

.cover-badge {{
    display: inline-block;
    font-family: 'Inter', sans-serif;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 5px 14px;
    border-radius: 9999px;
    margin-bottom: 20px;
}}

.cover-title {{
    font-family: 'Inter', sans-serif;
    font-size: 34pt;
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.03em;
    color: #ffffff;
    margin: 0 0 15px 0;
    border: none;
    padding: 0;
}}

.cover-subtitle {{
    font-family: 'Newsreader', Georgia, serif;
    font-style: italic;
    font-size: 16pt;
    line-height: 1.4;
    color: #cbd5e1;
    margin: 0 0 40px 0;
    font-weight: 400;
}}

.cover-footer {{
    border-top: 1px solid rgba(255, 255, 255, 0.15);
    padding-top: 20px;
    font-family: 'Inter', sans-serif;
    font-size: 9.5pt;
    color: #94a3b8;
    display: flex;
    justify-content: space-between;
}}

/* Distinct Code Blocks */
.code-container {{
    margin: 1.4em 0;
    border-radius: 8px;
    background-color: var(--code-bg);
    border: 1px solid #313244;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    overflow: hidden;
    page-break-inside: avoid;
    break-inside: avoid;
}}

.code-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 14px;
    background-color: var(--code-header-bg);
    border-bottom: 1px solid #262638;
}}

.code-lang-pill {{
    font-family: 'Fira Code', monospace;
    font-size: 7.5pt;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: #89b4fa;
    background: rgba(137, 180, 250, 0.12);
    padding: 2px 8px;
    border-radius: 4px;
    border: 1px solid rgba(137, 180, 250, 0.2);
}}

.code-dot {{
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-left: 4px;
}}
.code-dot.red {{ background: #f38ba8; }}
.code-dot.yellow {{ background: #f9e2af; }}
.code-dot.green {{ background: #a6e3a1; }}

.code-body {{
    margin: 0;
    padding: 14px 16px;
    overflow-x: auto;
    font-family: 'Fira Code', 'Consolas', 'Cascadia Code', monospace;
    font-size: 8.5pt;
    line-height: 1.55;
    color: #cdd6f4;
    background-color: var(--code-bg);
}}

.code-body code {{
    font-family: inherit;
    font-size: inherit;
    background: none !important;
    padding: 0 !important;
    border: none !important;
    color: inherit;
}}

/* Inline Code */
code {{
    font-family: 'Fira Code', 'Consolas', monospace;
    font-size: 8.8pt;
    background-color: #f1f5f9;
    color: #4338ca;
    padding: 2px 5px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
}}

/* Callout Alerts */
.callout {{
    margin: 1.3em 0;
    padding: 12px 16px;
    border-radius: 6px;
    border-left: 4px solid;
    page-break-inside: avoid;
    break-inside: avoid;
    font-size: 10pt;
    line-height: 1.55;
}}

.callout-title {{
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 10pt;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}}

.callout-note {{ background: #f0fdf4; border-color: #16a34a; color: #166534; }}
.callout-note .callout-title {{ color: #15803d; }}

.callout-tip {{ background: #f0fdfa; border-color: #0d9488; color: #115e59; }}
.callout-tip .callout-title {{ color: #0f766e; }}

.callout-important {{ background: #eef2ff; border-color: #6366f1; color: #3730a3; }}
.callout-important .callout-title {{ color: #4338ca; }}

.callout-warning {{ background: #fffbeb; border-color: #d97706; color: #92400e; }}
.callout-warning .callout-title {{ color: #b45309; }}

.callout-caution {{ background: #fef2f2; border-color: #dc2626; color: #991b1b; }}
.callout-caution .callout-title {{ color: #b91c1c; }}

/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1.4em 0;
    font-family: 'Inter', sans-serif;
    font-size: 9pt;
    line-height: 1.45;
    page-break-inside: avoid;
    break-inside: avoid;
}}

th, td {{
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border);
}}

th {{
    background-color: #f1f5f9;
    font-weight: 700;
    color: #1e293b;
    border-bottom: 2px solid #cbd5e1;
}}

tr:nth-child(even) td {{
    background-color: #f8fafc;
}}

/* Blockquotes */
blockquote {{
    margin: 1.2em 0;
    padding: 8px 16px;
    border-left: 3px solid var(--primary);
    background-color: #f8fafc;
    color: #475569;
    font-style: italic;
    page-break-inside: avoid;
    break-inside: avoid;
}}

hr {{
    border: none;
    border-top: 1px solid var(--border);
    margin: 2em 0;
}}

ul, ol {{
    margin-top: 0;
    margin-bottom: 1em;
    padding-left: 1.5em;
}}

li {{
    margin-bottom: 0.35em;
}}

/* Pygments Token Colors */
{pygments_css}
"""


def build_full_html(body_content: str) -> str:
    css = get_css()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Architecting the 2D Shmup</title>
    <style>
{css}
    </style>
    <!-- MathJax for TeX equations -->
    <script>
    window.MathJax = {{
        tex: {{
            inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
            displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
        }},
        svg: {{ fontCache: 'global' }}
    }};
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
</head>
<body>

<!-- Cover Page -->
<div class="cover-page">
    <div>
        <div class="cover-badge">Engine Architecture & Game Design</div>
        <h1 class="cover-title">Architecting the<br>2D Shmup</h1>
        <div class="cover-subtitle">Systems, Choreography, and Engine Design for High-Performance Scrolling Shooters</div>
    </div>
    <div class="cover-footer">
        <div>An Engineering Reference Handbook</div>
        <div>First Edition • 2026</div>
    </div>
</div>

{body_content}

</body>
</html>"""


# ----------------------------------------------------------------------
# Chapter Ordering and Compilation
# ----------------------------------------------------------------------

def get_ordered_book_files(book_dir: Path) -> list[Path]:
    """Returns the ordered list of markdown files in the book."""
    ordered_names = [
        "README.md",
        "SUMMARY.md",
        "ch01_anatomy_of_a_shmup.md",
        "ch02_engine_architecture_and_core_loop.md",
        "ch03_spatial_partitioning_and_collision.md",
        "ch04_bullet_choreography_and_danmaku_math.md",
        "ch05_path_following_and_formation_flight.md",
        "ch06_level_representation_and_scripting.md",
        "ch07_boss_architecture_and_choreography.md",
        "ch08_level_editor_architecture_and_tooling.md",
        "ch09_vfx_audio_and_game_feel.md",
        "ch10_synthesis_and_implementation_exercises.md",
    ]
    
    files = []
    for name in ordered_names:
        p = book_dir / name
        if p.exists():
            files.append(p)
        else:
            print(f"Warning: Expected chapter file not found: {p}")
            
    return files


def find_browser_executable() -> str | None:
    """Finds installed Microsoft Edge or Google Chrome executable on Windows."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def compile_book(book_dir: Path, output_pdf: Path, keep_html: bool = False):
    print(f"[*] Reading chapters from: {book_dir.resolve()}")
    chapter_files = get_ordered_book_files(book_dir)
    print(f"[*] Found {len(chapter_files)} chapter files to compile.")

    sections_html = []
    for i, file_path in enumerate(chapter_files):
        print(f"    [{i+1}/{len(chapter_files)}] Parsing {file_path.name}...")
        raw_text = file_path.read_text(encoding="utf-8")
        
        # Render markdown to HTML
        rendered = md_parser.render(raw_text)
        
        # Post-process callouts and links
        processed = transform_github_alerts(rendered)
        processed = sanitize_links(processed)
        
        section_id = file_path.stem
        section_html = f'<section class="chapter" id="{section_id}">\n{processed}\n</section>'
        sections_html.append(section_html)

    full_html = build_full_html("\n\n".join(sections_html))
    
    html_output_path = output_pdf.with_suffix(".html")
    html_output_path.write_text(full_html, encoding="utf-8")
    print(f"[*] Generated intermediate HTML: {html_output_path.resolve()}")

    browser_exe = find_browser_executable()
    if not browser_exe:
        print("[-] Error: Could not locate Microsoft Edge or Google Chrome for PDF printing.")
        print(f"    Intermediate HTML has been preserved at: {html_output_path}")
        sys.exit(1)

    print(f"[*] Using browser engine: {browser_exe}")
    print(f"[*] Compiling to PDF: {output_pdf.resolve()} ...")

    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer",
        f"--print-to-pdf={output_pdf.resolve()}",
        str(html_output_path.resolve()),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[-] Browser returned error code {result.returncode}")
        print(result.stderr)
        sys.exit(1)

    if not output_pdf.exists():
        print("[-] Error: PDF file was not created by the browser engine.")
        sys.exit(1)

    size_mb = output_pdf.stat().st_size / (1024 * 1024)
    print(f"[+] Successfully compiled book PDF ({size_mb:.2f} MB): {output_pdf.resolve()}")

    if not keep_html:
        html_output_path.unlink(missing_ok=True)
    else:
        print(f"[*] Kept HTML source at: {html_output_path.resolve()}")


# ----------------------------------------------------------------------
# CLI Entry Point
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compile 'Architecting the 2D Shmup' markdown files into a styled PDF."
    )
    parser.add_argument(
        "--book-dir",
        type=Path,
        default=Path(__file__).parent / "book",
        help="Directory containing the markdown files (default: ./book)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path(__file__).parent / "Architecting_the_2D_Shmup.pdf",
        help="Output PDF path (default: ./Architecting_the_2D_Shmup.pdf)",
    )
    parser.add_argument(
        "--keep-html",
        action="store_true",
        help="Keep the generated intermediate HTML file.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the PDF upon completion.",
    )

    args = parser.parse_args()

    if not args.book_dir.exists():
        print(f"[-] Error: Book directory does not exist: {args.book_dir}")
        sys.exit(1)

    compile_book(args.book_dir, args.output, keep_html=args.keep_html)

    if args.open and args.output.exists():
        os.startfile(str(args.output.resolve()))


if __name__ == "__main__":
    main()
