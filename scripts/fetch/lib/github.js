import dotenv from "dotenv";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

export const OWNER = "open-telemetry";
export const REPO = "opentelemetry.io";
export const ALL_LOCALES = [
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
];
export const CONTRIBUTION_TYPES = ["both", "prs", "issues"];

const API_BASE = "https://api.github.com";
const API_VERSION = "2022-11-28";
const DAY_MS = 24 * 60 * 60 * 1000;

// The Search API never returns more than 1000 results for a query
const SEARCH_RESULT_CAP = 1000;
const PAGE_SIZE = 100;
// The Search API allows 30 requests per minute
const SEARCH_INTERVAL_MS = 2100;

const MAX_ATTEMPTS = 5;
const MAX_BACKOFF_MS = 30 * 1000;
const RESET_BUFFER_MS = 1000;
// Wait recommended by GitHub when a secondary rate limit has no retry-after
const SECONDARY_LIMIT_WAIT_MS = 60 * 1000;

export class GitHubApiError extends Error {
  constructor(message, { status, url, cause } = {}) {
    super(message, { cause });
    this.name = "GitHubApiError";
    this.status = status;
    this.url = url;
  }
}

/**
 * Parse the LANGS value into a list of language codes
 * @param {string|undefined} value - Comma-separated codes, empty for all
 * @returns {string[]} - Language codes
 */
export function parseLocales(value) {
  if (!value || !value.trim()) return [...ALL_LOCALES];

  const locales = [
    ...new Set(
      value
        .split(",")
        .map((locale) => locale.trim())
        .filter(Boolean)
    ),
  ];
  if (locales.length === 0) {
    throw new Error("LANGS does not contain any language code.");
  }
  return locales;
}

/**
 * Read and validate the configuration from the environment
 * @param {object} [env] - Environment to read, defaults to process.env
 * @returns {object} - { token, owner, repo, locales, year, type }
 */
export function config(env = process.env) {
  if (env === process.env) {
    dotenv.config({ quiet: true });
  }

  const token = env.GITHUB_TOKEN;
  if (!token) {
    throw new Error("GITHUB_TOKEN is not set. Please check your .env file.");
  }

  // Filter by year (default: current year)
  const year = env.YEAR || String(new Date().getUTCFullYear());
  if (!/^\d{4}$/.test(year)) {
    throw new Error(`YEAR must be a four-digit year, got "${year}".`);
  }

  const type = env.TYPE || "both";
  if (!CONTRIBUTION_TYPES.includes(type)) {
    throw new Error(
      `TYPE must be one of ${CONTRIBUTION_TYPES.join(", ")}, got "${type}".`
    );
  }

  return {
    token,
    owner: OWNER,
    repo: REPO,
    locales: parseLocales(env.LANGS),
    year,
    type,
  };
}

function parseDay(day) {
  const [year, month, date] = day.split("-").map(Number);
  return Date.UTC(year, month - 1, date);
}

function formatDay(ms) {
  return new Date(ms).toISOString().slice(0, 10);
}

/**
 * Get the date range of a calendar month (UTC)
 * @param {number|string} year - Year (e.g., 2025)
 * @param {number} month - Month (1-12)
 * @returns {object} - { start: "YYYY-MM-DD", end: "YYYY-MM-DD", month: "YYYY-MM" }
 */
export function monthRange(year, month) {
  const monthStr = String(month).padStart(2, "0");
  const lastDay = new Date(Date.UTC(Number(year), month, 0)).getUTCDate();

  return {
    start: `${year}-${monthStr}-01`,
    end: `${year}-${monthStr}-${String(lastDay).padStart(2, "0")}`,
    month: `${year}-${monthStr}`,
  };
}

/**
 * Split an inclusive day range into two non-overlapping halves
 * @param {string} from - Start day (YYYY-MM-DD)
 * @param {string} to - End day (YYYY-MM-DD), after `from`
 * @returns {Array} - [[from, mid], [mid + 1 day, to]]
 */
export function splitRange(from, to) {
  const start = parseDay(from);
  const end = parseDay(to);
  if (end <= start) {
    throw new Error(`Cannot split the range ${from}..${to}.`);
  }

  const mid = start + Math.floor((end - start) / DAY_MS / 2) * DAY_MS;
  return [
    [from, formatDay(mid)],
    [formatDay(mid + DAY_MS), to],
  ];
}

/**
 * Remove duplicate items, keeping the first occurrence
 * @param {Array} items - Items to filter
 * @param {Function} keyFn - Returns the identity of an item
 * @param {Set} [seen] - Keys already taken, updated in place
 * @returns {Array} - Items whose key was not seen before
 */
export function dedupeBy(items, keyFn, seen = new Set()) {
  const unique = [];
  for (const item of items) {
    const key = keyFn(item);
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(item);
  }
  return unique;
}

