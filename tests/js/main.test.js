import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const stub = pathToFileURL(path.join(here, "support/stub-fetch.js")).href;
const scriptsDir = path.resolve(here, "../../scripts/fetch");

/** Run a fetch script in an empty directory against stubbed API routes. */
function runScript(script, routes, { staleOutput, env = {} } = {}) {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), "fetch-main-"));
  if (staleOutput) {
    fs.mkdirSync(path.join(cwd, "data"));
    fs.writeFileSync(path.join(cwd, "data", staleOutput), '[{"stale":true}]');
  }

  const result = spawnSync(
    process.execPath,
    ["--import", stub, path.join(scriptsDir, script)],
    {
      cwd,
      encoding: "utf8",
      env: {
        PATH: process.env.PATH,
        GITHUB_TOKEN: "test-token",
        YEAR: "2025",
        LANGS: "pt",
        ...env,
        STUB_ROUTES: JSON.stringify(routes),
        STUB_LOG: path.join(cwd, "requests.log"),
      },
    },
  );

  const read = (name) => {
    const file = path.join(cwd, "data", name);
    return fs.existsSync(file) ? fs.readFileSync(file, "utf8") : null;
  };
  // Search queries requested by the script, decoded
  const searches = () => {
    const log = path.join(cwd, "requests.log");
    if (!fs.existsSync(log)) return [];
    return fs
      .readFileSync(log, "utf8")
      .split("\n")
      .filter(Boolean)
      .map((line) => new URL(line))
      .filter((url) => url.pathname.startsWith("/search/"))
      .map((url) => url.searchParams.get("q"));
  };
  return { ...result, read, searches };
}

const emptySearch = {
  body: { total_count: 0, incomplete_results: false, items: [] },
};

describe("fetch_release_metrics main", () => {
  const release = { body: [{ tag_name: "2025.01" }] };
  const tree = {
    body: {
      truncated: false,
      tree: [
        { path: "content/en/a.md" },
        { path: "content/en/b.md" },
        { path: "content/pt/a.md" },
      ],
    },
  };

  it("writes an empty array when no release matches, replacing stale data", () => {
    const result = runScript(
      "fetch_release_metrics.js",
      { releases: { body: [{ tag_name: "2024.12" }, { tag_name: "v1.0.0" }] } },
      { staleOutput: "release_metrics.json" },
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.read("release_metrics.json"), "[]");
  });

  it("records the stats and coverage of a release month", () => {
    const result = runScript("fetch_release_metrics.js", {
      releases: release,
      tree,
      search: {
        body: {
          total_count: 1,
          incomplete_results: false,
          items: [{ id: 1, number: 5 }],
        },
      },
      files: {
        body: [
          { filename: "content/pt/a.md", status: "added", additions: 3 },
          { filename: "content/pt/b.md", status: "modified", additions: 2 },
        ],
      },
    });

    assert.equal(result.status, 0, result.stderr);
    const records = JSON.parse(result.read("release_metrics.json"));
    assert.deepEqual(records, [
      {
        lang: "pt",
        month: "2025-01",
        lines_added: 5,
        pages_added: 1,
        files_updated: 1,
        coverage_pct: 50,
        pr_count: 1,
      },
    ]);
    assert.deepEqual(Object.keys(records[0]), [
      "lang",
      "month",
      "lines_added",
      "pages_added",
      "files_updated",
      "coverage_pct",
      "pr_count",
    ]);
  });

  it("exits non-zero on a search error instead of recording zeros", () => {
    const result = runScript("fetch_release_metrics.js", {
      releases: release,
      tree,
      search: { status: 422, body: { message: "Validation Failed" } },
    });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /Fatal error.*422/s);
    assert.equal(result.read("release_metrics.json"), null);
  });

  it("exits non-zero on a PR files error", () => {
    const result = runScript("fetch_release_metrics.js", {
      releases: release,
      tree,
      search: {
        body: {
          total_count: 1,
          incomplete_results: false,
          items: [{ id: 1, number: 5 }],
        },
      },
      files: { status: 404, body: { message: "Not Found" } },
    });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /404/);
    assert.equal(result.read("release_metrics.json"), null);
  });

  it("aborts when the git tree is truncated", () => {
    const result = runScript("fetch_release_metrics.js", {
      releases: release,
      tree: { body: { truncated: true, tree: [] } },
      search: emptySearch,
    });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /truncated/);
    assert.equal(result.read("release_metrics.json"), null);
  });
});

