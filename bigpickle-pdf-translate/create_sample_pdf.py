"""
Helper script to generate a sample Japanese PDF document for testing.
Uses PyMuPDF to create a multi-page Japanese PDF.
"""

import sys
import pymupdf

def create_sample_japanese_pdf(output_path: str = "sample_japanese.pdf"):
    doc = pymupdf.open()

    # Page 1: Introduction & Technology Overview
    page1 = doc.new_page(width=595, height=842) # A4
    
    title = "人工知能と自然言語処理の進化"
    text1 = """自然言語処理（NLP）は、コンピューターが人間の言語を理解し、解釈し、生成できるようにする人工知能の一分野です。
近年の深層学習の発展により、機械翻訳の精度は劇的に向上しました。

特に、トランスフォーマーモデルの登場は、翻訳の流暢さと文脈の理解を大幅に改善しました。
今日では、多くのシステムがローカル環境で高速に実行できるようになっています。"""

    header_rect = pymupdf.Rect(50, 50, 545, 90)
    page1.insert_textbox(header_rect, title, fontsize=18, fontname="japan", color=(0.1, 0.2, 0.5))

    body_rect = pymupdf.Rect(50, 110, 545, 400)
    page1.insert_textbox(body_rect, text1, fontsize=11, fontname="japan", color=(0.1, 0.1, 0.1))

    # Page 2: Practical Applications
    page2 = doc.new_page(width=595, height=842)
    title2 = "第2章: 実用的な応用例"
    text2 = """機械翻訳技術は、多言語ドキュメントの翻訳、国際ビジネスの円滑化、学術研究の共有など、幅広い分野で活用されています。
プライバシーが重視される環境では、ローカルモデルによる翻訳が最も安全な選択肢となります。

ローカル翻訳を実行することで、インターネット接続がない環境でも安全に機密文書を翻訳できます。
これにより、データ漏洩のリスクを回避することができます。"""

    header_rect2 = pymupdf.Rect(50, 50, 545, 90)
    page2.insert_textbox(header_rect2, title2, fontsize=18, fontname="japan", color=(0.1, 0.2, 0.5))

    body_rect2 = pymupdf.Rect(50, 110, 545, 400)
    page2.insert_textbox(body_rect2, text2, fontsize=11, fontname="japan", color=(0.1, 0.1, 0.1))

    doc.save(output_path)
    doc.close()
    print(f"Sample Japanese PDF generated at: {output_path}")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "sample_japanese.pdf"
    create_sample_japanese_pdf(out)
