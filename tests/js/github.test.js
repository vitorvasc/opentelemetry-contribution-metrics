import { afterEach, describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";

import {
  ALL_LOCALES,
  config,
  createClient,
  getRetryDelay,
  monthRange,
  parseLocales,
  parseNextLink,
  splitRange,
  writeJson,
} from "../../scripts/fetch/lib/github.js";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

/**
 * Replace globalThis.fetch with a scripted handler.
 * `script` is a function (url, init, callNumber) or an array of responses
 * consumed in order. A response is { status, headers, body }.
 */
function mockFetch(script) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    const response = Array.isArray(script)
      ? script[calls.length - 1]
      : await script(String(url), init, calls.length);
    if (!response) throw new Error(`Unexpected request #${calls.length}`);
    if (response.throws) throw response.throws;

    const body =
      typeof response.body === "string"
        ? response.body
        : JSON.stringify(response.body ?? null);
    return new Response(body, {
      status: response.status ?? 200,
      headers: response.headers,
    });
  };
  return calls;
}

const START = 1_700_000_000_000;

/** Client with a fake clock: sleeping advances time instead of waiting. */
function testClient(options = {}) {
  const sleeps = [];
  let clock = START;
  const client = createClient({
    token: "test-token",
    sleep: async (ms) => {
      sleeps.push(ms);
      clock += ms;
    },
    now: () => clock,
    searchIntervalMs: 0,
    warn: () => {},
    log: () => {},
    ...options,
  });
  return { ...client, sleeps };
}

describe("parseLocales", () => {
  it("defaults to every locale, including ko and pl", () => {
    assert.deepEqual(parseLocales(undefined), ALL_LOCALES);
    assert.deepEqual(parseLocales(""), ALL_LOCALES);
    assert.ok(ALL_LOCALES.includes("ko"));
    assert.ok(ALL_LOCALES.includes("pl"));
  });

  it("trims, drops empties, and removes duplicates", () => {
    assert.deepEqual(parseLocales(" pt, es,,pt "), ["pt", "es"]);
  });

  it("rejects a value without any code", () => {
    assert.throws(() => parseLocales(" , "), /LANGS/);
  });
});

describe("config", () => {
  it("requires GITHUB_TOKEN and throws instead of exiting", () => {
    assert.throws(() => config({}), /GITHUB_TOKEN is not set/);
  });

  it("returns defaults for a token-only environment", () => {
    const cfg = config({ GITHUB_TOKEN: "t" });
    assert.deepEqual(cfg, {
      token: "t",
      owner: "open-telemetry",
      repo: "opentelemetry.io",
      locales: ALL_LOCALES,
      year: String(new Date().getUTCFullYear()),
      type: "both",
    });
  });

  it("treats empty variables exported by make as unset", () => {
    const cfg = config({ GITHUB_TOKEN: "t", LANGS: "", TYPE: "", YEAR: "" });
    assert.equal(cfg.type, "both");
    assert.deepEqual(cfg.locales, ALL_LOCALES);
  });

  it("reads YEAR, LANGS and TYPE", () => {
    const cfg = config({
      GITHUB_TOKEN: "t",
      YEAR: "2024",
      LANGS: "pt,es",
      TYPE: "prs",
    });
    assert.equal(cfg.year, "2024");
    assert.deepEqual(cfg.locales, ["pt", "es"]);
    assert.equal(cfg.type, "prs");
  });

  it("rejects an invalid YEAR or TYPE", () => {
    assert.throws(() => config({ GITHUB_TOKEN: "t", YEAR: "25" }), /YEAR/);
    assert.throws(() => config({ GITHUB_TOKEN: "t", TYPE: "pr" }), /TYPE/);
  });
});

describe("monthRange", () => {
  it("handles leap years", () => {
    assert.deepEqual(monthRange(2024, 2), {
      start: "2024-02-01",
      end: "2024-02-29",
      month: "2024-02",
    });
    assert.equal(monthRange(2025, 2).end, "2025-02-28");
    assert.equal(monthRange(2100, 2).end, "2100-02-28");
    assert.equal(monthRange(2000, 2).end, "2000-02-29");
  });

  it("handles December and 30-day months", () => {
    assert.deepEqual(monthRange(2025, 12), {
      start: "2025-12-01",
      end: "2025-12-31",
      month: "2025-12",
    });
    assert.equal(monthRange("2025", 4).end, "2025-04-30");
    assert.equal(monthRange(2025, 1).start, "2025-01-01");
  });
});

