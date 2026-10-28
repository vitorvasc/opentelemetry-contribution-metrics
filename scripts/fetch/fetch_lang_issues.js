import {
  config,
  createClient,
  run,
  writeJson,
} from "./lib/github.js";

const OUTPUT_FILE = "lang_contributions.json";

/**
 * Build the search query for a language's PRs and/or issues
 * @param {object} params - { owner, repo, lang, type }
 * @returns {string} - Search query without the date qualifier
 */
export function buildQuery({ owner, repo, lang, type }) {
  let typeFilter = "";
  if (type === "prs") {
    typeFilter = " is:pr";
  } else if (type === "issues") {
    typeFilter = " is:issue";
  }
  // type === "both" means no additional filter

  return `repo:${owner}/${repo} label:"lang:${lang}"${typeFilter}`;
}

/**
 * Convert a search item to a contribution record
 * @param {string} lang - Language code
 * @param {object} item - Search API item
 * @returns {object} - Contribution record
 */
export function toContribution(lang, item) {
  return {
    lang,
    number: item.number,
    title: item.title,
    created_at: item.created_at,
    closed_at: item.closed_at,
    state: item.state,
    labels: item.labels.map((l) => l.name),
    url: item.html_url,
  };
}

async function fetchLocale(gh, { owner, repo, lang, year, type }) {
  console.log(`Fetching data for language: ${lang}`);

  const items = await gh.ghSearchIssues({
    query: buildQuery({ owner, repo, lang, type }),
    dateField: "created",
    from: `${year}-01-01`,
    to: `${year}-12-31`,
  });
  const all = items.map((item) => toContribution(lang, item));

  console.log(`✓ Completed ${lang}: ${all.length} total contributions`);
  return all;
}

async function main() {
  const { token, owner, repo, locales, year, type } = config();
  const gh = createClient({ token });

  console.log(`\nStarting fetch for languages: ${locales.join(", ")}`);
  console.log(`Filtering for year: ${year}`);
  console.log(`Type: ${type === "both" ? "PRs and issues" : type}\n`);

  let merged = [];
  for (const lang of locales) {
    const data = await fetchLocale(gh, { owner, repo, lang, year, type });
    merged = merged.concat(data);
  }

  const outputPath = writeJson(OUTPUT_FILE, merged);

  console.log(`\n✓ Done! Saved ${merged.length} contributions to ${outputPath}`);
  console.log(`Languages fetched: ${locales.join(", ")}`);
}

if (import.meta.main) {
  run(main);
}
