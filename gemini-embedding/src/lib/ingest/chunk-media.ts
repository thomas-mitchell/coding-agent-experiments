import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import ffmpegPath from "ffmpeg-static";
import type { MediaKind, PendingChunk } from "../types";
import { LIMITS } from "../media";

/**
 * Video is capped at 120s per request and audio at 180s, so long media is cut
 * into segments with ffmpeg's segment muxer. The muxer also writes a CSV list
 * with the real start/end timestamp of every segment, which becomes the chunk
 * metadata the UI uses to seek the preview player.
 *
 * Containers the embedding model accepts directly (mp4/mov, mp3/wav) are split
 * with a stream copy - fast, no quality loss. Anything else is transcoded into
 * a format the model definitely understands.
 */
const PASSTHROUGH_VIDEO = new Set(["video/mp4", "video/quicktime"]);
const PASSTHROUGH_AUDIO = new Set(["audio/mpeg", "audio/wav"]);

export async function chunkMedia(
  bytes: Buffer,
  mimeType: string,
  kind: "video" | "audio",
  filename: string,
): Promise<PendingChunk[]> {
  if (!ffmpegPath) {
    throw new Error("ffmpeg binary not found - reinstall the ffmpeg-static package");
  }

  const isVideo = kind === "video";
  const passthrough = isVideo ? PASSTHROUGH_VIDEO.has(mimeType) : PASSTHROUGH_AUDIO.has(mimeType);
  const outExt = isVideo ? "mp4" : passthrough ? (mimeType === "audio/wav" ? "wav" : "mp3") : "mp3";
  const outMime = isVideo ? "video/mp4" : outExt === "wav" ? "audio/wav" : "audio/mpeg";
  const hardCap = isVideo ? LIMITS.videoSeconds : LIMITS.audioSeconds;
  // Aim a little under the cap: a stream copy can only cut on frame boundaries,
  // so the real segment always lands slightly past the requested time.
  const target = hardCap - 5;

  const workDir = await fs.mkdtemp(path.join(os.tmpdir(), "gemini-rag-"));
  const input = path.join(workDir, `input${path.extname(filename) || (isVideo ? ".mp4" : ".mp3")}`);

  try {
    await fs.writeFile(input, bytes);

    let segments = await segmentOnce(workDir, input, outExt, target, {
      transcode: !passthrough,
      isVideo,
      attempt: 0,
    });

    // A stream copy cuts only on keyframes, so a long GOP can overshoot the
    // model's hard limit - and the model would silently ignore the excess.
    // If that happened, redo the file with keyframes forced at the boundaries.
    if (segments.some((segment) => segment.end - segment.start > hardCap)) {
      segments = await segmentOnce(workDir, input, outExt, target, {
        transcode: true,
        isVideo,
        attempt: 1,
      });
      const worst = Math.max(...segments.map((s) => s.end - s.start));
      if (worst > hardCap) {
        throw new Error(
          `Could not cut ${filename} below the ${hardCap}s ${kind} limit (longest segment ${worst.toFixed(1)}s)`,
        );
      }
    }

    if (segments.length === 0) throw new Error("ffmpeg produced no segments");

    const chunks: PendingChunk[] = [];
    for (const [index, segment] of segments.entries()) {
      const data = await fs.readFile(segment.file);
      chunks.push({
        modality: kind as MediaKind,
        content: describe(filename, kind, segment.start, segment.end, index, segments.length),
        meta: { start_sec: segment.start, end_sec: segment.end },
        media: { bytes: data, mimeType: outMime },
      });
    }
    return chunks;
  } finally {
    await fs.rm(workDir, { recursive: true, force: true }).catch(() => {});
  }
}

function describe(
  filename: string,
  kind: string,
  start: number,
  end: number,
  index: number,
  total: number,
) {
  const range = `${clock(start)}-${clock(end)}`;
  return total === 1
    ? `${kind} "${filename}" (${range})`
    : `${kind} "${filename}", segment ${index + 1} of ${total} (${range})`;
}

function clock(seconds: number) {
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

type Segment = { file: string; start: number; end: number };

/**
 * One segmenting pass. `transcode` re-encodes and pins a keyframe at every
 * segment boundary, which is the only way to guarantee exact segment lengths;
 * otherwise the streams are copied, which is far faster but cuts on keyframes.
 */
async function segmentOnce(
  workDir: string,
  input: string,
  outExt: string,
  target: number,
  options: { transcode: boolean; isVideo: boolean; attempt: number },
): Promise<Segment[]> {
  const outDir = path.join(workDir, `pass${options.attempt}`);
  await fs.mkdir(outDir, { recursive: true });
  const listPath = path.join(outDir, "segments.csv");

  let codecArgs: string[];
  if (!options.transcode) {
    codecArgs = ["-c", "copy"];
  } else if (options.isVideo) {
    codecArgs = [
      "-c:v",
      "libx264",
      "-preset",
      "veryfast",
      "-force_key_frames",
      `expr:gte(t,n_forced*${target})`,
      "-c:a",
      "aac",
    ];
  } else {
    codecArgs =
      outExt === "wav" ? ["-c:a", "pcm_s16le"] : ["-c:a", "libmp3lame", "-b:a", "128k"];
  }

  await runFfmpeg([
    "-hide_banner",
    "-loglevel",
    "error",
    "-i",
    input,
    ...codecArgs,
    "-f",
    "segment",
    "-segment_time",
    String(target),
    "-reset_timestamps",
    "1",
    "-segment_list",
    listPath,
    "-segment_list_type",
    "csv",
    path.join(outDir, `seg%04d.${outExt}`),
  ]);

  const raw = await fs.readFile(listPath, "utf8");
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [file, start, end] = line.split(",");
      return { file: path.join(outDir, file), start: Number(start) || 0, end: Number(end) || 0 };
    });
}

function runFfmpeg(args: string[]) {
  return new Promise<void>((resolve, reject) => {
    const child = spawn(ffmpegPath as unknown as string, args, { windowsHide: true });
    let stderr = "";
    child.stderr.on("data", (data) => {
      stderr += data.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited with code ${code}: ${stderr.trim().slice(0, 500)}`));
    });
  });
}