describe("splitRange", () => {
  it("splits into two adjacent halves", () => {
    assert.deepEqual(splitRange("2025-01-01", "2025-01-31"), [
      ["2025-01-01", "2025-01-16"],
      ["2025-01-17", "2025-01-31"],
    ]);
    assert.deepEqual(splitRange("2025-01-01", "2025-01-02"), [
      ["2025-01-01", "2025-01-01"],
      ["2025-01-02", "2025-01-02"],
    ]);
  });

  it("crosses month and year boundaries", () => {
    assert.deepEqual(splitRange("2024-12-30", "2025-01-02"), [
      ["2024-12-30", "2024-12-31"],
      ["2025-01-01", "2025-01-02"],
    ]);
    assert.deepEqual(splitRange("2024-02-28", "2024-03-01"), [
      ["2024-02-28", "2024-02-29"],
      ["2024-03-01", "2024-03-01"],
    ]);
  });

  it("covers every day exactly once when split down to single days", () => {
    const days = [];
    const visit = (from, to) => {
      if (from === to) return days.push(from);
      const [left, right] = splitRange(from, to);
      visit(...left);
      visit(...right);
    };
    visit("2024-01-01", "2024-12-31");

    assert.equal(days.length, 366);
    assert.equal(new Set(days).size, 366);
    assert.deepEqual(days, [...days].sort());
  });

  it("refuses a single day", () => {
    assert.throws(() => splitRange("2025-01-01", "2025-01-01"), /Cannot split/);
  });
});

describe("parseNextLink", () => {
  it("returns the rel=next URL", () => {
    const header =
      '<https://api.github.com/x?page=1>; rel="prev", ' +
      '<https://api.github.com/x?page=3>; rel="next", ' +
      '<https://api.github.com/x?page=9>; rel="last"';
    assert.equal(parseNextLink(header), "https://api.github.com/x?page=3");
  });

  it("returns null on the last page or without a header", () => {
    assert.equal(
      parseNextLink('<https://api.github.com/x?page=1>; rel="first"'),
      null
    );
    assert.equal(parseNextLink(null), null);
  });
});

describe("getRetryDelay", () => {
  const headers = (values = {}) => new Headers(values);
  const base = { attempt: 1, nowMs: START };

  it("honors retry-after on 403 and 429", () => {
    for (const status of [403, 429]) {
      const retry = getRetryDelay({
        ...base,
        status,
        headers: headers({ "retry-after": "7" }),
      });
      assert.equal(retry.delayMs, 7000);
    }
  });

  it("waits until x-ratelimit-reset when the quota is exhausted", () => {
    const retry = getRetryDelay({
      ...base,
      status: 403,
      headers: headers({
        "x-ratelimit-remaining": "0",
        "x-ratelimit-reset": String(START / 1000 + 30),
      }),
    });
    assert.equal(retry.delayMs, 31_000);
  });

  it("treats a rate-limit message without headers as a secondary limit", () => {
    const retry = getRetryDelay({
      ...base,
      status: 403,
      headers: headers(),
      bodyText: "You have exceeded a secondary rate limit.",
    });
    assert.equal(retry.delayMs, 60_000);
  });

  it("backs off exponentially on 5xx, capped at 30s", () => {
    const delays = [1, 2, 3, 4, 5, 6, 7].map(
      (attempt) =>
        getRetryDelay({ status: 502, headers: headers(), attempt, nowMs: START })
          .delayMs
    );
    assert.deepEqual(delays, [1000, 2000, 4000, 8000, 16_000, 30_000, 30_000]);
  });

  it("does not retry client errors", () => {
    for (const status of [400, 401, 404, 422]) {
      assert.equal(getRetryDelay({ ...base, status, headers: headers() }), null);
    }
    assert.equal(
      getRetryDelay({
        ...base,
        status: 403,
        headers: headers(),
        bodyText: "Resource not accessible",
      }),
      null
    );
  });
});

