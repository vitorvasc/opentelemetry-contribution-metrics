import "dotenv/config";
import fetch from "node-fetch";
import fs from "fs";

const OWNER = "open-telemetry";
const REPO = "opentelemetry.io";
const TOKEN = process.env.GITHUB_TOKEN;

// Validate GITHUB_TOKEN
if (!TOKEN) {
  console.error("Error: GITHUB_TOKEN is not set. Please check your .env file.");
  process.exit(1);
}

// Filter by year (default: current year)
const YEAR = process.env.YEAR || new Date().getFullYear().toString();

/**
 * Get date range for a specific month
 * @param {number} month - Month (1-12)
 * @returns {object} - { start: "YYYY-MM-DD", end: "YYYY-MM-DD" }
 */
function getMonthDateRange(month) {
  const monthStr = month.toString().padStart(2, "0");
  const start = `${YEAR}-${monthStr}-01`;

  // Calculate last day of month
  const lastDay = new Date(parseInt(YEAR), month, 0).getDate();
  const end = `${YEAR}-${monthStr}-${lastDay.toString().padStart(2, "0")}`;

  return { start, end, month: `${YEAR}-${monthStr}` };
}

/**
 * Search for merged PRs in a date range with pagination
 * @param {string} dateStart - Start date (YYYY-MM-DD)
 * @param {string} dateEnd - End date (YYYY-MM-DD)
 * @param {Set} seenPRs - Set of already seen PR numbers for deduplication
 * @returns {Array} - Array of PR objects { number, merged_at }
 */
async function searchMergedPRs(dateStart, dateEnd, seenPRs) {
  const query = `repo:${OWNER}/${REPO} is:pr is:merged merged:${dateStart}..${dateEnd}`;
  const results = [];
  let page = 1;

  while (true) {
    const url = `https://api.github.com/search/issues?q=${encodeURIComponent(
      query
    )}&per_page=100&page=${page}`;

    try {
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${TOKEN}`,
          Accept: "application/vnd.github+json",
        },
      });

      // Check rate limit
      const remaining = res.headers.get("x-ratelimit-remaining");
      const reset = res.headers.get("x-ratelimit-reset");

      if (remaining === "0") {
        const resetDate = new Date(reset * 1000);
        console.warn(
          `⚠️  Rate limit exceeded. Resets at ${resetDate.toLocaleString()}`
        );
      }

      if (!res.ok) {
        const error = await res.text();
        throw new Error(`GitHub API error (${res.status}): ${error}`);
      }

      const data = await res.json();

      if (!data.items || data.items.length === 0) break;

      // Process items with deduplication
      for (const item of data.items) {
        if (!seenPRs.has(item.number)) {
          seenPRs.add(item.number);
          results.push({
            number: item.number,
            merged_at: item.pull_request?.merged_at || item.closed_at,
          });
        }
      }

      console.log(`    Page ${page}: ${data.items.length} items`);

      // Check if we've fetched all items
      if (data.items.length < 100) break;
      page++;
    } catch (error) {
      console.error(
        `Failed to search PRs (${dateStart}..${dateEnd}, page ${page}):`,
        error.message
      );
      throw error;
    }
  }

  return results;
}

/**
 * Main function
 */
async function main() {
  console.log(`\nFetching merged PRs for year: ${YEAR}`);
  console.log(`Using monthly date-chunking to avoid API limits\n`);

  const allPRs = [];
  const seenPRs = new Set();

  // Process each month
  for (let month = 1; month <= 12; month++) {
    const dateRange = getMonthDateRange(month);
    console.log(`\n--- Month ${dateRange.month} ---`);
    console.log(`  Date range: ${dateRange.start} to ${dateRange.end}`);

    const prs = await searchMergedPRs(dateRange.start, dateRange.end, seenPRs);
    allPRs.push(...prs);

    console.log(`  ✓ Found ${prs.length} merged PRs (total: ${allPRs.length})`);
  }

  // Save results
  const outputPath = "data/merged_prs.json";
  fs.writeFileSync(outputPath, JSON.stringify(allPRs, null, 2));

  console.log(`\n✓ Done! Saved ${allPRs.length} merged PRs to ${outputPath}`);
  console.log(`Year: ${YEAR}`);
}

main().catch((error) => {
  console.error("\n✗ Fatal error:", error.message);
  process.exit(1);
});
