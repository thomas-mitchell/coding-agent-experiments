"""
Build Script: Compiles all book markdown files into a single, publication-quality PDF.
Uses ReportLab with custom page templates, syntax-styled code blocks, tables, and typography.
"""

from __future__ import annotations
import os
import sys
import re
import html
import argparse
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Preformatted, Spacer, PageBreak,
    Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and draw total page count
    along with running headers and footers.
    """
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, total_pages: int) -> None:
        if self._pageNumber == 1:
            # Suppress header and footer on cover page
            return

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Running Header
        if self._pageNumber > 2:
            self.drawString(54, letter[1] - 36, "SYSTEMIC DEPTHS: Traditional Roguelike Design & Emergent Gameplay")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Running Footer
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(letter[0] - 54, 36, page_str)
        self.drawString(54, 36, "Architecture & Design for Emergence in Python")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 48, letter[0] - 54, 48)

        self.restoreState()


BOOK_STRUCTURE = [
    ("Intro", [
        ("preface.md", "Preface: The Systemic Turn"),
    ]),
    ("Part I: Philosophy, Foundations & Architecture of Emergence", [
        ("part1_foundations/ch01_anatomy_of_emergence.md", "Chapter 1: The Anatomy of Emergence in Roguelikes"),
        ("part1_foundations/ch02_architecture_interconnected_systems.md", "Chapter 2: Architectural Patterns for Interconnected Systems"),
    ]),
    ("Part II: The Reactive World - Space, Materials & Physics", [
        ("part2_reactive_world/ch03_spatial_models_vision.md", "Chapter 3: Spatial Models, Layered Topologies & Vision"),
        ("part2_reactive_world/ch04_material_systems_cellular_automata.md", "Chapter 4: Material Systems & Cellular Automata"),
        ("part2_reactive_world/ch05_verbs_affordances_interaction_matrix.md", "Chapter 5: Verbs, Affordances & The Interaction Matrix"),
    ]),
    ("Part III: Entities, Items, Status & Magic", [
        ("part3_entities_items_magic/ch06_dynamic_entities_status_effects.md", "Chapter 6: Dynamic Entity Composition & Reactive Status Effects"),
        ("part3_entities_items_magic/ch07_emergent_items_alchemy.md", "Chapter 7: Emergent Item Systems, Alchemy & Deduction"),
        ("part3_entities_items_magic/ch08_magic_projectiles_spatial.md", "Chapter 8: Magic, Projectiles & Spatial Mechanics"),
    ]),
    ("Part IV: Intelligence, Perception & Ecology", [
        ("part4_intelligence_ecology/ch09_living_dungeon_ai_ecology.md", "Chapter 9: The Living Dungeon: AI & Ecosystems"),
        ("part4_intelligence_ecology/ch10_information_perception_agency.md", "Chapter 10: Information, Perception & Player Agency"),
    ]),
    ("Part V: Procedural Generation for Systemic Play", [
        ("part5_procgen_systemic/ch11_level_gen_tactical_affordances.md", "Chapter 11: Level Generation with Tactical Affordances"),
        ("part5_procgen_systemic/ch12_procedural_encounters_bounded_chaos.md", "Chapter 12: Procedural Encounters, Synergies & Bounded Chaos"),
    ]),
    ("Part VI: Architecture, Balance, Testing & Production", [
        ("part6_architecture_production/ch13_determinism_testing.md", "Chapter 13: Determinism, State Serialization & Replays"),
        ("part6_architecture_production/ch14_balancing_emergent_systems.md", "Chapter 14: Balancing Emergent Systems"),
        ("part6_architecture_production/ch15_reference_engine_walkthrough.md", "Chapter 15: Reference Engine Deep Dive & Extension Guide"),
    ]),
]


def format_inline_markdown(text: str) -> str:
    """Escapes HTML and converts inline markdown (bold, italic, code, math) to ReportLab XML tags."""
    # 1. Extract inline code (`...`) into placeholders
    code_placeholders: list[str] = []
    def save_code(match: re.Match[str]) -> str:
        idx = len(code_placeholders)
        code_content = html.escape(match.group(1))
        code_placeholders.append(f'<font face="Courier" color="#0F172A"><b>{code_content}</b></font>')
        return f"__INLINE_CODE_{idx}__"
    
    text = re.sub(r'`([^`]+)`', save_code, text)

    # 2. Extract inline math ($...$ or $$...$$) into placeholders
    math_placeholders: list[str] = []
    def save_math(match: re.Match[str]) -> str:
        idx = len(math_placeholders)
        math_content = html.escape(match.group(1))
        math_placeholders.append(f'<font face="Courier-Oblique" color="#0F766E">{math_content}</font>')
        return f"__INLINE_MATH_{idx}__"
    
    text = re.sub(r'\$\$([^\$]+)\$\$', save_math, text)
    text = re.sub(r'\$([^\$]+)\$', save_math, text)

    # 3. Escape XML entities on the remaining text
    text = html.escape(text)

    # 4. Convert markdown links [text](url) -> <u>text</u>
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'<font color="#2563EB"><u>\1</u></font>', text)

    # 5. Bold & Italic
    text = re.sub(r'\*\*\*([^\*]+)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*([^\*]+)\*', r'<i>\1</i>', text)
    text = re.sub(r'\b_([^_]+)_\b', r'<i>\1</i>', text)

    # 6. Restore code and math placeholders
    for idx, code_html in enumerate(code_placeholders):
        text = text.replace(f"__INLINE_CODE_{idx}__", code_html)

    for idx, math_html in enumerate(math_placeholders):
        text = text.replace(f"__INLINE_MATH_{idx}__", math_html)

    return text


def create_code_block(code_text: str, language: str = "") -> Table:
    """Wraps code snippets into a beautifully styled syntax card with background and accent bar."""
    lang_display = language.upper() if language else "CODE"

    # Header row with language tag
    header_para = Paragraph(
        f'<font face="Helvetica-Bold" size="7" color="#64748B">{lang_display}</font>',
        ParagraphStyle("CodeHeader", fontName="Helvetica-Bold", fontSize=7, leading=9)
    )

    # Clean code formatting
    lines = code_text.strip("\n").split("\n")
    formatted_lines: list[str] = []
    for line in lines:
        escaped = html.escape(line)
        # Highlight comments
        if escaped.lstrip().startswith("#"):
            formatted_lines.append(f'<font color="#64748B"><i>{escaped}</i></font>')
        else:
            formatted_lines.append(escaped)

    code_body = "<br/>".join(formatted_lines)
    code_para = Paragraph(
        f'<font face="Courier" size="8" color="#0F172A">{code_body}</font>',
        ParagraphStyle("CodeText", fontName="Courier", fontSize=8, leading=10.5)
    )

    table_data = [
        [header_para],
        [code_para]
    ]

    t = Table(table_data, colWidths=[letter[0] - 108])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('LINELEFT', (0, 0), (0, -1), 3.5, colors.HexColor("#0284C7")),  # Sky blue accent
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, 1), 2),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 6),
    ]))
    return t


def create_blockquote(quote_text: str) -> Table:
    """Wraps blockquotes and callout notes with light tint and left accent bar."""
    clean_text = re.sub(r'^>\s*', '', quote_text, flags=re.MULTILINE)
    formatted = format_inline_markdown(clean_text.strip())
    p = Paragraph(
        f'<font face="Helvetica-Oblique" size="9.5" color="#334155">{formatted}</font>',
        ParagraphStyle("QuoteStyle", fontName="Helvetica-Oblique", fontSize=9.5, leading=13.5)
    )
    t = Table([[p]], colWidths=[letter[0] - 108])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),  # Soft blue tint
        ('LINELEFT', (0, 0), (0, -1), 3.0, colors.HexColor("#2563EB")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#DBEAFE")),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def create_markdown_table(rows: list[list[str]]) -> Table:
    """Converts markdown table rows into a styled ReportLab Table."""
    if not rows:
        return Table([[""]])

    num_cols = len(rows[0])
    avail_width = letter[0] - 108
    col_width = avail_width / num_cols

    table_data: list[list[Paragraph]] = []
    for r_idx, row in enumerate(rows):
        row_paras: list[Paragraph] = []
        is_header = (r_idx == 0)
        for cell in row:
            cell_fmt = format_inline_markdown(cell.strip())
            if is_header:
                p = Paragraph(
                    f'<b><font face="Helvetica-Bold" size="8.5" color="#FFFFFF">{cell_fmt}</font></b>',
                    ParagraphStyle("TH", fontName="Helvetica-Bold", fontSize=8.5, leading=11, alignment=0)
                )
            else:
                p = Paragraph(
                    f'<font face="Helvetica" size="8.5" color="#1E293B">{cell_fmt}</font>',
                    ParagraphStyle("TD", fontName="Helvetica", fontSize=8.5, leading=11, alignment=0)
                )
            row_paras.append(p)
        table_data.append(row_paras)

    t = Table(table_data, colWidths=[col_width] * num_cols)
    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),  # Header deep slate
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]

    for r in range(1, len(rows)):
        bg = colors.HexColor("#F8FAFC") if r % 2 == 1 else colors.HexColor("#FFFFFF")
        style_commands.append(('BACKGROUND', (0, r), (-1, r), bg))

    t.setStyle(TableStyle(style_commands))
    return t


def parse_markdown_file(filepath: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    """Parses a markdown chapter file into a list of ReportLab Flowables."""
    flowables: list[Any] = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # 1. Blank line
        if not line.strip():
            i += 1
            continue

        # 2. Code block (```)
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip()
            code_lines: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # Skip closing ```
            flowables.append(Spacer(1, 4))
            flowables.append(create_code_block("\n".join(code_lines), language=lang))
            flowables.append(Spacer(1, 6))
            continue

        # 3. Blockquote (> ...)
        if line.strip().startswith(">"):
            quote_lines: list[str] = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i])
                i += 1
            flowables.append(Spacer(1, 4))
            flowables.append(create_blockquote("\n".join(quote_lines)))
            flowables.append(Spacer(1, 6))
            continue

        # 4. Table (| col1 | col2 |)
        if line.strip().startswith("|") and line.strip().endswith("|"):
            table_lines: list[str] = []
            while i < n and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                # Skip divider line | --- | --- |
                if not re.match(r'^\|(\s*:?-+:?\s*\|)+$', lines[i].strip()):
                    raw_cells = [c for c in lines[i].strip().split("|")[1:-1]]
                    table_lines.append(raw_cells)
                i += 1
            if table_lines:
                flowables.append(Spacer(1, 4))
                flowables.append(create_markdown_table(table_lines))
                flowables.append(Spacer(1, 6))
            continue

        # 5. Horizontal rule (---)
        if line.strip() in ("---", "***", "___"):
            flowables.append(Spacer(1, 6))
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceBefore=4, spaceAfter=8))
            i += 1
            continue

        # 6. Headings (#, ##, ###, ####)
        if line.startswith("# "):
            title = format_inline_markdown(line[2:].strip())
            # Chapter header with top accent bar
            flowables.append(HRFlowable(width="100%", thickness=3, color=colors.HexColor("#0284C7"), spaceAfter=10))
            flowables.append(Paragraph(title, styles["ChapterHeading"]))
            flowables.append(Spacer(1, 8))
            i += 1
            continue
        elif line.startswith("## "):
            title = format_inline_markdown(line[3:].strip())
            flowables.append(Spacer(1, 8))
            flowables.append(Paragraph(title, styles["SectionHeading"]))
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceAfter=6))
            i += 1
            continue
        elif line.startswith("### "):
            title = format_inline_markdown(line[4:].strip())
            flowables.append(Spacer(1, 6))
            flowables.append(Paragraph(title, styles["SubSectionHeading"]))
            flowables.append(Spacer(1, 3))
            i += 1
            continue
        elif line.startswith("#### "):
            title = format_inline_markdown(line[5:].strip())
            flowables.append(Spacer(1, 4))
            flowables.append(Paragraph(title, styles["SubSubSectionHeading"]))
            flowables.append(Spacer(1, 2))
            i += 1
            continue

        # 7. Lists (- or * or 1.)
        if re.match(r'^\s*[\-\*]\s+', line):
            list_text = re.sub(r'^\s*[\-\*]\s+', '', line)
            fmt = format_inline_markdown(list_text)
            flowables.append(Paragraph(f'<font color="#0284C7">&bull;</font>  {fmt}', styles["BulletItem"]))
            i += 1
            continue
        elif re.match(r'^\s*\d+\.\s+', line):
            num_match = re.match(r'^\s*(\d+\.)\s+(.*)', line)
            if num_match:
                num_str, rest = num_match.groups()
                fmt = format_inline_markdown(rest)
                flowables.append(Paragraph(f'<b><font color="#0284C7">{num_str}</font></b> {fmt}', styles["NumberedItem"]))
            i += 1
            continue

        # 8. Regular paragraph (accumulate multi-line paragraphs)
        para_lines = [line]
        i += 1
        while i < n and lines[i].strip() and not lines[i].startswith(("#", ">", "```", "|", "- ", "* ", "1.", "2.", "3.", "---")):
            para_lines.append(lines[i])
            i += 1

        raw_para = " ".join(para_lines).strip()
        if raw_para:
            fmt_para = format_inline_markdown(raw_para)
            flowables.append(Paragraph(fmt_para, styles["Body"]))
            flowables.append(Spacer(1, 5))

    return flowables


def build_book_pdf(output_pdf_name: str = "Systemic_Depths_Roguelike_Design.pdf") -> str:
    """Builds the complete book PDF document."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    book_dir = os.path.join(base_dir, "book")
    output_path = os.path.join(base_dir, output_pdf_name)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    # Styles
    styles: dict[str, ParagraphStyle] = {
        "CoverTitle": ParagraphStyle(
            "CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            textColor=colors.HexColor("#0F172A"),
            alignment=1,  # Centered
        ),
        "CoverSubtitle": ParagraphStyle(
            "CoverSubtitle",
            fontName="Helvetica-Oblique",
            fontSize=14,
            leading=19,
            textColor=colors.HexColor("#0284C7"),
            alignment=1,
        ),
        "CoverMeta": ParagraphStyle(
            "CoverMeta",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"),
            alignment=1,
        ),
        "ChapterHeading": ParagraphStyle(
            "ChapterHeading",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=23,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=0,
            spaceAfter=6,
        ),
        "SectionHeading": ParagraphStyle(
            "SectionHeading",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=10,
            spaceAfter=2,
            keepWithNext=True,
        ),
        "SubSectionHeading": ParagraphStyle(
            "SubSectionHeading",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#334155"),
            spaceBefore=8,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "SubSubSectionHeading": ParagraphStyle(
            "SubSubSectionHeading",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#475569"),
            spaceBefore=6,
            spaceAfter=2,
            keepWithNext=True,
        ),
        "Body": ParagraphStyle(
            "Body",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#1E293B"),
            alignment=4,  # Justified
        ),
        "BulletItem": ParagraphStyle(
            "BulletItem",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#1E293B"),
            leftIndent=15,
            firstLineIndent=-10,
        ),
        "NumberedItem": ParagraphStyle(
            "NumberedItem",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#1E293B"),
            leftIndent=15,
            firstLineIndent=-10,
        ),
        "TOCTitle": ParagraphStyle(
            "TOCTitle",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            alignment=0,
            spaceAfter=8,
        ),
        "TOCPart": ParagraphStyle(
            "TOCPart",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#0284C7"),
            spaceBefore=6,
            spaceAfter=2,
        ),
        "TOCItem": ParagraphStyle(
            "TOCItem",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
            leftIndent=12,
        ),
    }

    story: list[Any] = []

    # =========================================================================
    # 1. COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 100))
    story.append(HRFlowable(width="100%", thickness=4, color=colors.HexColor("#0284C7"), spaceAfter=20))
    story.append(Paragraph("SYSTEMIC DEPTHS", styles["CoverTitle"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Designing & Architecting Emergent Traditional Roguelikes", styles["CoverSubtitle"]))
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=30))
    story.append(Spacer(1, 80))

    meta_text = """
    <b>A Comprehensive Practitioner's Guide</b><br/>
    Rule Composition, Spatial Topologies, Cellular Dynamics, & Autonomous AI in Python<br/><br/>
    <i>Google DeepMind Agentic Engineering</i><br/>
    2026 Edition
    """
    story.append(Paragraph(meta_text, styles["CoverMeta"]))
    story.append(PageBreak())

    # =========================================================================
    # 2. TABLE OF CONTENTS
    # =========================================================================
    story.append(Paragraph("Table of Contents", styles["TOCTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    for part_title, chapters in BOOK_STRUCTURE:
        if part_title != "Intro":
            story.append(Paragraph(part_title, styles["TOCPart"]))
        for rel_path, title in chapters:
            story.append(Paragraph(f'<font color="#0284C7">&bull;</font> {title}', styles["TOCItem"]))
        story.append(Spacer(1, 4))

    story.append(PageBreak())

    # =========================================================================
    # 3. CHAPTERS (Each starting on a fresh page)
    # =========================================================================
    total_chapters = sum(len(chaps) for _, chaps in BOOK_STRUCTURE)
    chap_count = 0

    for part_title, chapters in BOOK_STRUCTURE:
        for rel_path, chapter_title in chapters:
            chap_count += 1
            full_path = os.path.join(book_dir, rel_path)
            if not os.path.exists(full_path):
                print(f"Warning: Chapter file not found: {full_path}")
                continue

            chapter_flowables = parse_markdown_file(full_path, styles)
            story.extend(chapter_flowables)

            # Ensure page break after each chapter except the final one
            if chap_count < total_chapters:
                story.append(PageBreak())

    # Build PDF with two-pass NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile roguelike design book markdown files into a PDF.")
    parser.add_argument("--output", "-o", default="Systemic_Depths_Roguelike_Design.pdf", help="Output PDF filename")
    args = parser.parse_args()

    out_pdf = build_book_pdf(args.output)
    print(f"Successfully compiled book PDF: {out_pdf}")


if __name__ == "__main__":
    main()
