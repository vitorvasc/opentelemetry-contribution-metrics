import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";

import * as langIssues from "../../scripts/fetch/fetch_lang_issues.js";
import * as mergedPrs from "../../scripts/fetch/fetch_merged_prs.js";
import * as releaseMetrics from "../../scripts/fetch/fetch_release_metrics.js";

const scriptsDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../scripts/fetch"
);

describe("fetch_lang_issues", () => {
  const base = { owner: "o", repo: "r", lang: "pt" };

  it("builds a query per contribution type", () => {
    assert.equal(
      langIssues.buildQuery({ ...base, type: "both" }),
      'repo:o/r label:"lang:pt"'
    );
    assert.equal(
      langIssues.buildQuery({ ...base, type: "prs" }),
      'repo:o/r label:"lang:pt" is:pr'
    );
    assert.equal(
      langIssues.buildQuery({ ...base, type: "issues" }),
      'repo:o/r label:"lang:pt" is:issue'
    );
  });

  it("maps a search item to a contribution record", () => {
    const record = langIssues.toContribution("pt", {
      number: 7,
      title: "Translate",
      created_at: "2025-01-02T00:00:00Z",
      closed_at: null,
      state: "open",
      labels: [{ name: "lang:pt" }, { name: "sig:docs" }],
      html_url: "https://github.com/o/r/pull/7",
      extra: "ignored",
    });

    assert.deepEqual(record, {
      lang: "pt",
      number: 7,
      title: "Translate",
      created_at: "2025-01-02T00:00:00Z",
      closed_at: null,
      state: "open",
      labels: ["lang:pt", "sig:docs"],
      url: "https://github.com/o/r/pull/7",
    });
  });
});

describe("fetch_merged_prs", () => {
  it("builds the merged PR query", () => {
    assert.equal(
      mergedPrs.buildQuery({ owner: "o", repo: "r" }),
      "repo:o/r is:pr is:merged"
    );
  });

  it("uses merged_at and falls back to closed_at", () => {
    assert.deepEqual(
      mergedPrs.toMergedPR({
        number: 1,
        pull_request: { merged_at: "2025-03-01T10:00:00Z" },
        closed_at: "2025-03-02T10:00:00Z",
      }),
      { number: 1, merged_at: "2025-03-01T10:00:00Z" }
    );
    assert.deepEqual(
      mergedPrs.toMergedPR({ number: 2, closed_at: "2025-03-02T10:00:00Z" }),
      { number: 2, merged_at: "2025-03-02T10:00:00Z" }
    );
  });
});

