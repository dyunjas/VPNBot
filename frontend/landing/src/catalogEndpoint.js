// Development uses Vite's local proxy; deployed sites use the public API domain.
export function catalogEndpoints(hostname,configuredBase){
  const local=["localhost","127.0.0.1","[::1]","::1"].includes(hostname);
  const base=(configuredBase??(local?"":"https://api.lunet.pro")).trim().replace(/\/+$/,"");
  return [`${base}/api/public/catalog`,"/catalog.json"];
}
