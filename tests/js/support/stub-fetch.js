// Preloaded with `node --import` to replace the network when a fetch script
// runs as a child process. STUB_ROUTES maps an endpoint kind to { status?, body }.
// When STUB_LOG is set, every requested URL is appended to that file.
import fs from "node:fs";

const routes = JSON.parse(process.env.STUB_ROUTES ?? "{}");

function endpointKind(pathname) {
  if (/^\/repos\/[^/]+\/[^/]+$/.test(pathname)) return "repo";
  if (pathname.endsWith("/releases")) return "releases";
  if (pathname.includes("/git/trees/")) return "tree";
  if (pathname.startsWith("/search/")) return "search";
  if (pathname.endsWith("/files")) return "files";
  return null;
}

globalThis.fetch = async (url) => {
  if (process.env.STUB_LOG) {
    fs.appendFileSync(process.env.STUB_LOG, `${url}\n`);
  }
  const { pathname } = new URL(url);
  const route = routes[endpointKind(pathname)];

  if (!route) {
    return new Response(
      JSON.stringify({ message: `No stub for ${pathname}` }),
      {
        status: 404,
      },
    );
  }
  return new Response(JSON.stringify(route.body), {
    status: route.status ?? 200,
  });
};
