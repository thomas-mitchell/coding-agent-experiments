import { ingest } from "@/lib/ingest/run";

export const runtime = "nodejs";
export const maxDuration = 3600;
export const dynamic = "force-dynamic";

/**
 * POST /api/ingest - runs the embedding pipeline and streams progress as
 * server-sent events so the GUI can show per-document status live.
 */
export async function POST(request: Request) {
  const force = new URL(request.url).searchParams.get("force") === "1";
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (payload: unknown) =>
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));

      try {
        for await (const event of ingest({ force })) send(event);
      } catch (error) {
        send({
          type: "fatal",
          message: error instanceof Error ? error.message : String(error),
        });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