describe("fetch_coverage main", () => {
  const tree = {
    body: {
      truncated: false,
      tree: [
        { path: "content/en/docs/a.md" },
        { path: "content/en/docs/b.md" },
        { path: "content/en/docs/c.md" },
        { path: "content/en/docs/d.md" },
        { path: "content/en/docs/logo.png" },
        { path: "content/pt/docs/a.md" },
        { path: "content/pt/docs/b.md" },
        { path: "content/es/docs/a.md" },
        { path: "content/es/docs/logo.png" },
      ],
    },
  };

  it("records the coverage of every language, zero when it has no content", () => {
    const result = runScript(
      "fetch_coverage.js",
      { tree },
      { env: { LANGS: "pt,es,ko" } },
    );

    assert.equal(result.status, 0, result.stderr);
    const records = JSON.parse(result.read("coverage_snapshot.json"));
    assert.deepEqual(
      records.map(({ as_of, ...record }) => record),
      [
        { lang: "pt", coverage_pct: 50, lang_files: 2, en_files: 4 },
        { lang: "es", coverage_pct: 25, lang_files: 1, en_files: 4 },
        { lang: "ko", coverage_pct: 0, lang_files: 0, en_files: 4 },
      ],
    );
    for (const record of records) {
      assert.match(record.as_of, /^\d{4}-\d{2}-\d{2}$/);
    }
    assert.deepEqual(Object.keys(records[0]), [
      "lang",
      "coverage_pct",
      "lang_files",
      "en_files",
      "as_of",
    ]);
  });

  it("covers every tracked language when LANGS is unset", () => {
    const result = runScript(
      "fetch_coverage.js",
      { tree },
      { env: { LANGS: "" } },
    );

    assert.equal(result.status, 0, result.stderr);
    const langs = JSON.parse(result.read("coverage_snapshot.json")).map(
      (record) => record.lang,
    );
    assert.deepEqual(langs, [
      "bn",
      "es",
      "fr",
      "ja",
      "ko",
      "pl",
      "pt",
      "ro",
      "uk",
      "zh",
    ]);
  });

  it("aborts when the git tree is truncated, keeping the previous data", () => {
    const result = runScript(
      "fetch_coverage.js",
      { tree: { body: { truncated: true, tree: [] } } },
      { staleOutput: "coverage_snapshot.json" },
    );

    assert.equal(result.status, 1);
    assert.match(result.stderr, /Fatal error.*truncated/s);
    assert.equal(result.read("coverage_snapshot.json"), '[{"stale":true}]');
  });

  it("exits non-zero when the tree request fails", () => {
    const result = runScript("fetch_coverage.js", {
      tree: { status: 404, body: { message: "Not Found" } },
    });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /404/);
    assert.equal(result.read("coverage_snapshot.json"), null);
  });
});

describe("fetch_lang_issues main", () => {
  it("writes contribution records", () => {
    const result = runScript("fetch_lang_issues.js", {
      search: {
        body: {
          total_count: 1,
          incomplete_results: false,
          items: [
            {
              id: 11,
              number: 7,
              title: "Translate",
              created_at: "2025-01-02T00:00:00Z",
              closed_at: null,
              state: "open",
              labels: [{ name: "lang:pt" }],
              html_url: "https://github.com/o/r/pull/7",
              pull_request: { merged_at: "2025-01-03T00:00:00Z" },
              user: { login: "maria", type: "User" },
            },
          ],
        },
      },
    });

    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.read("lang_contributions.json")), [
      {
        lang: "pt",
        number: 7,
        title: "Translate",
        created_at: "2025-01-02T00:00:00Z",
        closed_at: null,
        state: "open",
        labels: ["lang:pt"],
        url: "https://github.com/o/r/pull/7",
        merged_at: "2025-01-03T00:00:00Z",
        author: "maria",
        author_type: "User",
      },
    ]);
  });

  it("exits non-zero when the search fails", () => {
    const result = runScript("fetch_lang_issues.js", {
      search: { status: 422, body: { message: "Validation Failed" } },
    });

    assert.equal(result.status, 1);
    assert.equal(result.read("lang_contributions.json"), null);
  });
});

