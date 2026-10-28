import { fetchTree, summarizeCoverage } from "./lib/coverage.js";
import { config, createClient, run, writeJson } from "./lib/github.js";

const OUTPUT_FILE = "coverage_snapshot.json";
// HEAD resolves to the default branch of the repository
const REF = "HEAD";

/**
 * Build one coverage record per language from a git tree
 * @param {Array} tree - Entries of a recursive git tree
 * @param {string[]} locales - Language codes
 * @param {Date} date - When the tree was read
 * @returns {Array} - { lang, coverage_pct, lang_files, en_files, as_of } per language
 */
export function buildSnapshot(tree, locales, date) {
  const asOf = date.toISOString().slice(0, 10);

  return locales.map((lang) => {
    const coverage = summarizeCoverage(tree, lang);
    return {
      lang,
      coverage_pct: coverage.percentage,
      lang_files: coverage.lang_files,
      en_files: coverage.en_files,
      as_of: asOf,
    };
  });
}

async function main() {
  const { token, owner, repo, locales } = config();
  const gh = createClient({ token });

  console.log(`\nFetching translation coverage for: ${locales.join(", ")}`);
  console.log(`Reading the default branch of ${owner}/${repo}\n`);

  const tree = await fetchTree(gh, { owner, repo }, REF);
  const snapshot = buildSnapshot(tree, locales, new Date());

  for (const record of snapshot) {
    console.log(
      `  ${record.lang}: ${record.coverage_pct}% ` +
        `(${record.lang_files} of ${record.en_files} pages)`,
    );
  }

  const outputPath = writeJson(OUTPUT_FILE, snapshot);

  console.log(`\n✓ Done! Saved ${snapshot.length} records to ${outputPath}`);
}

if (import.meta.main) {
  run(main);
}
