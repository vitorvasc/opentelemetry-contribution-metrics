// Preloaded with `node --import` to replace the network when a fetch script
// runs as a child process. STUB_ROUTES maps an endpoint kind to { status?, body }.
const routes = JSON.parse(process.env.STUB_ROUTES ?? "{}");

function endpointKind(pathname) {
  if (pathname.endsWith("/releases")) return "releases";
  if (pathname.includes("/git/trees/")) return "tree";
  if (pathname.startsWith("/search/")) return "search";
  if (pathname.endsWith("/files")) return "files";
  return null;
}

globalThis.fetch = async (url) => {
  const { pathname } = new URL(url);
  const route = routes[endpointKind(pathname)];

  if (!route) {
    return new Response(JSON.stringify({ message: `No stub for ${pathname}` }), {
      status: 404,
    });
  }
  return new Response(JSON.stringify(route.body), { status: route.status ?? 200 });
};
