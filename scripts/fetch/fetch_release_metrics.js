import {
  config,
  createClient,
  monthRange,
  run,
  writeJson,
} from "./lib/github.js";

const OUTPUT_FILE = "release_metrics.json";

/**
 * Filter releases to the YYYY.MM pattern of a year, oldest first
 * @param {Array} releases - Releases from the GitHub API
 * @param {string} year - Year to keep (e.g., "2025")
 * @returns {Array} - Monthly releases of that year
 */
export function selectMonthlyReleases(releases, year) {
  return releases
    .filter((release) => /^\d{4}\.\d{2}$/.test(release.tag_name))
    .filter((release) => release.tag_name.split(".")[0] === year)
    .sort((a, b) => a.tag_name.localeCompare(b.tag_name)); // oldest first
}

/**
 * Parse release tag to get month date range
 * @param {string} tag - Release tag (e.g., "2025.10")
 * @returns {object} - { start: "2025-10-01", end: "2025-10-31", month: "2025-10" }
 */
export function getReleaseMonth(tag) {
  const [year, month] = tag.split(".");
  return monthRange(year, parseInt(month, 10));
}

/**
 * Build the search query for a language's merged localization PRs
 * @param {object} params - { owner, repo, lang }
 * @returns {string} - Search query without the date qualifier
 */
export function buildQuery({ owner, repo, lang }) {
  return `repo:${owner}/${repo} is:pr is:merged label:lang:${lang}`;
}

/**
 * Calculate stats (lines added, pages added) from the files of a PR
 * @param {Array} files - Files changed by the PR
 * @param {string} lang - Language code
 * @returns {object} - { lines_added, pages_added, files_updated }
 */
export function summarizePRFiles(files, lang) {
  // Filter to content/{lang}/ files only
  const langPath = `content/${lang}/`;
  const langFiles = files.filter((file) => file.filename.startsWith(langPath));

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
}

/**
 * Calculate translation coverage from a git tree
 * @param {Array} tree - Entries of a recursive git tree
 * @param {string} lang - Language code
 * @returns {object} - { percentage, lang_files, en_files }
 */
export function summarizeCoverage(tree, lang) {
  // Count .md files in content/en/ and content/{lang}/
  const countMarkdown = (prefix) =>
    tree.filter(
      (item) => item.path.startsWith(prefix) && item.path.endsWith(".md")
    ).length;

  const enFiles = countMarkdown("content/en/");
  const langFiles = countMarkdown(`content/${lang}/`);
  const percentage = enFiles > 0 ? (langFiles / enFiles) * 100 : 0;

  return {
    percentage: Math.round(percentage * 10) / 10, // Round to 1 decimal
    lang_files: langFiles,
    en_files: enFiles,
  };
}

/**
 * Fetch all GitHub releases and filter to YYYY.MM pattern
 */
async function fetchReleases(gh, { owner, repo, year }) {
  console.log("Fetching releases from GitHub...");

  const releases = await gh.ghPaginate(`/repos/${owner}/${repo}/releases`);
  const monthlyReleases = selectMonthlyReleases(releases, year);

  console.log(`✓ Found ${monthlyReleases.length} monthly releases`);
  return monthlyReleases;
}

/**
 * Get the full file tree of a release tag
 */
async function fetchTree(gh, { owner, repo }, tagName) {
  const data = await gh.ghFetch(
    `/repos/${owner}/${repo}/git/trees/${tagName}?recursive=1`
  );

  if (data.truncated) {
    throw new Error(
      `Git tree for ${tagName} is truncated, coverage would be undercounted`
    );
  }
  return data.tree;
}

/**
 * Get stats for one language from the PRs merged in a date range
 */
async function fetchLanguageMonth(gh, { owner, repo }, lang, dateRange) {
  const items = await gh.ghSearchIssues({
    query: buildQuery({ owner, repo, lang }),
    dateField: "merged",
    from: dateRange.start,
    to: dateRange.end,
  });
  const prNumbers = items.map((item) => item.number);
  console.log(`    Found ${prNumbers.length} PRs`);

  const stats = { lines_added: 0, pages_added: 0, files_updated: 0 };
  for (const prNumber of prNumbers) {
    const files = await gh.ghPaginate(
      `/repos/${owner}/${repo}/pulls/${prNumber}/files`
    );
    const prStats = summarizePRFiles(files, lang);
    stats.lines_added += prStats.lines_added;
    stats.pages_added += prStats.pages_added;
    stats.files_updated += prStats.files_updated;
  }

  return { stats, prCount: prNumbers.length };
}

/**
 * Main function
 */
async function main() {
  const { token, owner, repo, locales, year } = config();
  const gh = createClient({ token });
  const repoRef = { owner, repo };

  console.log(`\nFetching release metrics for languages: ${locales.join(", ")}`);
  console.log(`Filtering releases for year: ${year}\n`);
  console.log("Starting release metrics collection...\n");

  // Fetch all monthly releases
  const releases = await fetchReleases(gh, { owner, repo, year });

  if (releases.length === 0) {
    console.log("No releases found matching criteria.");
  }

  const results = [];

  // Process each release
  for (const release of releases) {
    const tagName = release.tag_name;
    const dateRange = getReleaseMonth(tagName);

    console.log(`\n--- Processing release ${tagName} ---`);
    console.log(`Date range: ${dateRange.start} to ${dateRange.end}`);

    // Coverage is read from the same tree for every language of the tag
    const tree = await fetchTree(gh, repoRef, tagName);

    // Process each language
    for (const lang of locales) {
      console.log(`\n  Language: ${lang}`);

      const { stats, prCount } = await fetchLanguageMonth(
        gh,
        repoRef,
        lang,
        dateRange
      );
      const coverage = summarizeCoverage(tree, lang);

      console.log(`    Lines added: ${stats.lines_added}`);
      console.log(`    Pages added: ${stats.pages_added}`);
      console.log(`    Files updated: ${stats.files_updated}`);
      console.log(`    Coverage: ${coverage.percentage}%`);

      // Months without PRs are still recorded to show 0 activity
      results.push({
        lang,
        month: dateRange.month,
        lines_added: stats.lines_added,
        pages_added: stats.pages_added,
        files_updated: stats.files_updated,
        coverage_pct: coverage.percentage,
        pr_count: prCount,
      });
    }
  }

  const outputPath = writeJson(OUTPUT_FILE, results);

  console.log(`\n✓ Done! Saved ${results.length} records to ${outputPath}`);
  console.log(`Releases processed: ${releases.length}`);
  console.log(`Languages: ${locales.join(", ")}`);
}

if (import.meta.main) {
  run(main);
}