describe("fetch_release_metrics", () => {
  it("keeps only YYYY.MM releases of the year, oldest first", () => {
    const releases = [
      { tag_name: "2025.10" },
      { tag_name: "v1.2.3" },
      { tag_name: "2025.02" },
      { tag_name: "2024.12" },
      { tag_name: "2025.1" },
      { tag_name: "2025.03.1" },
      { tag_name: "2025.09" },
    ];

    assert.deepEqual(
      releaseMetrics.selectMonthlyReleases(releases, "2025").map((r) => r.tag_name),
      ["2025.02", "2025.09", "2025.10"]
    );
    assert.deepEqual(releaseMetrics.selectMonthlyReleases([], "2025"), []);
  });

  it("derives the month range from a tag", () => {
    assert.deepEqual(releaseMetrics.getReleaseMonth("2025.10"), {
      start: "2025-10-01",
      end: "2025-10-31",
      month: "2025-10",
    });
    assert.equal(releaseMetrics.getReleaseMonth("2024.02").end, "2024-02-29");
    assert.equal(releaseMetrics.getReleaseMonth("2025.12").end, "2025-12-31");
  });

  it("builds the localization PR query", () => {
    assert.equal(
      releaseMetrics.buildQuery({ owner: "o", repo: "r", lang: "ja" }),
      "repo:o/r is:pr is:merged label:lang:ja"
    );
  });

  describe("summarizePRFiles", () => {
    it("counts only markdown files under content/{lang}/", () => {
      const files = [
        { filename: "content/pt/docs/a.md", status: "added", additions: 10 },
        { filename: "content/pt/docs/b.md", status: "modified", additions: 4 },
        { filename: "content/pt/docs/c.md", status: "renamed", additions: 2 },
        { filename: "content/pt/docs/d.png", status: "added", additions: 99 },
        { filename: "content/es/docs/a.md", status: "added", additions: 50 },
        { filename: "content/en/docs/a.md", status: "added", additions: 50 },
        { filename: "content/pt/docs/e.md", status: "added" },
      ];

      assert.deepEqual(releaseMetrics.summarizePRFiles(files, "pt"), {
        lines_added: 16,
        pages_added: 2,
        files_updated: 1,
      });
    });

    it("returns zeros when no file matches", () => {
      assert.deepEqual(releaseMetrics.summarizePRFiles([], "pt"), {
        lines_added: 0,
        pages_added: 0,
        files_updated: 0,
      });
    });
  });

  describe("summarizeCoverage", () => {
    const tree = [
      { path: "content/en/docs/a.md" },
      { path: "content/en/docs/b.md" },
      { path: "content/en/docs/c.md" },
      { path: "content/en/docs/img.png" },
      { path: "content/pt/docs/a.md" },
      { path: "content/pt/docs/img.png" },
      { path: "content/ja/docs/a.md" },
      { path: "content/ja/docs/b.md" },
    ];

    it("compares markdown file counts with the English content", () => {
      assert.deepEqual(releaseMetrics.summarizeCoverage(tree, "pt"), {
        percentage: 33.3,
        lang_files: 1,
        en_files: 3,
      });
      assert.equal(releaseMetrics.summarizeCoverage(tree, "ja").percentage, 66.7);
    });

    it("reports zero for a language without content or without English files", () => {
      assert.equal(releaseMetrics.summarizeCoverage(tree, "ko").percentage, 0);
      assert.deepEqual(releaseMetrics.summarizeCoverage([], "pt"), {
        percentage: 0,
        lang_files: 0,
        en_files: 0,
      });
    });
  });

  it("sums per-PR stats", () => {
    assert.deepEqual(
      releaseMetrics.sumStats([
        { lines_added: 1, pages_added: 2, files_updated: 3 },
        { lines_added: 10, pages_added: 20, files_updated: 30 },
      ]),
      { lines_added: 11, pages_added: 22, files_updated: 33 }
    );
    assert.deepEqual(releaseMetrics.sumStats([]), {
      lines_added: 0,
      pages_added: 0,
      files_updated: 0,
    });
  });

  it("builds records with the fields the processing step reads", () => {
    const record = releaseMetrics.buildRecord({
      lang: "pt",
      month: "2025-10",
      stats: { lines_added: 5, pages_added: 1, files_updated: 2 },
      coverage: { percentage: 12.5, lang_files: 1, en_files: 8 },
      prCount: 3,
    });

    assert.deepEqual(Object.keys(record), [
      "lang",
      "month",
      "lines_added",
      "pages_added",
      "files_updated",
      "coverage_pct",
      "pr_count",
    ]);
    assert.equal(record.coverage_pct, 12.5);
    assert.equal(record.pr_count, 3);
  });
});

describe("script entry points", () => {
  const scripts = [
    "fetch_lang_issues.js",
    "fetch_merged_prs.js",
    "fetch_release_metrics.js",
  ];
  // Run from an empty directory so no .env file is picked up
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), "fetch-entry-"));
  const env = { PATH: process.env.PATH };

  for (const script of scripts) {
    const file = path.join(scriptsDir, script);

    it(`${script} can be imported without GITHUB_TOKEN`, () => {
      const result = spawnSync(
        process.execPath,
        [
          "--input-type=module",
          "-e",
          `await import(${JSON.stringify(pathToFileURL(file).href)}); console.log("imported");`,
        ],
        { cwd, env, encoding: "utf8" }
      );

      assert.equal(result.status, 0, result.stderr);
      assert.equal(result.stdout.trim(), "imported");
    });

    it(`${script} exits with status 1 when GITHUB_TOKEN is missing`, () => {
      const result = spawnSync(process.execPath, [file], {
        cwd,
        env,
        encoding: "utf8",
      });

      assert.equal(result.status, 1);
      assert.match(result.stderr, /GITHUB_TOKEN is not set/);
      assert.equal(fs.existsSync(path.join(cwd, "data")), false);
    });
  }
});
