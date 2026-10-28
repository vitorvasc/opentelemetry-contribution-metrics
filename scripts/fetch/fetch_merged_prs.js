import {
  config,
  createClient,
  monthRange,
  run,
  writeJson,
} from "./lib/github.js";

const OUTPUT_FILE = "merged_prs.json";

/**
 * Build the search query for merged PRs
 * @param {object} params - { owner, repo }
 * @returns {string} - Search query without the date qualifier
 */
export function buildQuery({ owner, repo }) {
  return `repo:${owner}/${repo} is:pr is:merged`;
}

/**
 * Convert a search item to a merged PR record
 * @param {object} item - Search API item
 * @returns {object} - { number, merged_at }
 */
export function toMergedPR(item) {
  return {
    number: item.number,
    merged_at: item.pull_request?.merged_at || item.closed_at,
  };
}

async function main() {
  const { token, owner, repo, year } = config();
  const gh = createClient({ token });

  console.log(`\nFetching merged PRs for year: ${year}`);
  console.log(
    `Using monthly date-chunking to keep searches under the API cap\n`,
  );

  const allPRs = [];

  // Process each month
  for (let month = 1; month <= 12; month++) {
    const dateRange = monthRange(year, month);
    console.log(`\n--- Month ${dateRange.month} ---`);
    console.log(`  Date range: ${dateRange.start} to ${dateRange.end}`);

    const items = await gh.ghSearchIssues({
      query: buildQuery({ owner, repo }),
      dateField: "merged",
      from: dateRange.start,
      to: dateRange.end,
    });
    const prs = items.map(toMergedPR);
    allPRs.push(...prs);

    console.log(`  ✓ Found ${prs.length} merged PRs (total: ${allPRs.length})`);
  }

  const outputPath = writeJson(OUTPUT_FILE, allPRs);

  console.log(`\n✓ Done! Saved ${allPRs.length} merged PRs to ${outputPath}`);
  console.log(`Year: ${year}`);
}

if (import.meta.main) {
  run(main);
}