describe("ghFetch", () => {
  it("sends auth headers and parses JSON", async () => {
    const calls = mockFetch([{ body: { ok: true } }]);
    const gh = testClient();

    assert.deepEqual(await gh.ghFetch("/repos/o/r"), { ok: true });
    assert.equal(calls[0].url, "https://api.github.com/repos/o/r");
    assert.equal(calls[0].init.headers.Authorization, "Bearer test-token");
    assert.equal(
      calls[0].init.headers.Accept,
      "application/vnd.github+json"
    );
    assert.ok(calls[0].init.headers["X-GitHub-Api-Version"]);
  });

  it("throws a descriptive error without retrying a 404", async () => {
    const calls = mockFetch([{ status: 404, body: { message: "Not Found" } }]);
    const gh = testClient();

    await assert.rejects(gh.ghFetch("/repos/o/missing"), (error) => {
      assert.equal(error.status, 404);
      assert.match(error.message, /404.*\/repos\/o\/missing.*Not Found/s);
      assert.doesNotMatch(error.message, /test-token/);
      return true;
    });
    assert.equal(calls.length, 1);
    assert.deepEqual(gh.sleeps, []);
  });

  it("does not retry a bad token", async () => {
    const calls = mockFetch([{ status: 401, body: { message: "Bad credentials" } }]);
    const gh = testClient();

    await assert.rejects(gh.ghFetch("/user"), /401/);
    assert.equal(calls.length, 1);
  });

  it("honors retry-after", async () => {
    const calls = mockFetch([
      { status: 429, headers: { "retry-after": "7" }, body: {} },
      { body: { ok: 1 } },
    ]);
    const gh = testClient();

    assert.deepEqual(await gh.ghFetch("/x"), { ok: 1 });
    assert.equal(calls.length, 2);
    assert.deepEqual(gh.sleeps, [7000]);
  });

  it("sleeps until the rate limit reset", async () => {
    const calls = mockFetch([
      {
        status: 403,
        headers: {
          "x-ratelimit-remaining": "0",
          "x-ratelimit-reset": String(START / 1000 + 30),
        },
        body: { message: "API rate limit exceeded" },
      },
      { body: { ok: 1 } },
    ]);
    const gh = testClient();

    assert.deepEqual(await gh.ghFetch("/x"), { ok: 1 });
    assert.equal(calls.length, 2);
    assert.deepEqual(gh.sleeps, [31_000]);
  });

  it("backs off on 5xx and then succeeds", async () => {
    const calls = mockFetch([
      { status: 502, body: "bad gateway" },
      { status: 503, body: "unavailable" },
      { body: { ok: 1 } },
    ]);
    const gh = testClient();

    assert.deepEqual(await gh.ghFetch("/x"), { ok: 1 });
    assert.equal(calls.length, 3);
    assert.deepEqual(gh.sleeps, [1000, 2000]);
  });

  it("gives up after the maximum number of attempts", async () => {
    const calls = mockFetch(() => ({ status: 500, body: "boom" }));
    const gh = testClient({ maxAttempts: 3 });

    await assert.rejects(gh.ghFetch("/x"), /500/);
    assert.equal(calls.length, 3);
    assert.deepEqual(gh.sleeps, [1000, 2000]);
  });

  it("retries network errors and reports the last one", async () => {
    const calls = mockFetch([
      { throws: new TypeError("fetch failed") },
      { body: { ok: 1 } },
    ]);
    const gh = testClient();
    assert.deepEqual(await gh.ghFetch("/x"), { ok: 1 });
    assert.equal(calls.length, 2);

    mockFetch(() => ({ throws: new TypeError("fetch failed") }));
    await assert.rejects(testClient({ maxAttempts: 2 }).ghFetch("/x"), /fetch failed/);
  });

  it("never sends the token to another host", async () => {
    const calls = mockFetch([{ body: {} }]);
    const gh = testClient();

    await assert.rejects(gh.ghFetch("https://example.com/x"), /Refusing/);
    assert.equal(calls.length, 0);
  });
});

