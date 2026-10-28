import path from "node:path";
import dotenv from "dotenv";

import {
  checkGitVersion,
  computeDrift,
  localeOf,
  summarizeDrift,
  syncClone,
  validateLocales,
} from "./lib/drift.js";
import { OWNER, parseLocales, REPO, run, writeJson } from "./lib/github.js";

const OUTPUT_FILE = "drift.json";
// Under data/, which git ignores
export const DEFAULT_CLONE_DIR = "data/.cache/opentelemetry.io";

/**
 * Build the drift dataset written to data/drift.json
 * @param {object} drift - Result of computeDrift
 * @param {string[]} locales - Language codes, in output order
 * @param {Date} date - When the report was computed
 * @returns {object} - { repo, head, generated_at, en_pages, languages, pages }
 */
export function buildDataset({ head, enPages, report }, locales, date) {
  return {
    repo: `${OWNER}/${REPO}`,
    head,
    generated_at: date.toISOString(),
    en_pages: enPages,
    languages: summarizeDrift(report, locales),
    pages: [...report].map(([page, { status, sha, patched }]) => ({
      lang: localeOf(page),
      path: page,
      status,
      pinned_sha: sha,
      patched,
    })),
  };
}

function seconds(fromMs) {
  return ((performance.now() - fromMs) / 1000).toFixed(1);
}

async function main() {
  // No GitHub token is needed: the repository is cloned anonymously
  dotenv.config({ quiet: true });
  const locales = validateLocales(parseLocales(process.env.LANGS));
  const dir = path.resolve(process.env.CLONE_DIR || DEFAULT_CLONE_DIR);
  const url = `https://github.com/${OWNER}/${REPO}.git`;

  await checkGitVersion();

  console.log(`\nMeasuring translation drift for: ${locales.join(", ")}`);
  console.log(`Clone of ${OWNER}/${REPO}: ${dir}\n`);

  const syncStart = performance.now();
  const action = await syncClone({ dir, url, locales });
  console.log(`  ${action} the clone in ${seconds(syncStart)}s`);

  const driftStart = performance.now();
  const drift = await computeDrift({ dir, locales });
  console.log(
    `  compared ${drift.report.size} pages with ${drift.head.sha.slice(0, 12)} ` +
      `in ${seconds(driftStart)}s\n`,
  );

  const dataset = buildDataset(drift, locales, new Date());
  for (const record of dataset.languages) {
    console.log(
      `  ${record.lang}: ${record.pages} pages, ${record.current} current, ` +
        `${record.drifted} drifted, ${record.unpinned} unpinned, ` +
        `${record.orphan} orphan, ${record.invalid_pin} invalid pin`,
    );
  }

  const outputPath = writeJson(OUTPUT_FILE, dataset);

  console.log(`\n✓ Done! Saved ${dataset.pages.length} pages to ${outputPath}`);
}

if (import.meta.main) {
  run(main);
}
