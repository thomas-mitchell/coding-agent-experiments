import { PDFDocument } from "pdf-lib";
import { extractText, getDocumentProxy } from "unpdf";
import type { PendingChunk } from "../types";
import { LIMITS } from "../media";

/**
 * gemini-embedding-2 takes one PDF of at most 6 pages per request, so a
 * document is split into 6-page slices. Each slice is embedded natively as a
 * PDF (the model sees the page layout, not just extracted text); the extracted
 * text is kept alongside it purely so results are readable in the UI and so
 * the reasoning model has something to quote.
 */
export async function chunkPdf(bytes: Buffer, filename: string): Promise<PendingChunk[]> {
  const source = await PDFDocument.load(new Uint8Array(bytes), { ignoreEncryption: true });
  const pageCount = source.getPageCount();
  if (pageCount === 0) return [];

  const pageText = await extractPageText(bytes, pageCount);

  const chunks: PendingChunk[] = [];
  for (let start = 0; start < pageCount; start += LIMITS.pdfPages) {
    const end = Math.min(start + LIMITS.pdfPages, pageCount);

    const slice = await PDFDocument.create();
    const copied = await slice.copyPages(
      source,
      Array.from({ length: end - start }, (_, i) => start + i),
    );
    for (const page of copied) slice.addPage(page);

    const text = pageText.slice(start, end).join("\n\n").trim();
    chunks.push({
      modality: "pdf",
      content: text || `${filename}, pages ${start + 1}-${end} (no extractable text layer)`,
      meta: { page_start: start + 1, page_end: end },
      media: {
        bytes: Buffer.from(await slice.save()),
        mimeType: "application/pdf",
      },
    });
  }

  return chunks;
}

async function extractPageText(bytes: Buffer, pageCount: number): Promise<string[]> {
  try {
    const proxy = await getDocumentProxy(new Uint8Array(bytes));
    const { text } = await extractText(proxy, { mergePages: false });
    return Array.isArray(text) ? text : [];
  } catch {
    // A scanned or malformed PDF still embeds fine visually; only the snippet is lost.
    return Array.from({ length: pageCount }, () => "");
  }
}
