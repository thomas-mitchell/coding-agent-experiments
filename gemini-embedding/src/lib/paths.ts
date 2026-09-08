import "server-only";
import path from "node:path";
import { env } from "./env";

/** Absolute path of the folder that holds every source document. */
export function documentsRoot() {
  return path.resolve(process.cwd(), env().DOCUMENTS_DIR);
}

/**
 * Resolve a repo-relative document path to an absolute one, refusing anything
 * that escapes the documents folder. Every filesystem read/write driven by
 * user input goes through here.
 */
export function resolveInsideRoot(relPath: string) {
  const root = documentsRoot();
  const absolute = path.resolve(root, relPath);
  const relative = path.relative(root, absolute);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`Path escapes the documents folder: ${relPath}`);
  }
  return absolute;
}

/** Normalise a filesystem path into the POSIX-style key stored in the database. */
export function toRelKey(absolute: string) {
  return path.relative(documentsRoot(), absolute).split(path.sep).join("/");
}

/** Strip anything that could redirect an upload outside the documents folder. */
export function sanitizeFilename(name: string) {
  const base = path.basename(name).replace(/[\u0000-\u001f]/g, "");
  const cleaned = base.replace(/[<>:"|?*\/]/g, "_").replace(/^\.+/, "").trim();
  return cleaned || `upload-${Date.now()}`;
}
