import "dotenv/config";
import fetch from "node-fetch";
import fs from "fs";

const OWNER = "open-telemetry";
const REPO = "opentelemetry.io";
const ALL_LOCALES = ["bn", "es", "fr", "ja", "pt", "ro", "uk", "zh"];
const TOKEN = process.env.GITHUB_TOKEN;

// Validate GITHUB_TOKEN
if (!TOKEN) {
  console.error("Error: GITHUB_TOKEN is not set. Please check your .env file.");
  process.exit(1);
}

// Get languages from LANGS environment variable, or use all if not specified
const LOCALES = process.env.LANGS
  ? process.env.LANGS.split(",").map((l) => l.trim())
  : ALL_LOCALES;

// Filter releases by year (default: current year)
const YEAR = process.env.YEAR || new Date().getFullYear().toString();

console.log(`\nFetching release metrics for languages: ${LOCALES.join(", ")}`);
console.log(`Filtering releases for year: ${YEAR}\n`);

/**
 * Fetch all GitHub releases and filter to YYYY.MM pattern
 */
async function fetchReleases() {
  console.log("Fetching releases from GitHub...");
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/releases?per_page=100`;

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

    const releases = await res.json();

    // Filter to YYYY.MM pattern and filter by year
    const monthlyReleases = releases
      .filter((release) => /^\d{4}\.\d{2}$/.test(release.tag_name))
      .filter((release) => {
        const [releaseYear] = release.tag_name.split('.');
        return releaseYear === YEAR;
      })
      .sort((a, b) => a.tag_name.localeCompare(b.tag_name)); // oldest first

    console.log(`✓ Found ${monthlyReleases.length} monthly releases`);
    return monthlyReleases;
  } catch (error) {
    console.error(`Failed to fetch releases:`, error.message);
    throw error;
  }
}

/**
 * Parse release tag to get month date range
 * @param {string} tag - Release tag (e.g., "2025.10")
 * @returns {object} - { start: "2025-10-01", end: "2025-10-31", month: "2025-10" }
 */
function getReleaseMonth(tag) {
  const [year, month] = tag.split(".");
  const start = `${year}-${month}-01`;

  // Calculate last day of month
  const lastDay = new Date(parseInt(year), parseInt(month), 0).getDate();
  const end = `${year}-${month}-${lastDay.toString().padStart(2, "0")}`;

  return { start, end, month: `${year}-${month}` };
}

/**
 * Search for localization PRs merged in a date range
 * @param {string} lang - Language code
 * @param {string} dateStart - Start date (YYYY-MM-DD)
 * @param {string} dateEnd - End date (YYYY-MM-DD)
 * @returns {Array} - Array of PR numbers
 */
async function searchLocalizationPRs(lang, dateStart, dateEnd) {
  const query = `repo:${OWNER}/${REPO} is:pr is:merged label:lang:${lang} merged:${dateStart}..${dateEnd}`;
  const url = `https://api.github.com/search/issues?q=${encodeURIComponent(
    query
  )}&per_page=100`;

  try {
    const res = await fetch(url, {
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        Accept: "application/vnd.github+json",
      },
    });

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`Search API error (${res.status}): ${error}`);
    }

    const data = await res.json();
    const prNumbers = data.items.map((item) => item.number);

    return prNumbers;
  } catch (error) {
    console.error(
      `Failed to search PRs for ${lang} (${dateStart}..${dateEnd}):`,
      error.message
    );
    return [];
  }
}

/**
 * Get detailed stats for a PR (lines added, pages added)
 * @param {number} prNumber - PR number
 * @param {string} lang - Language code
 * @returns {object} - { lines_added, pages_added, files_updated }
 */
async function getPRStats(prNumber, lang) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/pulls/${prNumber}/files?per_page=100`;

  try {
    const res = await fetch(url, {
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        Accept: "application/vnd.github+json",
      },
    });

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`PR files API error (${res.status}): ${error}`);
    }

    const files = await res.json();

    // Filter to content/{lang}/ files only
    const langPath = `content/${lang}/`;
    const langFiles = files.filter((file) =>
      file.filename.startsWith(langPath)
    );

    // Calculate stats
    let lines_added = 0;
    let pages_added = 0;
    let files_updated = 0;

    for (const file of langFiles) {
      // Only count .md files
      if (file.filename.endsWith(".md")) {
        lines_added += file.additions || 0;

        if (file.status === "added") {
          pages_added++;
        } else if (file.status === "modified") {
          files_updated++;
        }
      }
    }

    return { lines_added, pages_added, files_updated };
  } catch (error) {
    console.error(`Failed to get stats for PR #${prNumber}:`, error.message);
    return { lines_added: 0, pages_added: 0, files_updated: 0 };
  }
}

