import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  buildDataset,
  DEFAULT_CLONE_DIR,
} from "../../scripts/fetch/fetch_drift.js";
import { createGitRunner, syncClone } from "../../scripts/fetch/lib/drift.js";
import { createSandbox, createSource, page } from "./support/git-fixture.js";

const script = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../scripts/fetch/fetch_drift.js",
);

describe("buildDataset", () => {
  it("combines the head, per-language counts and per-page records", () => {
    const sha = "a".repeat(40);
    const report = new Map([
      ["content/pt/a.md", { sha, patched: false, status: "drifted" }],
      ["content/pt/b.md", { sha: null, patched: false, status: "unpinned" }],
    ]);
    const dataset = buildDataset(
      {
        head: { sha: "f".repeat(40), committed_at: "2026-10-28T15:48:25Z" },
        enPages: 3,
        report,
      },
      ["pt"],
      new Date("2026-10-28T18:00:00Z"),
    );

    assert.deepEqual(dataset, {
      repo: "open-telemetry/opentelemetry.io",
      head: { sha: "f".repeat(40), committed_at: "2026-10-28T15:48:25Z" },
      generated_at: "2026-10-28T18:00:00.000Z",
      en_pages: 3,
      languages: [
        {
          lang: "pt",
          pages: 2,
          current: 0,
          drifted: 1,
          unpinned: 1,
          orphan: 0,
          invalid_pin: 0,
        },
      ],
      pages: [
        {
          lang: "pt",
          path: "content/pt/a.md",
          status: "drifted",
          pinned_sha: sha,
          patched: false,
        },
        {
          lang: "pt",
          path: "content/pt/b.md",
          status: "unpinned",
          pinned_sha: null,
          patched: false,
        },
      ],
    });
  });

  it("keeps the default clone under the ignored data directory", () => {
    assert.match(DEFAULT_CLONE_DIR, /^data\/\.cache\//);
  });
});

describe("fetch_drift main", () => {
  function runScript(cwd, env) {
    return spawnSync(process.execPath, [script], {
      cwd,
      env,
      encoding: "utf8",
    });
  }

  it("can be imported without any configuration", () => {
    const { root, env } = createSandbox();
    const result = spawnSync(
      process.execPath,
      [
        "--input-type=module",
        "-e",
        `await import(${JSON.stringify(pathToFileURL(script).href)}); console.log("imported");`,
      ],
      { cwd: root, env: { PATH: env.PATH }, encoding: "utf8" },
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout.trim(), "imported");
  });

  it("updates the clone in CLONE_DIR and writes data/drift.json", async () => {
    const { root, env } = createSandbox();
    const src = createSource(path.join(root, "upstream"), env);
    src.write("content/en/a.md", "A\n");
    src.write("content/en/b.md", "B\n");
    const c0 = src.commit("add English pages");
    src.write("content/pt/a.md", page(c0));
    src.write("content/pt/b.md", page(c0));
    src.write("content/es/a.md", page(null));
    src.commit("add translations");

    const cloneDir = path.join(root, "clone");
    await syncClone({
      dir: cloneDir,
      url: src.url,
      locales: ["pt"],
      git: createGitRunner(env),
    });
    src.write("content/en/a.md", "A, revised\n");
    const head = src.commit("revise a");

    const cwd = path.join(root, "work");
    fs.mkdirSync(cwd);
    const result = runScript(cwd, {
      ...env,
      CLONE_DIR: cloneDir,
      LANGS: "pt,es",
    });

    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /updated the clone/);
    assert.match(result.stdout, /pt: 2 pages, 1 current, 1 drifted/);

    const dataset = JSON.parse(
      fs.readFileSync(path.join(cwd, "data", "drift.json"), "utf8"),
    );
    assert.equal(dataset.head.sha, head);
    assert.equal(dataset.en_pages, 2);
    assert.deepEqual(
      dataset.languages.map(({ lang, pages, drifted, unpinned }) => ({
        lang,
        pages,
        drifted,
        unpinned,
      })),
      [
        { lang: "pt", pages: 2, drifted: 1, unpinned: 0 },
        { lang: "es", pages: 1, drifted: 0, unpinned: 1 },
      ],
    );
    assert.deepEqual(
      dataset.pages.map((p) => [p.path, p.status]),
      [
        ["content/es/a.md", "unpinned"],
        ["content/pt/a.md", "drifted"],
        ["content/pt/b.md", "current"],
      ],
    );
  });

  it("exits with status 1 and writes nothing when CLONE_DIR is not its clone", () => {
    const { root, env } = createSandbox();
    const cloneDir = path.join(root, "not-a-clone");
    fs.mkdirSync(cloneDir);
    fs.writeFileSync(path.join(cloneDir, "file.txt"), "data\n");

    const result = runScript(root, { ...env, CLONE_DIR: cloneDir });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /exists but is not a git clone/);
    assert.equal(fs.existsSync(path.join(root, "data")), false);
  });

  it("rejects an invalid language code before touching git", () => {
    const { root, env } = createSandbox();

    const result = runScript(root, { ...env, LANGS: "pt,../x" });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /"\.\.\/x" is not a language code/);
    assert.equal(fs.existsSync(path.join(root, "data")), false);
  });
});