describe("ghPaginate", () => {
  it("follows Link headers until there is no next page", async () => {
    const calls = mockFetch([
      {
        headers: {
          link: '<https://api.github.com/repos/o/r/releases?per_page=100&page=2>; rel="next"',
        },
        body: [{ id: 1 }, { id: 2 }],
      },
      {
        headers: {
          link: '<https://api.github.com/repos/o/r/releases?per_page=100&page=3>; rel="next"',
        },
        body: [{ id: 3 }],
      },
      { body: [{ id: 4 }] },
    ]);
    const gh = testClient();

    const items = await gh.ghPaginate("/repos/o/r/releases");
    assert.deepEqual(
      items.map((i) => i.id),
      [1, 2, 3, 4]
    );
    assert.equal(calls.length, 3);
    assert.equal(
      calls[0].url,
      "https://api.github.com/repos/o/r/releases?per_page=100"
    );
    assert.match(calls[1].url, /page=2/);
  });

  it("stops after a single page without a Link header", async () => {
    const calls = mockFetch([{ body: [{ id: 1 }] }]);
    const gh = testClient();

    assert.deepEqual(await gh.ghPaginate("/repos/o/r/pulls/1/files"), [
      { id: 1 },
    ]);
    assert.equal(calls.length, 1);
  });

  it("rejects a response that is not a list", async () => {
    mockFetch([{ body: { message: "nope" } }]);
    await assert.rejects(testClient().ghPaginate("/x"), /Expected a list/);
  });
});

/**
 * Fake Search API: `perDay` items for every day of the queried date range,
 * ascending, with the real page limits (422 past the 1000th result).
 */
function fakeSearch(perDay, { onRequest } = {}) {
  return (url) => {
    const params = new URL(url).searchParams;
    const q = params.get("q");
    const [, from, to] = q.match(/(?:created|merged):(\S+)\.\.(\S+)/);
    onRequest?.(q, params);

    const page = Number(params.get("page"));
    const perPage = Number(params.get("per_page"));
    if (page * perPage > 1000) {
      return { status: 422, body: { message: "Only the first 1000 search results are available" } };
    }

    const items = [];
    for (
      let day = Date.parse(from);
      day <= Date.parse(to);
      day += 24 * 60 * 60 * 1000
    ) {
      for (let k = 0; k < perDay; k++) {
        const id = day / 1000 + k;
        items.push({ id, number: id });
      }
    }
    return {
      body: {
        total_count: items.length,
        incomplete_results: false,
        items: items.slice((page - 1) * perPage, page * perPage),
      },
    };
  };
}

