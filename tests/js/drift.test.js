import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { describe, it } from "node:test";

import {
  CACHE_MARKER,
  checkGitVersion,
  classifyPages,
  computeDrift,
  createGitRunner,
  enCounterpartOf,
  parseCatFileBatch,
  parseLsTree,
  parsePin,
  STATUSES,
  summarizeDrift,
  syncClone,
  validateLocales,
} from "../../scripts/fetch/lib/drift.js";
import { createSandbox, createSource, page } from "./support/git-fixture.js";

const SHA_A = "a".repeat(40);
const SHA_B = "b".repeat(40);

describe("parsePin", () => {
  it("reads the default_lang_commit sha", () => {
    assert.deepEqual(parsePin(page(SHA_A)), { sha: SHA_A, patched: false });
  });

  it("recognizes a # patched marker and ignores other comments", () => {
    assert.equal(parsePin(page(SHA_A, { suffix: " # patched" })).patched, true);
    assert.equal(parsePin(page(SHA_A, { suffix: "  #patched" })).patched, true);
    assert.equal(parsePin(page(SHA_A, { suffix: " # todo" })).patched, false);
  });

  it("matches the key case-insensitively and keeps the first match", () => {
    const text = `---\nDefault_Lang_Commit: ${SHA_A}\ndefault_lang_commit: ${SHA_B}\n---\n`;
    assert.equal(parsePin(text).sha, SHA_A);
  });

  it("accepts short shas", () => {
    assert.equal(parsePin(page("abc1234")).sha, "abc1234");
  });

  it("returns null without a line-anchored key", () => {
    assert.equal(parsePin(page(null)), null);
    assert.equal(parsePin(`---\n# default_lang_commit: ${SHA_A}\n---\n`), null);
    assert.equal(parsePin("---\ndefault_lang_commit: \n---\n"), null);
  });

  it("matches a line in the body too, as upstream does", () => {
    const text = `---\ntitle: Guide\n---\n\ndefault_lang_commit: ${SHA_B}\n`;
    assert.equal(parsePin(text).sha, SHA_B);
  });
});

describe("enCounterpartOf", () => {
  it("maps any locale directory to content/en, keeping the rest", () => {
    assert.equal(
      enCounterpartOf("content/pt/docs/_index.md"),
      "content/en/docs/_index.md",
    );
    assert.equal(
      enCounterpartOf("content/pt-br/docs/a.md"),
      "content/en/docs/a.md",
    );
  });
});

describe("validateLocales", () => {
  it("accepts language codes and rejects anything else", () => {
    assert.deepEqual(validateLocales(["pt", "pt-br"]), ["pt", "pt-br"]);
    for (const bad of ["en", "../x", "p", "a/b", "toolong"]) {
      assert.throws(() => validateLocales([bad]), /is not a language code/);
    }
  });
});

