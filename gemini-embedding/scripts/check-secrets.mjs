/**
 * Fails if anything that looks like a live credential has made it into a
 * git-tracked file. Run before committing: `npm run check:secrets`.
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";

const PATTERNS = [
  { name: "OpenAI key", re: /\bsk-[A-Za-z0-9_-]{20,}/ },
  { name: "Google API key", re: /\bAIza[0-9A-Za-z_-]{30,}/ },
  { name: "Supabase secret key", re: /\bsb_secret_[A-Za-z0-9_-]{10,}/ },
  { name: "JWT (service_role / anon key)", re: /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\./ },
];

// The template is allowed to contain the literal placeholder "sk-your-openai-key".
const ALLOWED = [/sk-your-openai-key/];

// Cached + untracked-but-not-ignored: everything a commit would actually pick up.
const tracked = execFileSync("git", ["ls-files", "--cached", "--others", "--exclude-standard"], {
  encoding: "utf8",
})
  .split("\n")
  .map((line) => line.trim())
  .filter(Boolean);

const findings = [];

for (const file of tracked) {
  let content;
  try {
    content = fs.readFileSync(file, "utf8");
  } catch {
    continue; // binary or unreadable
  }
  if (content.includes(String.fromCharCode(0))) continue; // binary

  content.split("\n").forEach((line, index) => {
    if (ALLOWED.some((allowed) => allowed.test(line))) return;
    for (const { name, re } of PATTERNS) {
      if (re.test(line)) findings.push(`${file}:${index + 1}  ${name}`);
    }
  });
}

if (findings.length > 0) {
  console.error("Possible credentials found in tracked files:\n");
  for (const finding of findings) console.error(`  ${finding}`);
  console.error("\nMove them into .env.local (which is gitignored) before committing.");
  process.exit(1);
}

const envIgnored = (() => {
  try {
    execFileSync("git", ["check-ignore", "-q", ".env.local"]);
    return true;
  } catch {
    return false;
  }
})();

if (!envIgnored) {
  console.error(".env.local is NOT gitignored - fix .gitignore before committing.");
  process.exit(1);
}

console.log(`No credentials found in ${tracked.length} tracked files; .env.local is gitignored.`);
