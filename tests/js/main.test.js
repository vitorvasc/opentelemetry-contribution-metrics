import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";

const here = path.dirname(fileURLToPath(import.meta.url));
const stub = pathToFileURL(path.join(here, "support/stub-fetch.js")).href;
const scriptsDir = path.resolve(here, "../../scripts/fetch");

/** Run a fetch script in an empty directory against stubbed API routes. */
function runScript(script, routes, { staleOutput } = {}) {
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
        STUB_ROUTES: JSON.stringify(routes),
      },
    }
  );

  const read = (name) => {
    const file = path.join(cwd, "data", name);
    return fs.existsSync(file) ? fs.readFileSync(file, "utf8") : null;
  };
  return { ...result, read };
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
      { staleOutput: "release_metrics.json" }
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
