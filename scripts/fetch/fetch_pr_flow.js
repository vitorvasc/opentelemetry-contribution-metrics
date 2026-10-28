import { buildQuery, toContribution } from "./fetch_lang_issues.js";
import { config, createClient, run, writeJson } from "./lib/github.js";

const OUTPUT_FILE = "pr_flow.json";

/**
 * Get the day range that covers every PR the repository ever had
 * @param {string} repoCreatedAt - When the repository was created
 * @param {Date} now - Last day of the range
 * @returns {object} - { from: "YYYY-MM-DD", to: "YYYY-MM-DD" }
 */
export function allTimeRange(repoCreatedAt, now) {
  const created = new Date(repoCreatedAt);
  if (Number.isNaN(created.getTime())) {
    throw new Error(`Invalid repository creation date "${repoCreatedAt}".`);
  }

  return {
    from: created.toISOString().slice(0, 10),
    to: now.toISOString().slice(0, 10),
  };
}

async function main() {
  const { token, owner, repo, locales } = config();
  const gh = createClient({ token });

  const repository = await gh.ghFetch(`/repos/${owner}/${repo}`);
  const { from, to } = allTimeRange(repository.created_at, new Date());

  console.log(`\nStarting fetch for languages: ${locales.join(", ")}`);
  console.log(`Every PR created from ${from} to ${to}\n`);

  let records = [];
  for (const lang of locales) {
    console.log(`Fetching PRs for language: ${lang}`);
    const items = await gh.ghSearchIssues({
      query: buildQuery({ owner, repo, lang, type: "prs" }),
      dateField: "created",
      from,
      to,
    });
    console.log(`✓ Completed ${lang}: ${items.length} PRs`);
    records = records.concat(items.map((item) => toContribution(lang, item)));
  }

  const outputPath = writeJson(OUTPUT_FILE, records);

  console.log(`\n✓ Done! Saved ${records.length} PRs to ${outputPath}`);
  console.log(`Languages fetched: ${locales.join(", ")}`);
}

if (import.meta.main) {
  run(main);
}
