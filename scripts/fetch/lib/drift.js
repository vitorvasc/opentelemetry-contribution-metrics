import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export const CONTENT_DIR = "content";
export const DEFAULT_LANG = "en";
// Page statuses, in chart order
export const STATUSES = [
  "current",
  "drifted",
  "unpinned",
  "orphan",
  "invalid_pin",
];
// Set on clones created by syncClone; only marked clones are ever reset
export const CACHE_MARKER = "contribution-metrics.cache";
// GIT_NO_LAZY_FETCH, which keeps reads from fetching unknown pins, needs 2.44
export const MIN_GIT_VERSION = [2, 44];

const DIFF_CONCURRENCY = 8;
const LOCALE_RE = /^[a-z][a-z-]{1,4}$/i;

// Same pin pattern as upstream scripts/i18n/drift.mjs: line-anchored, first
// match in the whole file, case-insensitive. `# patched` marks a manually
// reconciled pin and does not change the drift status.
const PIN_RE =
  /^default_lang_commit:\s*([a-f0-9]+)(?<patched>\s*#\s*patched)?/im;

/**
 * Read the default_lang_commit pin of a localized page
 * @param {string} text - Page source
 * @returns {object|null} - { sha, patched }, or null when the page has no pin
 */
export function parsePin(text) {
  const match = PIN_RE.exec(text);
  if (!match) return null;
  return { sha: match[1], patched: Boolean(match.groups.patched) };
}

/**
 * Map a localized page to the English page it translates
 * @param {string} page - Path such as content/pt/docs/_index.md
 * @returns {string} - Path such as content/en/docs/_index.md
 */
export function enCounterpartOf(page) {
  return page.replace(
    new RegExp(`^${CONTENT_DIR}/[^/]{2,5}/`),
    `${CONTENT_DIR}/${DEFAULT_LANG}/`,
  );
}

/**
 * Get the language code of a page under the content directory
 * @param {string} page - Path such as content/pt/docs/_index.md
 * @returns {string} - Language code such as pt
 */
export function localeOf(page) {
  return page.split("/")[1];
}

/**
 * Check language codes before they become sparse-checkout paths
 * @param {string[]} locales - Language codes
 * @returns {string[]} - The same codes
 */
export function validateLocales(locales) {
  for (const locale of locales) {
    if (!LOCALE_RE.test(locale) || locale === DEFAULT_LANG) {
      throw new Error(
        `"${locale}" is not a language code of a translated content directory.`,
      );
    }
  }
  return locales;
}

async function mapLimit(items, limit, fn) {
  const queue = [...items];
  async function worker() {
    while (queue.length > 0) await fn(queue.shift());
  }
  await Promise.all(
    Array.from({ length: Math.min(limit, items.length) }, worker),
  );
}

/**
 * Classify localized pages against their English counterparts, with the
 * precedence of upstream drift.mjs: a page without an English counterpart is
 * an orphan, then a page without a pin is unpinned, then the English page
 * either changed since the pin (drifted) or not (current). A pin git cannot
 * diff is invalid.
 * @param {Map} pagePins - Page path -> { sha, patched } or null
 * @param {object} effects
 * @param {Function} effects.enExists - (enPath) => boolean, at the head commit
 * @param {Function} effects.changedEnSince - async (sha) => Set of English
 *   paths changed since the pin; rejects when git cannot resolve the pin
 * @param {number} [effects.concurrency] - Diffs run at the same time
 * @returns {Map} - Page path -> { status, sha, patched }, in input order
 */
export async function classifyPages(
  pagePins,
  { enExists, changedEnSince, concurrency = DIFF_CONCURRENCY },
) {
  const report = new Map();
  const pending = new Map();

  for (const [page, pin] of pagePins) {
    const entry = { sha: pin?.sha ?? null, patched: pin?.patched ?? false };
    report.set(page, entry);

    if (!enExists(enCounterpartOf(page))) {
      entry.status = "orphan";
    } else if (!pin) {
      entry.status = "unpinned";
    } else {
      if (!pending.has(pin.sha)) pending.set(pin.sha, []);
      pending.get(pin.sha).push(page);
    }
  }

  // One diff per unique pin, shared by every page with that pin
  await mapLimit([...pending.keys()], concurrency, async (sha) => {
    let changed = null;
    try {
      changed = await changedEnSince(sha);
    } catch {
      changed = null;
    }
    for (const page of pending.get(sha)) {
      const entry = report.get(page);
      if (!changed) entry.status = "invalid_pin";
      else if (changed.has(enCounterpartOf(page))) entry.status = "drifted";
      else entry.status = "current";
    }
  });

  return report;
}

/**
 * Count page statuses per language
 * @param {Map} report - Result of classifyPages
 * @param {string[]} locales - Language codes, in output order
 * @returns {Array} - { lang, pages, current, drifted, unpinned, orphan, invalid_pin }
 */
export function summarizeDrift(report, locales) {
  const byLocale = new Map(
    locales.map((lang) => [
      lang,
      {
        lang,
        pages: 0,
        ...Object.fromEntries(STATUSES.map((status) => [status, 0])),
      },
    ]),
  );

  for (const [page, { status }] of report) {
    const counts = byLocale.get(localeOf(page));
    if (!counts) continue;
    counts.pages++;
    counts[status]++;
  }
  return [...byLocale.values()];
}

/**
 * Create a git runner
 * @param {object} [baseEnv] - Environment for every git process
 * @returns {Function} - async (args, { cwd, input, env, buffer }) => stdout,
 *   a string, or a Buffer when buffer is true; rejects on a non-zero exit
 */
export function createGitRunner(baseEnv = process.env) {
  return (args, { cwd, input, env = {}, buffer = false } = {}) =>
    new Promise((resolve, reject) => {
      const child = spawn("git", args, {
        cwd,
        // Never wait on a credential prompt
        env: { ...baseEnv, GIT_TERMINAL_PROMPT: "0", ...env },
        stdio: ["pipe", "pipe", "pipe"],
      });
      const stdout = [];
      const stderr = [];
      child.stdout.on("data", (chunk) => stdout.push(chunk));
      child.stderr.on("data", (chunk) => stderr.push(chunk));
      // git may exit before reading all of its input
      child.stdin.on("error", () => {});
      child.on("error", reject);
      child.on("close", (code) => {
        if (code !== 0) {
          const message = Buffer.concat(stderr).toString("utf8").trim();
          reject(new Error(`git ${args[0]} failed (exit ${code}): ${message}`));
          return;
        }
        const out = Buffer.concat(stdout);
        resolve(buffer ? out : out.toString("utf8"));
      });
      child.stdin.end(input ?? "");
    });
}

export const runGit = createGitRunner();

/**
 * Fail unless git supports GIT_NO_LAZY_FETCH
 * @param {Function} [git] - Runner from createGitRunner
 */
export async function checkGitVersion(git = runGit) {
  const output = await git(["--version"]);
  const match = output.match(/(\d+)\.(\d+)/);
  const [major, minor] = match ? [Number(match[1]), Number(match[2])] : [0, 0];
  const [minMajor, minMinor] = MIN_GIT_VERSION;

  if (major < minMajor || (major === minMajor && minor < minMinor)) {
    throw new Error(
      `git ${MIN_GIT_VERSION.join(".")} or newer is required, found: ${output.trim()}`,
    );
  }
}

function sparseArgs(locales) {
  return [
    "sparse-checkout",
    "set",
    "--cone",
    ...locales.map((lang) => `${CONTENT_DIR}/${lang}`),
  ];
}

async function assertManagedClone(git, dir) {
  let top;
  try {
    top = (await git(["rev-parse", "--show-toplevel"], { cwd: dir })).trim();
  } catch {
    top = null;
  }
  if (!top || fs.realpathSync(top) !== fs.realpathSync(dir)) {
    throw new Error(
      `${dir} exists but is not a git clone. Remove it or set CLONE_DIR to another path.`,
    );
  }

  let marker;
  try {
    marker = (
      await git(["config", "--local", "--get", CACHE_MARKER], { cwd: dir })
    ).trim();
  } catch {
    marker = null;
  }
  if (marker !== "true") {
    throw new Error(
      `${dir} is a git clone this script did not create, so it will not be ` +
        "reset. Remove it or set CLONE_DIR to another path.",
    );
  }
}

/**
 * Create or update a blobless clone holding only the translated content.
 * Commits and trees cover the whole history, so pins can be diffed locally;
 * file contents are fetched only for the content/<lang> directories.
 * An existing clone is reset to the remote default branch, so CLONE_DIR must
 * be a clone this function created.
 * @param {object} options
 * @param {string} options.dir - Clone directory
 * @param {string} options.url - Repository URL
 * @param {string[]} options.locales - Language codes to check out
 * @param {Function} [options.git] - Runner from createGitRunner
 * @returns {string} - "cloned" or "updated"
 */
export async function syncClone({ dir, url, locales, git = runGit }) {
  validateLocales(locales);

  const isEmpty = !fs.existsSync(dir) || fs.readdirSync(dir).length === 0;
  if (isEmpty) {
    const parent = path.dirname(path.resolve(dir));
    fs.mkdirSync(parent, { recursive: true });
    await git(
      [
        "clone",
        "--quiet",
        "--filter=blob:none",
        "--sparse",
        "--config",
        `${CACHE_MARKER}=true`,
        url,
        path.resolve(dir),
      ],
      { cwd: parent },
    );
    await git(sparseArgs(locales), { cwd: dir });
    return "cloned";
  }

  await assertManagedClone(git, dir);
  await git(["fetch", "--quiet", "--prune", "origin"], { cwd: dir });
  // Follows a rename of the default branch
  await git(["remote", "set-head", "origin", "--auto"], { cwd: dir });
  await git(["reset", "--quiet", "--hard", "origin/HEAD"], { cwd: dir });
  // After the reset, so new languages are fetched at the new head only
  await git(sparseArgs(locales), { cwd: dir });
  return "updated";
}

/**
 * Parse `git ls-tree -r -z` output
 * @param {string} output - NUL-separated "<mode> <type> <oid>\t<path>" records
 * @returns {Array} - { oid, path } per blob
 */
export function parseLsTree(output) {
  return output
    .split("\0")
    .filter(Boolean)
    .map((record) => {
      const tab = record.indexOf("\t");
      const [, type, oid] = record.slice(0, tab).split(" ");
      return { type, oid, path: record.slice(tab + 1) };
    })
    .filter((entry) => entry.type === "blob")
    .map(({ oid, path: file }) => ({ oid, path: file }));
}

/**
 * Parse `git cat-file --batch` output for the requested objects. Sizes are
 * byte counts, so the output is sliced as a Buffer before decoding.
 * @param {Buffer} output - Batch output
 * @param {string[]} oids - Requested objects, in request order
 * @returns {string[]} - Object contents decoded as UTF-8, in request order
 */
export function parseCatFileBatch(output, oids) {
  const texts = [];
  let offset = 0;

  for (const oid of oids) {
    const newline = output.indexOf(0x0a, offset);
    if (newline < 0) throw new Error(`git cat-file output ended before ${oid}`);
    const header = output.toString("utf8", offset, newline);
    const [, type, size] = header.split(" ");
    if (!size) {
      throw new Error(`git cat-file could not read ${oid}: ${header}`);
    }
    const start = newline + 1;
    const end = start + Number(size);
    if (type !== "blob" || end > output.length) {
      throw new Error(`git cat-file returned an unexpected object: ${header}`);
    }
    texts.push(output.toString("utf8", start, end));
    // Each object is followed by a newline
    offset = end + 1;
  }
  return texts;
}

/**
 * Compute the drift report of a clone at its current head. Every read runs
 * with GIT_NO_LAZY_FETCH, so a pin to a commit missing from the clone is
 * reported as invalid instead of being fetched from the remote.
 * @param {object} options
 * @param {string} options.dir - Clone directory
 * @param {string[]} options.locales - Language codes
 * @param {Function} [options.git] - Runner from createGitRunner
 * @returns {object} - { head: { sha, committed_at }, enPages, report }
 */
export async function computeDrift({ dir, locales, git = runGit }) {
  validateLocales(locales);
  const read = (args, options = {}) =>
    git(args, { ...options, cwd: dir, env: { GIT_NO_LAZY_FETCH: "1" } });

  const sha = (await read(["rev-parse", "--verify", "HEAD^{commit}"])).trim();
  const committedAt = (
    await read([
      "show",
      "--no-patch",
      "--no-show-signature",
      "--format=%cI",
      sha,
    ])
  ).trim();

  const entries = parseLsTree(
    await read(["ls-tree", "-r", "-z", sha, "--", CONTENT_DIR]),
  );
  const enPrefix = `${CONTENT_DIR}/${DEFAULT_LANG}/`;
  const enPaths = new Set(
    entries.map((entry) => entry.path).filter((p) => p.startsWith(enPrefix)),
  );
  const tracked = new Set(locales);
  const pages = entries
    .filter(
      (entry) =>
        entry.path.endsWith(".md") && tracked.has(localeOf(entry.path)),
    )
    .sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));

  const oids = pages.map((page) => page.oid);
  const texts =
    oids.length > 0
      ? parseCatFileBatch(
          await read(["cat-file", "--batch"], {
            input: oids.map((oid) => `${oid}\n`).join(""),
            buffer: true,
          }),
          oids,
        )
      : [];
  const pagePins = new Map(
    pages.map((page, i) => [page.path, parsePin(texts[i])]),
  );

  const report = await classifyPages(pagePins, {
    enExists: (enPath) => enPaths.has(enPath),
    // Three-dot range, as upstream: English changes since the merge base of
    // the pin and the head. Rename detection is off: an English path that
    // exists at the head is listed either way, and in a blobless clone the
    // detection would download file contents. -z keeps paths unquoted.
    changedEnSince: async (pin) => {
      const output = await read([
        "diff",
        "--name-only",
        "--no-renames",
        "-z",
        `${pin}...${sha}`,
        "--",
        `${CONTENT_DIR}/${DEFAULT_LANG}`,
      ]);
      return new Set(output.split("\0").filter(Boolean));
    },
  });

  return {
    head: { sha, committed_at: committedAt },
    enPages: [...enPaths].filter((p) => p.endsWith(".md")).length,
    report,
  };
}
