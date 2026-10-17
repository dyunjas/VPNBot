import {test} from "node:test";
import assert from "node:assert/strict";
import {catalogEndpoints} from "../frontend/landing/src/catalogEndpoint.js";

test("deployed landing requests public API, not the landing domain",()=>{
  for(const hostname of ["lunet.pro","www.lunet.pro"]){
    assert.deepEqual(catalogEndpoints(hostname),["https://api.lunet.pro/api/public/catalog","/catalog.json"]);
  }
});
test("local development retains Vite proxy",()=>{
  for(const hostname of ["localhost","127.0.0.1","[::1]"]){assert.equal(catalogEndpoints(hostname)[0],"/api/public/catalog")}
});
test("API origin can be configured without duplicate slashes",()=>{
  assert.equal(catalogEndpoints("lunet.pro","https://api.example.test///")[0],"https://api.example.test/api/public/catalog");
  assert.equal(catalogEndpoints("lunet.pro","")[0],"/api/public/catalog");
});