describe("ghSearchIssues", () => {
  const search = (gh, overrides = {}) =>
    gh.ghSearchIssues({
      query: "repo:o/r is:pr",
      dateField: "merged",
      from: "2025-01-01",
      to: "2025-01-31",
      ...overrides,
    });

  it("builds the query and pages until total_count is reached", async () => {
    const calls = mockFetch(fakeSearch(10));
    const gh = testClient();

    const items = await search(gh);
    assert.equal(items.length, 310);
    // 310 results = 4 pages, with no extra request for an empty page
    assert.equal(calls.length, 4);

    const params = new URL(calls[0].url).searchParams;
    assert.equal(
      params.get("q"),
      "repo:o/r is:pr merged:2025-01-01..2025-01-31"
    );
    assert.equal(params.get("per_page"), "100");
    assert.equal(params.get("sort"), "created");
    assert.equal(params.get("order"), "asc");
  });

  it("splits the date range when more than 1000 results match", async () => {
    const queries = [];
    const calls = mockFetch(
      fakeSearch(60, { onRequest: (q) => queries.push(q) })
    );
    const gh = testClient();

    const items = await search(gh);

    // 31 days x 60 = 1860 results, split into 16 + 15 days (960 + 900)
    assert.equal(items.length, 1860);
    assert.equal(new Set(items.map((i) => i.id)).size, 1860);
    assert.ok(queries.includes("repo:o/r is:pr merged:2025-01-01..2025-01-31"));
    assert.ok(queries.includes("repo:o/r is:pr merged:2025-01-01..2025-01-16"));
    assert.ok(queries.includes("repo:o/r is:pr merged:2025-01-17..2025-01-31"));
    // 1 probe + 10 pages + 9 pages; never asks past the 1000th result
    assert.equal(calls.length, 20);
    assert.ok(calls.every((call) => !call.url.includes("page=11")));
  });

  it("splits recursively until every part fits", async () => {
    mockFetch(fakeSearch(300));
    const items = await search(testClient());

    // 31 days x 300 = 9300 results, each part holds at most 3 days
    assert.equal(items.length, 9300);
    assert.equal(new Set(items.map((i) => i.id)).size, 9300);
  });

  it("fails when a single day still exceeds the cap", async () => {
    mockFetch(fakeSearch(1001));
    const gh = testClient();

    await assert.rejects(
      search(gh, { from: "2025-01-05", to: "2025-01-05" }),
      /More than 1000 results on 2025-01-05/
    );
  });

  it("removes items returned twice", async () => {
    mockFetch([
      {
        body: {
          total_count: 3,
          incomplete_results: false,
          items: [{ id: 1 }, { id: 2 }, { id: 1 }],
        },
      },
    ]);
    const items = await search(testClient());
    assert.deepEqual(items, [{ id: 1 }, { id: 2 }]);
  });

  it("spaces search requests apart", async () => {
    mockFetch(fakeSearch(125));
    const gh = testClient({ searchIntervalMs: 2100 });

    await search(gh, { from: "2025-01-01", to: "2025-01-02" });
    // 250 results = 3 pages: no wait before the first request
    assert.deepEqual(gh.sleeps, [2100, 2100]);
  });

  it("does not space non-search requests", async () => {
    mockFetch([{ body: {} }, { body: {} }]);
    const gh = testClient({ searchIntervalMs: 2100 });

    await gh.ghFetch("/repos/o/r");
    await gh.ghFetch("/repos/o/r");
    assert.deepEqual(gh.sleeps, []);
  });

  it("retries incomplete results and then fails", async () => {
    const incomplete = {
      body: { total_count: 1, incomplete_results: true, items: [] },
    };
    const complete = {
      body: { total_count: 1, incomplete_results: false, items: [{ id: 1 }] },
    };

    mockFetch([incomplete, complete]);
    assert.deepEqual(await search(testClient()), [{ id: 1 }]);

    mockFetch(() => incomplete);
    const gh = testClient();
    await assert.rejects(search(gh), /incomplete results/);
    // Five attempts spread over about a minute
    assert.deepEqual(gh.sleeps, [4000, 8000, 16_000, 32_000]);
  });

  it("does not request page 11 when results disappear while paging", async () => {
    // total_count says 950 results, but one was removed before page 10
    const calls = mockFetch((url) => {
      const page = Number(new URL(url).searchParams.get("page"));
      if (page > 10) {
        return { status: 422, body: { message: "Only the first 1000 search results are available" } };
      }
      const size = page < 10 ? 100 : 49;
      return {
        body: {
          total_count: 950,
          incomplete_results: false,
          items: Array.from({ length: size }, (_, k) => ({ id: page * 1000 + k })),
        },
      };
    });

    const items = await search(testClient());

    assert.equal(items.length, 949);
    assert.equal(calls.length, 10);
  });

  it("propagates API errors", async () => {
    mockFetch([{ status: 422, body: { message: "Validation Failed" } }]);
    await assert.rejects(search(testClient()), /422.*Validation Failed/s);
  });
});

describe("writeJson", () => {
  it("creates the directory and writes formatted JSON", () => {
    const dir = path.join(
      fs.mkdtempSync(path.join(os.tmpdir(), "write-json-")),
      "nested",
      "data"
    );

    const written = writeJson("out.json", [], dir);

    assert.equal(written, path.join(dir, "out.json"));
    assert.equal(fs.readFileSync(written, "utf8"), "[]");
    writeJson("out.json", [{ a: 1 }], dir);
    assert.equal(
      fs.readFileSync(written, "utf8"),
      JSON.stringify([{ a: 1 }], null, 2)
    );
  });
});
