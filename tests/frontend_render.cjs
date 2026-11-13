/* Pure renderer checks in Node. This does not automate a browser. */
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const path = require("node:path");
const root = path.resolve(__dirname,"..");
const fixture = JSON.parse(fs.readFileSync(0,"utf8"));
const noop = ()=>{};
const element = {addEventListener:noop};
const context = vm.createContext({
  document:{addEventListener:noop,querySelector:()=>element,querySelectorAll:()=>[]},
  window:{addEventListener:noop},location:{hash:"#overview",search:"",href:"http://127.0.0.1:8000/#overview"},
  URL, URLSearchParams, Intl, Blob, TextEncoder, setTimeout,clearTimeout, console,fixture
});
const source = fs.readFileSync(path.join(root,"web/app.js"),"utf8").replace(/\nboot\(\);\s*$/,"");
vm.runInContext(source,context);
vm.runInContext("state.config=fixture.config; state.detail=fixture.detail;",context);
for(const [name, expression] of [
  ["overview","overviewView(fixture.overview)"],
  ["queue","listView(fixture.page)"],
  ["detail","detailView(fixture.detail)"],
  ["reviews","reviewsTab(fixture.detail)"],
  ["changes","driftTab(fixture.detail)"],
  ["agents","agentsView()"]
]){
  const html = vm.runInContext(expression,context);
  assert.equal(typeof html,"string",name);
  assert.ok(html.length>500,name);
  assert.ok(!html.includes("[object Object]"),name);
  assert.ok(!html.includes("undefined"),name);
}
context.attack = '<img src=x onerror="steal()"><script>steal()</script>';
const escaped = vm.runInContext("esc(attack)",context);
assert.ok(!escaped.includes("<script>"));
assert.ok(escaped.includes("&lt;script&gt;"));
fixture.detail.listing.title=context.attack;
const malicious = vm.runInContext("detailView(fixture.detail)",context);
assert.ok(!malicious.includes(context.attack));
assert.ok(malicious.includes(escaped));
const markup=fs.readFileSync(path.join(root,"web/index.html"),"utf8");
for(const match of markup.matchAll(/data-action="([^"]+)"/g)){
  assert.ok(source.includes('"'+match[1]+'"'),"Missing action handler: "+match[1]);
}
assert.ok(!markup.includes('href="#dataset"'),"Dataset navigation removed");
assert.equal(vm.runInContext("typeof datasetView",context),"undefined");
assert.ok(vm.runInContext("evidenceTab(fixture.detail)",context).includes("Copy draft"));
assert.ok(!/\sonclick=/i.test(markup),"No inline script handlers under CSP");
assert.ok(!/\b(?:alert|confirm|prompt)\s*\(/.test(source),"App-owned dialogs only");
console.log("6 view renderers, untrusted-content escaping, and static command bindings passed.");