/**
 * Calculate coverage percentage at a specific release tag
 * @param {string} lang - Language code
 * @param {string} tagName - Release tag (e.g., "2025.10")
 * @returns {object} - { percentage, lang_files, en_files }
 */
async function getCoverageAtTag(lang, tagName) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/git/trees/${tagName}?recursive=1`;

  try {
    const res = await fetch(url, {
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        Accept: "application/vnd.github+json",
      },
    });

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`Tree API error (${res.status}): ${error}`);
    }

    const data = await res.json();
    const tree = data.tree;

    // Count .md files in content/en/ and content/{lang}/
    const enFiles = tree.filter(
      (item) =>
        item.path.startsWith("content/en/") && item.path.endsWith(".md")
    ).length;

    const langFiles = tree.filter(
      (item) =>
        item.path.startsWith(`content/${lang}/`) && item.path.endsWith(".md")
    ).length;

    const percentage = enFiles > 0 ? (langFiles / enFiles) * 100 : 0;

    return {
      percentage: Math.round(percentage * 10) / 10, // Round to 1 decimal
      lang_files: langFiles,
      en_files: enFiles,
    };
  } catch (error) {
    console.error(`Failed to get coverage for ${lang} at ${tagName}:`, error.message);
    return { percentage: 0, lang_files: 0, en_files: 0 };
  }
}

/**
 * Main function
 */
async function main() {
  console.log("Starting release metrics collection...\n");

  // Fetch all monthly releases
  const releases = await fetchReleases();

  if (releases.length === 0) {
    console.log("No releases found matching criteria.");
    return;
  }

  const results = [];

  // Process each release
  for (const release of releases) {
    const tagName = release.tag_name;
    const dateRange = getReleaseMonth(tagName);

    console.log(`\n--- Processing release ${tagName} ---`);
    console.log(`Date range: ${dateRange.start} to ${dateRange.end}`);

    // Process each language
    for (const lang of LOCALES) {
      console.log(`\n  Language: ${lang}`);

      // Get all PRs for this language in this month
      const prNumbers = await searchLocalizationPRs(
        lang,
        dateRange.start,
        dateRange.end
      );
      console.log(`    Found ${prNumbers.length} PRs`);

      if (prNumbers.length === 0) {
        // Still record the month even if no PRs, to show 0 activity
        const coverage = await getCoverageAtTag(lang, tagName);

        results.push({
          lang,
          month: dateRange.month,
          lines_added: 0,
          pages_added: 0,
          files_updated: 0,
          coverage_pct: coverage.percentage,
          pr_count: 0,
        });
        continue;
      }

      // Collect stats from all PRs
      let totalLinesAdded = 0;
      let totalPagesAdded = 0;
      let totalFilesUpdated = 0;

      for (const prNum of prNumbers) {
        const stats = await getPRStats(prNum, lang);
        totalLinesAdded += stats.lines_added;
        totalPagesAdded += stats.pages_added;
        totalFilesUpdated += stats.files_updated;
      }

      // Get coverage at end of month
      const coverage = await getCoverageAtTag(lang, tagName);

      console.log(`    Lines added: ${totalLinesAdded}`);
      console.log(`    Pages added: ${totalPagesAdded}`);
      console.log(`    Files updated: ${totalFilesUpdated}`);
      console.log(`    Coverage: ${coverage.percentage}%`);

      results.push({
        lang,
        month: dateRange.month,
        lines_added: totalLinesAdded,
        pages_added: totalPagesAdded,
        files_updated: totalFilesUpdated,
        coverage_pct: coverage.percentage,
        pr_count: prNumbers.length,
      });
    }
  }

  // Save results
  const outputPath = "data/release_metrics.json";
  fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));

  console.log(`\n✓ Done! Saved ${results.length} records to ${outputPath}`);
  console.log(`Releases processed: ${releases.length}`);
  console.log(`Languages: ${LOCALES.join(", ")}`);
}

main().catch((error) => {
  console.error("\n✗ Fatal error:", error.message);
  process.exit(1);
});