/**
 * Extract the URL of the next page from a Link header
 * @param {string|null} header - Value of the Link header
 * @returns {string|null} - Next page URL, or null on the last page
 */
export function parseNextLink(header) {
  if (!header) return null;
  const match = header.match(/<([^>]+)>\s*;\s*rel="next"/);
  return match ? match[1] : null;
}

function backoffMs(attempt) {
  return Math.min(MAX_BACKOFF_MS, 1000 * 2 ** (attempt - 1));
}

/**
 * Decide whether a failed response is worth retrying and for how long
 * @param {object} response - { status, headers, bodyText, attempt, nowMs }
 * @returns {object|null} - { delayMs, reason }, or null when not retryable
 */
export function getRetryDelay({
  status,
  headers,
  bodyText = "",
  attempt,
  nowMs,
}) {
  const retryAfter = headers.get("retry-after");
  const isLimited = status === 403 || status === 429;

  if ((isLimited || status === 503) && retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds)) {
      return { delayMs: seconds * 1000, reason: "retry-after requested" };
    }
  }

  if (isLimited) {
    const reset = Number(headers.get("x-ratelimit-reset"));
    if (headers.get("x-ratelimit-remaining") === "0" && reset) {
      return {
        delayMs: Math.max(0, reset * 1000 - nowMs) + RESET_BUFFER_MS,
        reason: "rate limit exhausted",
      };
    }

    if (status === 429 || /rate limit|abuse/i.test(bodyText)) {
      return {
        delayMs: Math.max(SECONDARY_LIMIT_WAIT_MS, backoffMs(attempt)),
        reason: "secondary rate limit",
      };
    }
    return null;
  }

  if (status >= 500) {
    return { delayMs: backoffMs(attempt), reason: `server error ${status}` };
  }
  return null;
}

/**
 * Create a GitHub API client
 * @param {object} options
 * @param {string} options.token - GitHub token
 * @param {Function} [options.fetchImpl] - fetch implementation, defaults to globalThis.fetch
 * @param {Function} [options.sleep] - (ms) => Promise, waits between retries
 * @param {Function} [options.now] - () => epoch milliseconds
 * @param {number} [options.searchIntervalMs] - Minimum gap between Search API requests
 * @param {number} [options.maxAttempts] - Attempts per request before giving up
 * @param {Function} [options.log] - Progress output
 * @param {Function} [options.warn] - Retry and rate limit output
 * @returns {object} - { ghRequest, ghFetch, ghPaginate, ghSearchIssues }
 */