describe("fetch_pr_flow main", () => {
  const repo = { body: { created_at: "2019-05-01T10:00:00Z" } };
  const item = {
    id: 11,
    number: 7,
    title: "Translate",
    created_at: "2021-03-04T09:00:00Z",
    closed_at: "2021-03-09T09:00:00Z",
    state: "closed",
    labels: [{ name: "lang:pt" }],
    html_url: "https://github.com/o/r/pull/7",
    pull_request: { merged_at: "2021-03-09T09:00:00Z" },
    user: { login: "maria", type: "User" },
  };
  const search = {
    body: { total_count: 1, incomplete_results: false, items: [item] },
  };

  it("fetches every PR of each language since the repository was created", () => {
    const result = runScript(
      "fetch_pr_flow.js",
      { repo, search },
      { env: { LANGS: "pt,es" } },
    );

    assert.equal(result.status, 0, result.stderr);
    const records = JSON.parse(result.read("pr_flow.json"));
    assert.deepEqual(
      records.map((record) => record.lang),
      ["pt", "es"],
    );
    assert.deepEqual(records[0], {
      lang: "pt",
      number: 7,
      title: "Translate",
      created_at: "2021-03-04T09:00:00Z",
      closed_at: "2021-03-09T09:00:00Z",
      state: "closed",
      labels: ["lang:pt"],
      url: "https://github.com/o/r/pull/7",
      merged_at: "2021-03-09T09:00:00Z",
      author: "maria",
      author_type: "User",
    });

    const [pt, es] = result.searches();
    assert.match(
      pt,
      /^repo:open-telemetry\/opentelemetry\.io label:"lang:pt" is:pr created:2019-05-01\.\.\d{4}-\d{2}-\d{2}$/,
    );
    assert.match(es, /label:"lang:es" is:pr created:2019-05-01\.\./);
  });

  it("ignores YEAR and TYPE, which only apply to the other pipelines", () => {
    const result = runScript(
      "fetch_pr_flow.js",
      { repo, search },
      { env: { YEAR: "2022", TYPE: "issues" } },
    );

    assert.equal(result.status, 0, result.stderr);
    const [query] = result.searches();
    assert.match(query, /is:pr created:2019-05-01\.\./);
    assert.doesNotMatch(query, /2022|is:issue/);
  });

  it("exits non-zero when the repository cannot be read, keeping the previous data", () => {
    const result = runScript(
      "fetch_pr_flow.js",
      { repo: { status: 404, body: { message: "Not Found" } }, search },
      { staleOutput: "pr_flow.json" },
    );

    assert.equal(result.status, 1);
    assert.match(result.stderr, /Fatal error.*404/s);
    assert.deepEqual(result.searches(), []);
    assert.equal(result.read("pr_flow.json"), '[{"stale":true}]');
  });

  it("exits non-zero when the repository has no creation date", () => {
    const result = runScript("fetch_pr_flow.js", {
      repo: { body: {} },
      search,
    });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /Invalid repository creation date/);
    assert.equal(result.read("pr_flow.json"), null);
  });

  it("exits non-zero when the search fails", () => {
    const result = runScript("fetch_pr_flow.js", {
      repo,
      search: { status: 422, body: { message: "Validation Failed" } },
    });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /422/);
    assert.equal(result.read("pr_flow.json"), null);
  });
});
