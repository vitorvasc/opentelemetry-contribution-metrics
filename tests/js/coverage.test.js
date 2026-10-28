import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  fetchTree,
  summarizeCoverage,
} from "../../scripts/fetch/lib/coverage.js";

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
    assert.deepEqual(summarizeCoverage(tree, "pt"), {
      percentage: 33.3,
      lang_files: 1,
      en_files: 3,
    });
    assert.equal(summarizeCoverage(tree, "ja").percentage, 66.7);
  });

  it("counts markdown files at any depth under the language directory", () => {
    const nested = [
      { path: "content/en/_index.md" },
      { path: "content/en/docs/a/b/c/page.md" },
      { path: "content/es/_index.md" },
      { path: "content/es/docs/a/b/c/page.md" },
    ];

    assert.deepEqual(summarizeCoverage(nested, "es"), {
      percentage: 100,
      lang_files: 2,
      en_files: 2,
    });
  });

  it("ignores files that are not markdown", () => {
    const mixed = [
      { path: "content/en/a.md" },
      { path: "content/en/b.html" },
      { path: "content/en/c.md.bak" },
      { path: "content/pt/a.md" },
      { path: "content/pt/b.yaml" },
      { path: "content/pt/c.png" },
    ];

    assert.deepEqual(summarizeCoverage(mixed, "pt"), {
      percentage: 100,
      lang_files: 1,
      en_files: 1,
    });
  });

  it("ignores similarly named directories and other content roots", () => {
    const entries = [
      { path: "content/en/docs/a.md" },
      { path: "content/pt-br/docs/a.md" },
      { path: "other/content/pt/a.md" },
    ];

    assert.equal(summarizeCoverage(entries, "pt").lang_files, 0);
  });

  it("reports zero for a language without content or without English files", () => {
    assert.deepEqual(summarizeCoverage(tree, "ko"), {
      percentage: 0,
      lang_files: 0,
      en_files: 3,
    });
    assert.deepEqual(summarizeCoverage([], "pt"), {
      percentage: 0,
      lang_files: 0,
      en_files: 0,
    });
  });

  it("rounds to one decimal", () => {
    const entries = [
      ...Array.from({ length: 7 }, (_, i) => ({ path: `content/en/${i}.md` })),
      { path: "content/pt/0.md" },
    ];

    assert.equal(summarizeCoverage(entries, "pt").percentage, 14.3);
  });
});

describe("fetchTree", () => {
  const repoRef = { owner: "o", repo: "r" };

  it("requests the recursive tree of a ref and returns its entries", async () => {
    const paths = [];
    const gh = {
      ghFetch: async (path) => {
        paths.push(path);
        return { truncated: false, tree: [{ path: "content/en/a.md" }] };
      },
    };

    const tree = await fetchTree(gh, repoRef, "2025.01");

    assert.deepEqual(paths, ["/repos/o/r/git/trees/2025.01?recursive=1"]);
    assert.deepEqual(tree, [{ path: "content/en/a.md" }]);
  });

  it("throws when GitHub truncated the tree, naming the ref", async () => {
    const gh = { ghFetch: async () => ({ truncated: true, tree: [] }) };

    await assert.rejects(
      fetchTree(gh, repoRef, "HEAD"),
      /Git tree for HEAD is truncated/,
    );
  });
});
