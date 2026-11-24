import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = dirname(fileURLToPath(import.meta.url));
const raw = process.env.THINDI_API_BASE || "";
const base = raw.trim().replace(/\/+$/, "");
const body = `window.THINDI_API_BASE = ${JSON.stringify(base)};\n`;
writeFileSync(join(root, "config.js"), body, "utf8");
console.log(`Wrote config.js with THINDI_API_BASE=${JSON.stringify(base)}`);
