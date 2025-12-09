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
  ? process.env.LANGS.split(",").map(l => l.trim())
  : ALL_LOCALES;

async function searchLang(lang, page = 1) {
  const q = `repo:${OWNER}/${REPO} label:"lang:${lang}"`;
  const url = `https://api.github.com/search/issues?q=${encodeURIComponent(q)}&per_page=100&page=${page}`;

  try {
    const res = await fetch(url, {
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        Accept: "application/vnd.github+json"
      }
    });

    // Check rate limit
    const remaining = res.headers.get("x-ratelimit-remaining");
    const reset = res.headers.get("x-ratelimit-reset");

    if (remaining === "0") {
      const resetDate = new Date(reset * 1000);
      console.warn(`⚠️  Rate limit exceeded. Resets at ${resetDate.toLocaleString()}`);
    }

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`GitHub API error (${res.status}): ${error}`);
    }

    return res.json();
  } catch (error) {
    console.error(`Failed to fetch data for ${lang} (page ${page}):`, error.message);
    throw error;
  }
}

async function fetchLocale(lang) {
  console.log(`Fetching data for language: ${lang}`);
  let all = [];
  let page = 1;

  while (true) {
    const data = await searchLang(lang, page);
    if (!data.items || data.items.length === 0) break;

    all = all.concat(
      data.items.map(item => ({
        lang,
        number: item.number,
        title: item.title,
        created_at: item.created_at,
        closed_at: item.closed_at,
        state: item.state,
        labels: item.labels.map(l => l.name),
        url: item.html_url
      }))
    );

    console.log(`  Page ${page}: ${data.items.length} items (total: ${all.length})`);
    page++;
  }

  console.log(`✓ Completed ${lang}: ${all.length} total contributions`);
  return all;
}

async function main() {
  console.log(`\nStarting fetch for languages: ${LOCALES.join(", ")}\n`);

  let merged = [];
  for (const lang of LOCALES) {
    const data = await fetchLocale(lang);
    merged = merged.concat(data);
  }

  const outputPath = "data/lang_contributions.json";
  fs.writeFileSync(outputPath, JSON.stringify(merged, null, 2));

  console.log(`\n✓ Done! Saved ${merged.length} contributions to ${outputPath}`);
  console.log(`Languages fetched: ${LOCALES.join(", ")}`);
}

main().catch(error => {
  console.error("\n✗ Fatal error:", error.message);
  process.exit(1);
});