export function createClient({
  token,
  fetchImpl = (...args) => globalThis.fetch(...args),
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  now = () => Date.now(),
  searchIntervalMs = SEARCH_INTERVAL_MS,
  maxAttempts = MAX_ATTEMPTS,
  log = console.log,
  warn = console.warn,
} = {}) {
  let nextSearchAt = 0;

  function toUrl(pathOrUrl) {
    const url = pathOrUrl.startsWith("http")
      ? pathOrUrl
      : `${API_BASE}${pathOrUrl}`;
    if (new URL(url).origin !== API_BASE) {
      throw new Error(`Refusing to send credentials to ${url}`);
    }
    return url;
  }

  async function wait(delayMs, reason, attempt) {
    warn(
      `⚠️  ${reason}. Retrying in ${Math.ceil(delayMs / 1000)}s ` +
        `(attempt ${attempt}/${maxAttempts})`
    );
    await sleep(delayMs);
  }

  async function throttleSearch() {
    const gap = nextSearchAt - now();
    if (gap > 0) await sleep(gap);
    nextSearchAt = now() + searchIntervalMs;
  }

  /**
   * Send a request, retrying rate limits and transient failures
   * @param {string} pathOrUrl - API path (e.g., "/repos/...") or full API URL
   * @returns {Response} - The successful response
   */
  async function ghRequest(pathOrUrl) {
    const url = toUrl(pathOrUrl);
    const isSearch = new URL(url).pathname.startsWith("/search/");
    const headers = {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": API_VERSION,
      "User-Agent": "opentelemetry-contribution-metrics",
    };

    for (let attempt = 1; ; attempt++) {
      if (isSearch) await throttleSearch();

      let res;
      try {
        res = await fetchImpl(url, { headers });
      } catch (cause) {
        if (attempt >= maxAttempts) {
          throw new GitHubApiError(
            `Request to ${url} failed: ${cause.message}`,
            { url, cause }
          );
        }
        await wait(backoffMs(attempt), `Network error (${cause.message})`, attempt);
        continue;
      }

      if (res.ok) return res;

      const bodyText = await res.text().catch(() => "");
      const retry =
        attempt < maxAttempts
          ? getRetryDelay({
              status: res.status,
              headers: res.headers,
              bodyText,
              attempt,
              nowMs: now(),
            })
          : null;

      if (!retry) {
        throw new GitHubApiError(
          `GitHub API error (${res.status}) for ${url}: ${bodyText.slice(0, 300)}`,
          { status: res.status, url }
        );
      }
      await wait(retry.delayMs, retry.reason, attempt);
    }
  }

  /**
   * GET a JSON document
   * @param {string} pathOrUrl - API path or full API URL
   * @returns {*} - Parsed JSON body
   */
  async function ghFetch(pathOrUrl) {
    const res = await ghRequest(pathOrUrl);
    return res.json();
  }

  /**
   * Fetch every page of a list endpoint
   * @param {string} pathOrUrl - API path or full API URL of a list endpoint
   * @returns {Array} - Items from all pages
   */
  async function ghPaginate(pathOrUrl) {
    const first = new URL(toUrl(pathOrUrl));
    if (!first.searchParams.has("per_page")) {
      first.searchParams.set("per_page", String(PAGE_SIZE));
    }

    const items = [];
    let url = first.toString();
    while (url) {
      const res = await ghRequest(url);
      const page = await res.json();
      if (!Array.isArray(page)) {
        throw new Error(`Expected a list from ${url}`);
      }
      items.push(...page);
      url = page.length > 0 ? parseNextLink(res.headers.get("link")) : null;
    }
    return items;
  }

  async function searchPage(q, page, { sort, order }) {
    const params = new URLSearchParams({
      q,
      sort,
      order,
      per_page: String(PAGE_SIZE),
      page: String(page),
    });

    for (let attempt = 1; ; attempt++) {
      const data = await ghFetch(`/search/issues?${params}`);
      if (!data.incomplete_results) return data;
      if (attempt >= maxAttempts) {
        throw new Error(`Search returned incomplete results for: ${q}`);
      }
      await wait(backoffMs(attempt), "Search returned incomplete results", attempt);
    }
  }

  async function searchRange(query, dateField, from, to, sorting) {
    const q = `${query} ${dateField}:${from}..${to}`;
    const first = await searchPage(q, 1, sorting);

    if (first.total_count > SEARCH_RESULT_CAP) {
      if (from === to) {
        throw new Error(
          `More than ${SEARCH_RESULT_CAP} results on ${from} for: ${query}`
        );
      }
      const [left, right] = splitRange(from, to);
      log(
        `  ${from}..${to} has ${first.total_count} results, ` +
          `splitting at ${left[1]}`
      );
      return [
        ...(await searchRange(query, dateField, ...left, sorting)),
        ...(await searchRange(query, dateField, ...right, sorting)),
      ];
    }

    const items = [...first.items];
    for (let page = 2; items.length < first.total_count; page++) {
      const next = await searchPage(q, page, sorting);
      if (next.items.length === 0) break;
      items.push(...next.items);
    }
    return items;
  }

  /**
   * Search issues and PRs created or merged within a date range. Ranges
   * matching more than 1000 results are split in half until each part fits.
   * @param {object} params
   * @param {string} params.query - Search query without the date qualifier
   * @param {string} params.dateField - Date qualifier name (e.g., "created", "merged")
   * @param {string} params.from - First day (YYYY-MM-DD)
   * @param {string} params.to - Last day (YYYY-MM-DD)
   * @param {string} [params.sort] - Sort field, "created" by default
   * @param {string} [params.order] - "asc" (default) or "desc"
   * @returns {Array} - Unique search items
   */
  async function ghSearchIssues({
    query,
    dateField,
    from,
    to,
    sort = "created",
    order = "asc",
  }) {
    const items = await searchRange(query, dateField, from, to, {
      sort,
      order,
    });
    return dedupeBy(items, (item) => item.id);
  }

  return { ghRequest, ghFetch, ghPaginate, ghSearchIssues };
}

/**
 * Write a JSON file into the data directory, creating it when missing
 * @param {string} name - File name (e.g., "merged_prs.json")
 * @param {*} data - Value to serialize
 * @param {string} [dir] - Output directory, relative to the working directory
 * @returns {string} - Path written
 */
export function writeJson(name, data, dir = "data") {
  const outputPath = path.join(dir, name);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(data, null, 2));
  return outputPath;
}

/**
 * Whether a module was started directly with `node <file>`
 * @param {string} moduleUrl - The module's import.meta.url
 * @returns {boolean}
 */
export function isEntryPoint(moduleUrl) {
  const entry = process.argv[1];
  if (!entry) return false;

  try {
    return fs.realpathSync(entry) === fs.realpathSync(fileURLToPath(moduleUrl));
  } catch {
    return false;
  }
}

/**
 * Run an async main function, exiting with status 1 on failure
 * @param {Function} main - Async entry point
 */
export function run(main) {
  main().catch((error) => {
    console.error("\n✗ Fatal error:", error.message);
    process.exit(1);
  });
}
