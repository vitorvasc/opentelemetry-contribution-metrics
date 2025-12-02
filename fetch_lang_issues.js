import fetch from "node-fetch";
import fs from "fs";

const OWNER = "open-telemetry";
const REPO = "opentelemetry.io";
const LOCALES = ["pt", "es"]; // idiomas que você quer medir
const TOKEN = process.env.GITHUB_TOKEN;

async function searchLang(lang, page = 1) {
  const q = `repo:${OWNER}/${REPO} label:"lang:${lang}"`;
  const url = `https://api.github.com/search/issues?q=${encodeURIComponent(q)}&per_page=100&page=${page}`;

  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      Accept: "application/vnd.github+json"
    }
  });

  return res.json();
}

async function fetchLocale(lang) {
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
    page++;
  }

  return all;
}

async function main() {
  let merged = [];
  for (const lang of LOCALES) {
    const data = await fetchLocale(lang);
    merged = merged.concat(data);
  }

  fs.writeFileSync("lang_contributions.json", JSON.stringify(merged, null, 2));
  console.log("Done. Saved to lang_contributions.json");
}

main();