describe("classifyPages", () => {
  const en = new Set([
    "content/en/a.md",
    "content/en/b.md",
    "content/en/c.md",
    "content/en/d.md",
  ]);
  const enExists = (p) => en.has(p);

  it("applies the upstream precedence: orphan, unpinned, then the diff", async () => {
    const pins = new Map([
      ["content/pt/a.md", { sha: SHA_A, patched: false }],
      ["content/pt/b.md", { sha: SHA_A, patched: true }],
      ["content/pt/c.md", null],
      ["content/pt/gone.md", { sha: SHA_A, patched: false }],
      ["content/pt/new.md", null],
    ]);
    const report = await classifyPages(pins, {
      enExists,
      changedEnSince: async () => new Set(["content/en/a.md"]),
    });

    assert.deepEqual(Object.fromEntries(report), {
      "content/pt/a.md": { sha: SHA_A, patched: false, status: "drifted" },
      "content/pt/b.md": { sha: SHA_A, patched: true, status: "current" },
      "content/pt/c.md": { sha: null, patched: false, status: "unpinned" },
      "content/pt/gone.md": { sha: SHA_A, patched: false, status: "orphan" },
      "content/pt/new.md": { sha: null, patched: false, status: "orphan" },
    });
  });

  it("diffs once per unique pin and skips orphans", async () => {
    const calls = [];
    const pins = new Map([
      ["content/pt/a.md", { sha: SHA_A, patched: false }],
      ["content/es/a.md", { sha: SHA_A, patched: false }],
      ["content/ja/b.md", { sha: SHA_B, patched: false }],
      ["content/ja/gone.md", { sha: "c".repeat(40), patched: false }],
    ]);
    await classifyPages(pins, {
      enExists,
      changedEnSince: async (sha) => {
        calls.push(sha);
        return new Set();
      },
    });

    assert.deepEqual(calls.sort(), [SHA_A, SHA_B]);
  });

  it("marks every page of a pin git rejects as invalid", async () => {
    const pins = new Map([
      ["content/pt/a.md", { sha: SHA_A, patched: false }],
      ["content/es/a.md", { sha: SHA_A, patched: false }],
      ["content/pt/d.md", { sha: SHA_B, patched: false }],
    ]);
    const report = await classifyPages(pins, {
      enExists,
      changedEnSince: async (sha) => {
        if (sha === SHA_A) throw new Error("bad object");
        return new Set(["content/en/d.md"]);
      },
    });

    assert.equal(report.get("content/pt/a.md").status, "invalid_pin");
    assert.equal(report.get("content/es/a.md").status, "invalid_pin");
    assert.equal(report.get("content/pt/d.md").status, "drifted");
  });
});

describe("summarizeDrift", () => {
  const report = new Map([
    ["content/pt/a.md", { status: "drifted" }],
    ["content/pt/b.md", { status: "current" }],
    ["content/pt/c.md", { status: "current" }],
    ["content/pt/d.md", { status: "unpinned" }],
    ["content/es/a.md", { status: "orphan" }],
    ["content/es/b.md", { status: "invalid_pin" }],
    ["content/fr/a.md", { status: "current" }],
  ]);

  it("counts statuses per language in the requested order", () => {
    assert.deepEqual(summarizeDrift(report, ["pt", "es", "ko"]), [
      {
        lang: "pt",
        pages: 4,
        current: 2,
        drifted: 1,
        unpinned: 1,
        orphan: 0,
        invalid_pin: 0,
      },
      {
        lang: "es",
        pages: 2,
        current: 0,
        drifted: 0,
        unpinned: 0,
        orphan: 1,
        invalid_pin: 1,
      },
      {
        lang: "ko",
        pages: 0,
        current: 0,
        drifted: 0,
        unpinned: 0,
        orphan: 0,
        invalid_pin: 0,
      },
    ]);
  });

  it("splits every page of a language into exactly one status", () => {
    for (const record of summarizeDrift(report, ["pt", "es"])) {
      const total = STATUSES.reduce((sum, status) => sum + record[status], 0);
      assert.equal(total, record.pages);
    }
  });
});

describe("parseLsTree", () => {
  it("returns blobs with their object ids and skips submodules", () => {
    const output =
      "100644 blob 1111\tcontent/pt/a b.md\0" +
      "160000 commit 2222\tcontent/pt/sub\0" +
      "100644 blob 3333\tcontent/en/a.md\0";

    assert.deepEqual(parseLsTree(output), [
      { oid: "1111", path: "content/pt/a b.md" },
      { oid: "3333", path: "content/en/a.md" },
    ]);
  });
});

describe("parseCatFileBatch", () => {
  it("slices objects by byte size, so multibyte text stays aligned", () => {
    const first = "タイトル: 概要\n";
    const second = "default_lang_commit: abc\n";
    const output = Buffer.concat([
      Buffer.from(`1111 blob ${Buffer.byteLength(first)}\n${first}\n`),
      Buffer.from(`2222 blob ${Buffer.byteLength(second)}\n${second}\n`),
    ]);

    assert.deepEqual(parseCatFileBatch(output, ["1111", "2222"]), [
      first,
      second,
    ]);
  });

  it("throws on a missing object", () => {
    assert.throws(
      () => parseCatFileBatch(Buffer.from("1111 missing\n"), ["1111"]),
      /could not read 1111: 1111 missing/,
    );
  });
});

describe("checkGitVersion", () => {
  const fakeGit = (version) => async () => `git version ${version}\n`;

  it("accepts git 2.44 and newer", async () => {
    await checkGitVersion(fakeGit("2.44.0"));
    await checkGitVersion(fakeGit("2.54.0 (Apple Git-157)"));
    await checkGitVersion(fakeGit("3.0.1"));
  });

  it("rejects older git, which would lazily fetch unknown pins", async () => {
    await assert.rejects(
      checkGitVersion(fakeGit("2.43.7")),
      /git 2\.44 or newer is required, found: git version 2\.43\.7/,
    );
  });
});

/**
 * Upstream history used by the clone tests:
 *   C0 adds English pages a, b, c and an image
 *   C1 changes en/a
 *   side branch: S1 changes en/c, never merged
 *   refs/pull/1/head: P1 changes en/b, reachable from no branch
 *   C2 adds the localized pages
 */
function buildUpstream(dir, env) {
  const src = createSource(dir, env);
  src.write("content/en/a.md", "A\n");
  src.write("content/en/b.md", "B\n");
  src.write("content/en/c.md", "C\n");
  src.write("content/en/_index.md", "Home\n");
  src.write("content/en/img.png", "png\n");
  src.write("README.md", "upstream\n");
  const c0 = src.commit("add English pages");

  src.write("content/en/a.md", "A, revised\n");
  const c1 = src.commit("revise a");

  src.git("switch", "--quiet", "-c", "side");
  src.write("content/en/c.md", "C, on a side branch\n");
  const s1 = src.commit("revise c on a side branch");

  src.git("switch", "--quiet", "--detach", c1);
  src.write("content/en/b.md", "B, in a pull request\n");
  const p1 = src.commit("revise b in a pull request");
  src.git("update-ref", "refs/pull/1/head", p1);
  src.git("switch", "--quiet", "main");

  src.write("content/pt/a.md", page(c0, { title: "A" }));
  src.write("content/pt/b.md", page(c0, { title: "B", suffix: " # patched" }));
  src.write("content/pt/_index.md", page(null, { title: "Início" }));
  src.write("content/pt/gone.md", page(c0, { title: "Gone" }));
  src.write("content/pt/c.md", page(s1, { title: "C" }));
  src.write("content/pt/img.png", "png\n");
  src.write("content/es/a.md", page(c1.slice(0, 9), { title: "A" }));
  src.write("content/es/b.md", page(p1, { title: "B" }));
  src.write("content/es/c.md", page("deadbeef", { title: "C" }));
  src.write("content/ja/a.md", page(c1, { title: "概要 — 日本語のページ" }));
  src.write("content/fr/a.md", page(c0, { title: "A" }));
  const c2 = src.commit("add translations");

  return { src, shas: { c0, c1, s1, p1, c2 } };
}

function statusesOf(report) {
  return Object.fromEntries(
    [...report].map(([file, { status }]) => [file, status]),
  );
}

describe("syncClone and computeDrift", () => {
  it("clones only the translated content and classifies every page", async () => {
    const { root, env } = createSandbox();
    const { src, shas } = buildUpstream(path.join(root, "upstream"), env);
    const dir = path.join(root, "cache", "clone");
    const diffs = [];
    const runner = createGitRunner(env);
    const git = (args, options) => {
      if (args[0] === "diff") diffs.push(args);
      return runner(args, options);
    };

    const action = await syncClone({
      dir,
      url: src.url,
      locales: ["pt", "es", "ja"],
      git,
    });
    const drift = await computeDrift({
      dir,
      locales: ["pt", "es", "ja"],
      git,
    });

    assert.equal(action, "cloned");
    assert.equal(fs.existsSync(path.join(dir, "content/pt/a.md")), true);
    assert.equal(fs.existsSync(path.join(dir, "content/en")), false);
    assert.equal(fs.existsSync(path.join(dir, "content/fr")), false);

    assert.equal(drift.head.sha, shas.c2);
    assert.match(drift.head.committed_at, /^\d{4}-\d\d-\d\dT/);
    assert.equal(drift.enPages, 4);
    assert.deepEqual(statusesOf(drift.report), {
      "content/es/a.md": "current",
      // Reachable only from refs/pull/1/head, which a clone does not fetch
      "content/es/b.md": "invalid_pin",
      "content/es/c.md": "invalid_pin",
      "content/ja/a.md": "current",
      "content/pt/_index.md": "unpinned",
      "content/pt/a.md": "drifted",
      "content/pt/b.md": "current",
      // Three-dot: en/c changed only on the side branch of the pin
      "content/pt/c.md": "current",
      "content/pt/gone.md": "orphan",
    });
    assert.deepEqual(drift.report.get("content/pt/b.md"), {
      sha: shas.c0,
      patched: true,
      status: "current",
    });
    // c0, s1, c1 (short), p1, deadbeef, c1; the orphan's pin is never diffed
    assert.equal(diffs.length, 6);
  });

  it("updates an existing clone to the new upstream head", async () => {
    const { root, env } = createSandbox();
    const { src, shas } = buildUpstream(path.join(root, "upstream"), env);
    const dir = path.join(root, "clone");
    const git = createGitRunner(env);

    await syncClone({ dir, url: src.url, locales: ["pt"], git });
    const before = await computeDrift({ dir, locales: ["pt"], git });

    src.write("content/en/b.md", "B, revised on main\n");
    src.write("content/pt/_index.md", page(shas.c2, { title: "Início" }));
    const c3 = src.commit("revise b and pin the Portuguese home page");

    const action = await syncClone({
      dir,
      url: src.url,
      locales: ["pt", "es"],
      git,
    });
    const after = await computeDrift({ dir, locales: ["pt", "es"], git });

    assert.equal(action, "updated");
    assert.equal(before.head.sha, shas.c2);
    assert.equal(before.report.get("content/pt/b.md").status, "current");
    assert.equal(after.head.sha, c3);
    assert.equal(after.report.get("content/pt/b.md").status, "drifted");
    assert.equal(after.report.get("content/pt/_index.md").status, "current");
    // A language added on update is read at the new head
    assert.equal(after.report.get("content/es/a.md").status, "current");
    assert.equal(after.report.get("content/es/b.md").status, "invalid_pin");
  });

  it("refuses a directory that is not a clone, even inside another repository", async () => {
    const { root, env } = createSandbox();
    const { src } = buildUpstream(path.join(root, "upstream"), env);
    const dir = path.join(src.dir, "data", "cache");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "notes.txt"), "keep me\n");

    await assert.rejects(
      syncClone({
        dir,
        url: src.url,
        locales: ["pt"],
        git: createGitRunner(env),
      }),
      /exists but is not a git clone/,
    );
    assert.equal(
      fs.readFileSync(path.join(dir, "notes.txt"), "utf8"),
      "keep me\n",
    );
  });

  it("refuses a clone it did not create and leaves it untouched", async () => {
    const { root, env } = createSandbox();
    const { src } = buildUpstream(path.join(root, "upstream"), env);
    const dir = path.join(root, "own-clone");
    const git = createGitRunner(env);
    await git(["clone", "--quiet", src.url, dir]);
    fs.writeFileSync(path.join(dir, "README.md"), "local edit\n");

    await assert.rejects(
      syncClone({ dir, url: src.url, locales: ["pt"], git }),
      /did not create, so it will not be reset/,
    );
    assert.equal(
      fs.readFileSync(path.join(dir, "README.md"), "utf8"),
      "local edit\n",
    );
  });

  it("marks the clones it creates", async () => {
    const { root, env } = createSandbox();
    const { src } = buildUpstream(path.join(root, "upstream"), env);
    const dir = path.join(root, "clone");
    const git = createGitRunner(env);

    await syncClone({ dir, url: src.url, locales: ["pt"], git });

    assert.equal(
      (
        await git(["config", "--local", "--get", CACHE_MARKER], { cwd: dir })
      ).trim(),
      "true",
    );
  });
});
