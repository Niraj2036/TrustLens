"use strict";
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = value => value == null ? "—" : new Intl.NumberFormat("en-IN").format(value);
const money = (value, currency = "INR") => new Intl.NumberFormat("en-IN", {style:"currency",currency,maximumFractionDigits:0}).format(value);
const date = value => value ? new Intl.DateTimeFormat("en-IN", {day:"numeric",month:"short",year:"numeric",timeZone:"Asia/Kolkata"}).format(new Date(value)) : "Not analyzed";
const datetime = value => value ? new Intl.DateTimeFormat("en-IN", {day:"numeric",month:"short",hour:"2-digit",minute:"2-digit",timeZone:"Asia/Kolkata"}).format(new Date(value)) + " IST" : "—";
const names = {high:"High risk",medium:"Medium risk",low:"Low risk",insufficient:"Insufficient evidence",pending:"Not analyzed"};
const statusNames = {open:"Open",needs_review:"Needs review",reviewed:"Reviewed"};
const agentNames = {ingestion:"Listing ingestion",segmentation:"Review segmentation",compliance:"Listing compliance",claims:"Claim extraction",authenticity:"Review authenticity",seller:"Seller behavior",images:"Image signals",scoring:"Risk aggregation",report:"Reviewer report",orchestrator:"Orchestrator"};
const state = {overview:null,config:null,detail:null,routeToken:0,job:null,importing:false,reviewBusy:false,reviewDraft:null};
let toastTimer, searchTimer;
const paths = {
overview:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
grid:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
network:'<circle cx="12" cy="5" r="2.5"/><circle cx="5" cy="18" r="2.5"/><circle cx="19" cy="18" r="2.5"/><path d="m11 7-5 8m7-8 5 8M8 18h8"/>',
database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 4 16 4 16 0V5M4 12v7c0 4 16 4 16 0v-7"/>',
plus:'<path d="M12 5v14M5 12h14"/>', play:'<path d="m8 5 11 7-11 7Z"/>',
arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',back:'<path d="M19 12H5m5-5-5 5 5 5"/>',
download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
close:'<path d="m6 6 12 12M18 6 6 18"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
check:'<path d="m5 12 4 4L19 6"/>',shield:'<path d="m12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6Z"/><path d="m8 12 3 3 5-6"/>',
alert:'<path d="m12 3 10 18H2Z"/><path d="M12 9v5m0 3v1"/>',
star:'<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9Z"/>',
info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
chevron:'<path d="m6 9 6 6 6-6"/>',sort:'<path d="M8 4v16m-3-3 3 3 3-3M16 20V4m-3 3 3-3 3 3"/>',
file:'<path d="M14 2H5v20h14V7Zm0 0v5h5M8 12h8M8 16h6"/>',
refresh:'<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
users:'<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-16a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5"/>'
};
function icon(name) {return '<span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+(paths[name]||paths.shield)+'</svg></span>';}
function hydrateIcons(root=document){$$("[data-icon]",root).forEach(el=>{el.innerHTML=icon(el.dataset.icon);el.removeAttribute("data-icon");});}
function art(type, large=false){
 const shapes = {
 powerbank:'<rect x="10" y="4" width="16" height="27" rx="4"/><path d="M15 8h6m-3 5-3 6h5l-3 6"/><circle cx="18" cy="28" r=".6"/>',
 bottle:'<rect x="12" y="11" width="13" height="21" rx="4"/><path d="M14 11V6h9v5M12 19h13M15 5h7"/>',
 flask:'<path d="M14 10V5h8v5c4 2 4 3 4 7v12a3 3 0 0 1-3 3H13a3 3 0 0 1-3-3V17c0-4 0-5 4-7Z"/><path d="M10 17h16M15 3h6"/>',
 earbuds:'<rect x="5" y="17" width="26" height="14" rx="6"/><path d="M7 22h22M12 7v6m0-6a3 3 0 1 0-3 3m15-3v6m0-6a3 3 0 1 0-3 3"/>',
 lamp:'<path d="M8 31h22M18 31V19l8-9M18 19 9 11l7-7 8 8M25 9l6 6-9 4-3-4Z"/>',
 backpack:'<rect x="8" y="9" width="21" height="23" rx="6"/><path d="M14 9V5h9v4M12 22h13v7H12ZM8 17h21M5 14v12m27-12v12"/>',
 serum:'<rect x="11" y="14" width="15" height="18" rx="3"/><path d="M14 14V7h9v7M16 7V3h5v4M15 22h7"/>',
 cable:'<path d="M10 8v12a8 8 0 0 0 16 0v-8M6 3h8v7H6Zm16 1h8v8h-8ZM9 3V1m3 2V1"/>',
 watch:'<rect x="10" y="10" width="17" height="17" rx="5"/><path d="m14 10 1-8h8l1 8m-10 17 1 8h8l1-8M18 14v5l4 2M29 16v5"/>',
 grinder:'<rect x="10" y="13" width="17" height="19" rx="3"/><path d="M9 13h19M18 13V7h13M30 7V3h4v6h-4M10 22h17"/>',
 mat:'<path d="M8 10h22v18H8a5 5 0 0 1 0-10h21M8 10a5 5 0 0 0 0 10m0-10v10"/><ellipse cx="8" cy="24" rx="3" ry="4"/>',
 headphones:'<path d="M6 21v-5a12 12 0 0 1 24 0v5M6 17h5v13H6a3 3 0 0 1-3-3v-7a3 3 0 0 1 3-3Zm24 0h-5v13h5a3 3 0 0 0 3-3v-7a3 3 0 0 0-3-3Z"/>',
 box:'<path d="m18 3 13 7v17l-13 7-13-7V10Zm-13 7 13 7 13-7M18 17v17M11 6l14 8"/>'
 };
 return '<span class="product-art'+(large?' large':'')+'" aria-hidden="true"><svg viewBox="0 0 36 36">'+(shapes[type]||shapes.box)+'</svg></span>';
}
function badge(risk){return '<span class="risk-badge risk-'+esc(risk)+'">'+esc(names[risk]||risk)+'</span>';}
function scoreCell(item){return '<div class="score-cell"><strong>'+fmt(item.trust_score)+'</strong><span class="mini-track"><span class="'+esc(item.risk)+'" style="width:'+Number(item.trust_score||0)+'%"></span></span></div>';}
function stateView(title,message,action="retry",label="Try again",symbol="info"){return '<div class="state">'+icon(symbol)+'<h2>'+esc(title)+'</h2><p>'+esc(message)+'</p>'+(action?'<button class="btn" data-action="'+esc(action)+'">'+esc(label)+'</button>':'')+'</div>';}
function heading(title,description,actions=true){return '<div class="page-heading"><div><div class="page-overline"><span class="dot"></span>TRUST & SAFETY WORKSPACE</div><h1 tabindex="-1">'+esc(title)+'</h1><p>'+esc(description)+'</p></div>'+(actions?'<div class="heading-actions"><button class="btn" data-action="open-import">'+icon("plus")+'Import listings</button><button class="btn primary analyze-button" data-action="analyze-all" '+(state.job?'disabled':'')+'>'+icon("play")+'Analyze listings</button></div>':'')+'</div>';}
function notify(message,error=false){clearTimeout(toastTimer);const el=$("#toast");el.textContent=message;el.className="toast"+(error?" error":"");el.hidden=false;toastTimer=setTimeout(()=>{el.hidden=true;},5500);}
async function api(path,options={}){
 const controller = new AbortController();
 const timer = setTimeout(()=>controller.abort(),20000);
 try{
   const response = await fetch(path,{...options,signal:controller.signal,headers:{"Content-Type":"application/json",...options.headers}});
   const payload = await response.json();
   if(!response.ok)throw new Error(payload.error||"The request failed. Try again.");
   return payload;
 }catch(error){if(error.name==="AbortError")throw new Error("The request took too long. Check the local server and retry.");if(error instanceof TypeError)throw new Error("Cannot reach the local server. Keep python app.py running, then retry.");throw error;}
 finally{clearTimeout(timer);}
}
function routeInfo(){const hash=location.hash.slice(1)||"overview";return {view:hash.split("/")[0],id:hash.split("/")[1]};}
function query(){return new URLSearchParams(location.search);}
function setQuery(key,value){const url=new URL(location.href);if(value)url.searchParams.set(key,value);else url.searchParams.delete(key);if(key!=="page")url.searchParams.delete("page");history.replaceState(null,"",url);renderRoute(false);}
function navigate(view){location.hash=view;}
function link(view){return esc(location.search+"#"+view);}
function preserveFocus(){const el=document.activeElement;return el?.id?{id:el.id,start:el.selectionStart,end:el.selectionEnd}:null;}
function restoreFocus(info){if(!info)return;const el=document.getElementById(info.id);if(el){el.focus({preventScroll:true});if(typeof info.start==="number"&&el.setSelectionRange)el.setSelectionRange(info.start,info.end);}}
function listingsTable(items,compact=false){
 return '<div class="table-wrap"><table aria-label="'+(compact?'Priority listings':'Listing review queue')+'"><thead><tr><th scope="col">'+(compact?'Listing':'<button class="sort-button" data-action="sort" data-sort="title">Listing '+icon("sort")+'</button>')+'</th><th scope="col"'+(!compact&&(!query().get("sort")||query().get("sort")==="trust")?' aria-sort="ascending"':'')+'>'+(compact?'Trust score':'<button class="sort-button" data-action="sort" data-sort="trust">Trust score '+icon("sort")+'</button>')+'</th><th scope="col">Risk level</th>'+(compact?'':'<th scope="col">Reviews</th><th scope="col">Review status</th>')+'<th scope="col"><span class="sr-only">Open listing</span></th></tr></thead><tbody>'+items.map(item=>'<tr><td><div class="product-cell">'+art(item.illustration)+'<div class="product-info"><a class="product-link" href="'+link("listing/"+encodeURIComponent(item.id))+'">'+esc(item.title)+'</a><small>'+esc(item.category)+' · '+esc(item.id)+'</small></div></div></td><td>'+scoreCell(item)+'</td><td>'+badge(item.risk)+'</td>'+(compact?'':'<td class="review-total">'+fmt(item.review_count)+'<small>'+esc(item.average_rating??"—")+' ★ average</small></td><td><span class="pill '+(item.status==="reviewed"?'tone-success':'subtle')+'">'+esc(statusNames[item.status])+'</span></td>')+'<td><a class="arrow-link" href="'+link("listing/"+encodeURIComponent(item.id))+'" aria-label="Review '+esc(item.title)+'">'+icon("arrow")+'</a></td></tr>').join("")+'</tbody></table></div>';
}
function stat(label,value,foot,symbol,extra="",attention=false){return '<div class="stat"><div class="stat-head">'+esc(label)+icon(symbol)+'</div><div class="stat-value">'+esc(value)+'<span>'+esc(extra)+'</span></div><div class="stat-foot'+(attention?' stat-attention':'')+'">'+esc(foot)+'</div></div>';}
function overviewView(data){
 const totals=data.totals, dist=data.distribution;
 const total=totals.listings||1;
 const high=(dist.high||0)/total*100,medium=(dist.medium||0)/total*100,low=(dist.low||0)/total*100;
 const donut='conic-gradient(var(--color-danger) 0 '+high+'%, #dda53f '+high+'% '+(high+medium)+'%, #369c84 '+(high+medium)+'% '+(high+medium+low)+'%, #dce4ee '+(high+medium+low)+'% 100%)';
 const maxCategory=Math.max(1,...data.categories.map(c=>c.total));
 return heading("Trust overview","A clearer view of your listings, reviews, and the evidence behind them.")+
 '<div class="stats">'+stat("Listings monitored",fmt(totals.listings),"Across "+data.categories.length+" product categories","grid")+
 stat("High-risk listings",fmt(totals.high_risk),"Prioritize for a manual audit","shield","",true)+
 stat("Reviews analyzed",fmt(totals.reviews),"Timing, language, and reviewer cohorts","users")+
 stat("Average trust score",fmt(totals.average_trust),"Based on available screening evidence","star","/ 100")+'</div>'+
 '<div class="grid-charts"><section class="panel"><div class="panel-head"><div><h2>Trust distribution</h2><p>Every listing has a story. Start with its signals.</p></div><span class="pill subtle">All listings</span></div><div class="panel-body"><div class="donut-layout"><div class="donut" style="background:'+donut+'" role="img" aria-label="'+esc((dist.high||0)+' high risk, '+(dist.medium||0)+' medium risk, '+(dist.low||0)+' low risk, '+((dist.pending||0)+(dist.insufficient||0))+' pending or insufficient')+'"><div class="donut-label"><strong>'+fmt(totals.listings)+'</strong><small>total listings</small></div></div><div class="distribution-legend">'+["high","medium","low"].map(r=>'<div class="legend-line"><i class="swatch '+r+'"></i><span>'+names[r]+'</span><strong>'+fmt(dist[r]||0)+' <small>/ '+Math.round((dist[r]||0)/total*100)+'%</small></strong></div>').join("")+((dist.pending||dist.insufficient)?'<div class="legend-line"><i class="swatch"></i><span>Unassessed</span><strong>'+fmt((dist.pending||0)+(dist.insufficient||0))+'</strong></div>':'')+'</div></div></div><div class="panel-footer"><span>High &lt; 50 · Medium 50–74 · Low ≥ 75</span><span class="mono">0–100</span></div></section>'+
 '<section class="panel"><div class="panel-head"><div><h2>Where risk concentrates</h2><p>Trust signals across your product categories</p></div><div class="chart-legend"><span><i class="swatch high"></i>High</span><span><i class="swatch medium"></i>Medium</span><span><i class="swatch low"></i>Low</span></div></div><div class="panel-body"><div class="category-chart">'+data.categories.map(c=>'<div class="category-row"><span>'+esc(c.name)+'</span><div class="category-track" role="img" aria-label="'+esc(c.name+': '+c.high+' high, '+c.medium+' medium, '+c.low+' low risk out of '+c.total)+'">'+["high","medium","low"].map(r=>'<span class="category-segment '+r+'" style="width:'+(c[r]/maxCategory*100)+'%"></span>').join("")+'</div><span>'+c.total+'</span></div>').join("")+'</div></div><div class="panel-footer"><span>Counts reflect current listing analyses</span><a class="text-btn" href="'+link("listings")+'">Explore listings '+icon("arrow")+'</a></div></section></div>'+
 '<div class="grid-lower"><section class="panel"><div class="panel-head spaced"><div><h2>Review priorities</h2><p>Lowest trust scores first, with evidence a click away</p></div><a class="text-btn" href="'+link("listings")+'">View all '+icon("arrow")+'</a></div>'+
 (data.priority.length?listingsTable(data.priority,true):stateView("Your workspace is empty","Import product listings and reviews to begin.","open-import","Import listings","database"))+
 '<div class="panel-footer"><span>'+fmt(totals.needs_review)+' listings awaiting human review</span><span>'+fmt(totals.findings)+' screening findings</span></div></section>'+
 '<section class="panel pipeline-preview">'+icon("network")+'<h2>Ten agents.<br>One evidence trail.</h2><p>From raw listing data to a report you can act on. Every handoff is recorded.</p><div class="pipeline-steps">'+[["Ingest & organize","2 agents"],["Detect & cross-check","5 agents"],["Score, report & coordinate","3 agents"]].map(v=>'<div class="pipeline-step"><span class="step-check">'+icon("check")+'</span><span>'+v[0]+'</span><small>'+v[1]+'</small></div>').join("")+'</div><a class="text-btn" href="'+link("agents")+'">Explore the pipeline '+icon("arrow")+'</a></section></div>'+
 '<div class="info-banner">'+icon("info")+'<div><strong>Built to support human judgment.</strong> Scores are screening signals, not proof of fraud. The included sample dataset is synthetic; image checks use supplied metadata. Last analysis: '+esc(datetime(data.last_analysis))+'.</div></div>';
}
function selectControl(id,label,options,value){
 return '<div class="filter-control"><label class="sr-only" for="'+id+'">'+label+'</label><select id="'+id+'" data-filter="'+id.replace("filter-","")+'">'+options.map(([v,t])=>'<option value="'+esc(v)+'"'+(v===value?' selected':'')+'>'+esc(t)+'</option>').join("")+'</select></div>';
}
function listView(data){
 const params=query(), q=params.get("q")||"";
 const filters=[["risk",params.get("risk")],["category",params.get("category")],["status",params.get("status")]].filter(v=>v[1]);
 return heading("Listing review","Inspect the evidence, prioritize risk, and record your decision.")+
 '<section class="panel"><div class="filters"><div class="search-box">'+icon("search")+'<label class="sr-only" for="listing-search">Search listings</label><input id="listing-search" type="search" autocomplete="off" placeholder="Search listing, seller, or ID…" value="'+esc(q)+'"><button class="clear-search" data-action="clear-search" aria-label="Clear search" '+(!q?'hidden':'')+'>'+icon("close")+'</button></div>'+
 selectControl("filter-risk","Filter by risk",[["","All risk levels"],...Object.entries(names).map(([v,t])=>[v,t])],params.get("risk")||"")+
 selectControl("filter-category","Filter by category",[["","All categories"],...data.categories.map(c=>[c,c])],params.get("category")||"")+
 selectControl("filter-status","Filter by review status",[["","All statuses"],...Object.entries(statusNames)],params.get("status")||"")+
 selectControl("filter-sort","Sort listings",[["trust","Lowest trust first"],["reviews","Most reviews"],["recent","Recently updated"],["title","Title A–Z"]],params.get("sort")||"trust")+'</div>'+
 (filters.length?'<div class="filter-chips">'+filters.map(([key,value])=>'<span class="filter-chip">'+esc(key)+': '+esc(key==="risk"?names[value]:key==="status"?statusNames[value]:value)+'<button data-action="clear-filter" data-key="'+key+'" aria-label="Clear '+key+' filter">'+icon("close")+'</button></span>').join("")+'<button class="text-btn" data-action="reset-filters">Clear filters</button></div>':'')+
 (data.items.length?listingsTable(data.items):stateView(data.total?"No listings on this page":"No listings match","Try another search or clear the filters to see your listings.","reset-filters","Clear search & filters","search"))+
 '<div class="pagination"><span>'+(data.total?((data.page-1)*data.size+1)+'–'+Math.min(data.page*data.size,data.total):'0')+' of '+fmt(data.total)+' listings</span><div class="page-controls"><button class="btn" data-action="page" data-page="'+(data.page-1)+'" '+(data.page===1?'disabled':'')+'>Previous</button><span>Page '+data.page+' of '+data.pages+'</span><button class="btn" data-action="page" data-page="'+(data.page+1)+'" '+(data.page===data.pages?'disabled':'')+'>Next</button></div></div></section>'+
 '<p class="export-note">Review status is recorded separately from risk. A reviewed listing may still have a high risk score.</p>';
}

function findingView(f,index){
 return '<details class="finding" '+(index===0?'open':'')+'><summary><span class="risk-badge risk-'+esc(f.severity)+'">'+esc(f.severity[0].toUpperCase()+f.severity.slice(1))+'</span><h3>'+esc(f.title)+'</h3>'+icon("chevron")+'</summary><div class="finding-body"><p>'+esc(f.detail)+'</p><span class="eyebrow">SUPPLIED EVIDENCE</span><pre class="evidence-code">'+esc(JSON.stringify(f.evidence,null,2))+'</pre><div class="finding-action"><strong>Next action</strong> · '+esc(f.action)+'</div><div class="finding-source"><span>'+esc(agentNames[f.agent]||f.agent)+'</span><span>'+Math.round(f.confidence*100)+'% heuristic confidence</span></div></div></details>';
}
function sellerRequestText(detail){
 const report=detail?.report?.report;
 if(!report)return "";
 if(report.seller_request)return report.seller_request;
 if(!report.questions?.length)return "";
 return "Evidence request for "+detail.listing.title+" ("+detail.listing.id+")\n\n"+
 report.questions.map((q,index)=>(index+1)+". "+q.question).join("\n\n");
}
async function copySellerRequest(){
 const value=sellerRequestText(state.detail);
 if(!value)return;
 const button=document.querySelector('[data-action="copy-seller-request"]');
 if(button){button.disabled=true;button.setAttribute("aria-busy","true");}
 try{
   await navigator.clipboard.writeText(value);
   const error=$("#seller-copy-error");if(error)error.hidden=true;
   notify("Seller evidence request copied.");
 }catch{
   const error=$("#seller-copy-error");
   if(error){
     error.hidden=false;
     error.textContent="Automatic copy is unavailable. Copy the selected draft text with your keyboard.";
     const field=document.createElement("textarea");
     field.readOnly=true;field.value=value;field.className="manual-copy";
     field.style.resize="none";field.setAttribute("aria-label","Seller evidence request to copy");
     error.appendChild(field);field.focus();field.select();
   }
 }finally{if(button){button.disabled=false;button.setAttribute("aria-busy","false");}}
}
function evidenceTab(detail){
 const {report}=detail,claims=report.agents.claims?.claims||[],r=report.report;
 return (report.scoring.guardrails?.length?'<div class="info-banner" style="margin-bottom:16px">'+icon('info')+'<div><strong>Score cap applied.</strong> '+report.scoring.guardrails.map(g=>esc(g.reason)+' (maximum '+g.cap+'/100).').join(' ')+' Weighted score before cap: '+report.scoring.weighted_score+'/100.</div></div>':'')+'<div class="evidence-stack">'+(report.scoring.findings.length?report.scoring.findings.map(findingView).join(""):stateView("No configured red flags detected","The supplied data did not trigger the screening rules. Review the evidence coverage and limitations before deciding.",null,"","shield"))+'</div>'+
 '<section class="subsection"><div class="section-heading"><h2>Claims extracted from the listing</h2><span class="pill subtle">'+claims.length+' claims</span></div><div class="claims-grid">'+(claims.length?claims.map(c=>'<div class="claim"><small>'+esc(c.type)+' · Seller-stated</small><strong>'+esc(c.text)+'</strong><span class="pill '+(c.documents.length?'blue':'subtle')+'">'+esc(c.status)+'</span>'+(c.documents.length?'<p class="field-hint">'+esc(c.documents.join(", "))+'</p>':'')+'</div>').join(""):'<p class="muted small-text">No supported claim patterns were found in the supplied text.</p>')+'</div><p class="field-hint">Document supplied means a reference was included. It does not mean independently verified.</p></section>'+
 (r.questions.length?'<section class="subsection"><div class="section-heading"><h2>Seller evidence request</h2><button class="btn small" data-action="copy-seller-request">'+icon("file")+'Copy draft</button></div><p class="muted small-text">Review this draft before sending it to the seller.</p><div class="panel panel-body"><pre class="request-preview">'+esc(r.seller_request||sellerRequestText(detail))+'</pre><div id="seller-copy-error" class="form-error" role="alert" hidden></div></div></section>':'')+
 (r.suggested_edits.length?'<section class="subsection"><h2>Suggested listing edits</h2><p class="muted small-text">Draft suggestions only. The listing has not been changed.</p>'+r.suggested_edits.map(e=>'<div class="diff-row"><div class="diff-side before"><small>BEFORE</small>'+esc(e.before)+'</div><div class="diff-side after"><small>SUGGESTED</small>'+esc(e.after)+'</div></div>').join("")+'</section>':'')+
 '<details class="limitations"><summary>What this report can and cannot establish</summary><ul>'+r.limitations.map(l=>'<li>'+esc(l)+'</li>').join("")+'</ul></details>';
}
function reviewsTab(detail){
 const output=detail.report.agents.authenticity||{},metrics=output.metrics||{};
 const weekly=detail.report.agents.segmentation?.weekly||[];
 const max=Math.max(1,...weekly.map(w=>w.count));
 const p=Math.max(1,Math.min(Math.ceil(detail.listing.reviews.length/20)||1,Number(query().get("rp"))||1));
 const reviews=[...detail.listing.reviews].sort((a,b)=>a.date.localeCompare(b.date)).slice((p-1)*20,p*20);
 const flagged=new Set(output.flagged_reviewer_ids||[]);
 return '<div class="detail-stats"><div class="detail-stat">Peak 48-hour window<strong>'+fmt(metrics.burst_count)+'</strong>'+esc(metrics.burst_ratio??"—")+'× remaining-period baseline</div><div class="detail-stat">Reviews in text clusters<strong>'+fmt(metrics.duplicate_reviews)+'</strong>Exact or near-duplicate phrases</div><div class="detail-stat">Unverified purchases<strong>'+Math.round((metrics.unverified_share||0)*100)+'%</strong>Explicitly marked unverified</div></div>'+
 '<section class="panel"><div class="panel-head"><div><h2>Review volume over time</h2><p>Weekly cohorts · Monday start · UTC</p></div></div><div class="panel-body">'+(weekly.length?'<div class="timeline-chart" role="img" aria-label="'+esc(weekly.map(w=>w.week+': '+w.count+' reviews').join('; '))+'">'+weekly.map(w=>'<div class="timeline-bar '+(w.count===max?'peak':'')+'" style="height:'+Math.max(3,w.count/max*100)+'%" title="'+esc(w.week+' · '+w.count+' reviews')+'"></div>').join("")+'</div><div class="timeline-labels"><span>'+esc(weekly[0].week)+'</span><span>'+esc(weekly[weekly.length-1].week)+'</span></div><details class="limitations"><summary>Weekly counts</summary>'+weekly.map(w=>'<p>'+esc(w.week)+': '+w.count+' reviews; '+w.unverified+' unverified</p>').join("")+'</details>':'<p class="muted">No review dates supplied.</p>')+'</div></section>'+
 '<section class="subsection"><div class="section-heading"><h2>Review evidence</h2><span class="pill subtle">'+fmt(detail.listing.reviews.length)+' reviews</span></div><div class="panel"><div class="table-wrap"><table class="review-table" aria-label="Customer reviews"><thead><tr><th scope="col">Reviewer / date</th><th scope="col">Rating</th><th scope="col">Review text</th><th scope="col">Purchase</th></tr></thead><tbody>'+reviews.map(r=>'<tr><td><span class="mono">'+esc(r.reviewer_id)+'</span><br><small class="muted">'+esc(date(r.date))+'</small></td><td>'+esc(r.rating)+' ★</td><td class="review-text">'+esc(r.text)+(flagged.has(r.reviewer_id)?'<br><span class="pill tone-warning">In a flagged reviewer cluster</span>':'')+'</td><td><span class="pill '+(r.verified_purchase===true?'tone-success':'subtle')+'">'+(r.verified_purchase===true?'Verified':r.verified_purchase===false?'Unverified':'Unknown')+'</span></td></tr>').join("")+'</tbody></table></div><div class="pagination"><span>Showing '+(reviews.length?((p-1)*20+1)+'–'+Math.min(p*20,detail.listing.reviews.length):0)+' of '+fmt(detail.listing.reviews.length)+'</span><div class="page-controls"><button class="btn" data-action="review-page" data-page="'+(p-1)+'" '+(p===1?'disabled':'')+'>Previous</button><span>Page '+p+'</span><button class="btn" data-action="review-page" data-page="'+(p+1)+'" '+(p*20>=detail.listing.reviews.length?'disabled':'')+'>Next</button></div></div></div></section>';
}
function driftTab(detail){
 const output=detail.report.agents.seller||{},changes=output.changes||[];
 return '<section><h2>Listing changes</h2><p class="muted small-text">Compares the supplied previous version or the preceding local import. It is not a live 30-day marketplace snapshot.</p>'+
 (changes.length?changes.map(c=>'<h3 class="small-text">'+esc(c.field[0].toUpperCase()+c.field.slice(1))+'</h3><div class="diff-row"><div class="diff-side before"><small>PREVIOUS INPUT</small>'+esc(c.field==="price"?money(c.before,detail.listing.currency):c.before)+'</div><div class="diff-side after"><small>CURRENT INPUT</small>'+esc(c.field==="price"?money(c.after,detail.listing.currency):c.after)+'</div></div>').join(""):stateView("No changes available","No differing previous version was provided. Import an updated listing with the same ID to compare it here.",null,"","file"))+'</section>'+
 '<section class="subsection"><h2>Price history</h2><div class="panel"><table aria-label="Supplied price history"><thead><tr><th scope="col">Recorded date</th><th scope="col">Price</th></tr></thead><tbody>'+detail.listing.price_history.map(p=>'<tr><td>'+esc(date(p.date))+'</td><td>'+esc(money(p.price,detail.listing.currency))+'</td></tr>').join("")+'</tbody></table></div></section>'+
 '<section class="subsection"><h2>Current listing description</h2><div class="panel panel-body small-text">'+esc(detail.listing.description)+'</div></section>';
}
function traceCards(execution,outputs){
 return '<div class="agent-grid">'+state.config.agents.map((a,index)=>{
 const log=execution?.find(l=>l.agent===a.id),output=outputs?.[a.id];
 return '<article class="agent-card"><div class="agent-top">'+icon(a.id==="orchestrator"?"network":a.id==="report"?"file":a.stage==="Ingest"?"database":"shield")+'<span class="agent-number">'+String(index+1).padStart(2,"0")+'</span></div><h3>'+esc(a.name)+'</h3><p>'+esc(a.role)+'</p>'+(output?.metrics&&Object.keys(output.metrics).length?'<pre class="agent-metrics">'+esc(JSON.stringify(output.metrics,null,2))+'</pre>':'')+
 '<div class="agent-card-footer"><span class="pill '+(log?.status==="failed"?'tone-danger':log?'tone-success':'subtle')+'">'+esc(log?log.status:"Ready")+'</span><span>'+esc(log?log.duration_ms+' ms · '+log.attempts+' attempt'+(log.attempts>1?'s':''):a.stage)+'</span></div></article>';
 }).join("")+'</div>';
}
function reviewSidebar(detail){
 const draft=state.reviewDraft?.id===detail.listing.id?state.reviewDraft:null;
 return '<aside class="panel review-panel"><form id="review-form" class="panel-body" novalidate><div class="review-intro"><span class="eyebrow">HUMAN REVIEW</span><h2>Your decision, recorded.</h2><p>Assess the evidence and save your review. This changes only the local case status.</p></div>'+
 '<div class="form-field"><label for="review-status">Review status</label><select id="review-status">'+Object.entries(statusNames).map(([v,t])=>'<option value="'+v+'" '+((draft?.status||detail.summary.status)===v?'selected':'')+'>'+t+'</option>').join("")+'</select></div>'+
 '<div class="form-field"><label for="review-notes">Reviewer notes</label><textarea id="review-notes" maxlength="4000" style="resize: none" placeholder="Record what you checked and what needs follow-up…" aria-describedby="review-error review-notes-hint">'+esc(draft?.notes??detail.notes)+'</textarea><p id="review-notes-hint" class="field-hint">Saved on this computer · Up to 4,000 characters</p></div>'+
 '<div id="review-error" class="form-error" role="alert" hidden></div><div id="review-feedback" class="form-success" role="status"></div><button type="submit" id="save-review" class="btn primary" '+(state.reviewBusy?'disabled':'')+'>'+icon("check")+'Save review</button>'+
 '<div class="export-actions">'+(detail.report?'<a class="btn" href="/api/listings/'+encodeURIComponent(detail.listing.id)+'/report" download>'+icon("download")+'Download JSON report</a><button type="button" class="btn" data-action="export-markdown">'+icon("file")+'Download readable report</button>':'')+'<button type="button" class="btn analyze-button" data-action="analyze-one" '+(state.job?'disabled':'')+'>'+icon("refresh")+'Analyze this listing</button></div>'+
 '<div class="review-reminder">'+icon("shield")+'<span>No automatic approvals or delisting. Marketplace enforcement requires a human decision.</span></div></form></aside>';
}
function detailView(detail){
 const item=detail.listing,report=detail.report,scoring=report?.scoring;
 const selected=["evidence","reviews","changes","trace"].includes(query().get("tab"))?query().get("tab"):"evidence";
 const color=scoring?.risk==="high"?"var(--color-danger)":scoring?.risk==="medium"?"#dda53f":"#369c84";
 let content=report?(selected==="reviews"?reviewsTab(detail):selected==="changes"?driftTab(detail):selected==="trace"?traceCards(report.execution,report.agents):evidenceTab(detail)):stateView("Ready for analysis","Run the ten-agent pipeline to generate evidence, a trust score, and a reviewer report.","analyze-one","Analyze this listing","network");
 return '<a class="back-link" href="'+link("listings")+'">'+icon("back")+'Back to listing review</a><div class="listing-heading">'+art(item.illustration,true)+'<div><div class="listing-meta"><span class="mono">'+esc(item.id)+'</span><span>'+esc(item.category)+'</span>'+(detail.summary.synthetic?'<span class="pill blue">Synthetic sample</span>':'')+'</div><h1 tabindex="-1">'+esc(item.title)+'</h1><div class="listing-meta"><span>'+esc(item.seller.name)+'</span><span>·</span><strong>'+esc(money(item.price,item.currency))+'</strong><span>·</span><span>'+fmt(item.reviews.length)+' reviews</span><span>·</span><span>'+esc(item.region)+' screening preset</span></div></div></div>'+
 '<div class="detail-layout"><div class="detail-main">'+(report?'<section class="panel"><div class="trust-summary"><div class="score-ring" style="background:conic-gradient('+color+' 0 '+Number(scoring.trust_score||0)+'%, #e8eef5 '+Number(scoring.trust_score||0)+'% 100%)"><strong>'+fmt(scoring.trust_score)+'<small>TRUST / 100</small></strong></div><div class="trust-summary-text">'+badge(scoring.risk)+'<p>'+esc(report.report.summary)+'</p><div class="coverage"><strong>'+Math.round(scoring.coverage*100)+'% evidence coverage</strong> · '+(report.partial?'Partial analysis':'Pipeline completed')+' · '+esc(datetime(report.generated_at))+'</div></div></div><div class="signal-lanes">'+scoring.components.map(c=>'<div class="signal-lane"><div class="lane-top"><span>'+esc(c.agent==="authenticity"?"Reviews":c.agent==="images"?"Image metadata":c.agent[0].toUpperCase()+c.agent.slice(1))+' · '+Math.round(c.weight*100)+'%</span><strong>'+fmt(c.score)+'</strong></div><div class="mini-track"><span class="'+(c.score<50?"high":c.score<75?"medium":"low")+'" style="width:'+Number(c.score||0)+'%"></span></div></div>').join("")+'</div></section>':'')+
 '<div class="tabs" role="tablist" aria-label="Listing evidence sections">'+[["evidence","Evidence & claims"],["reviews","Reviews"],["changes","Listing changes"],["trace","Agent trace"]].map(([key,label])=>'<button id="tab-'+key+'" class="tab" role="tab" aria-selected="'+(selected===key)+'" aria-controls="detail-tab-panel" tabindex="'+(selected===key?0:-1)+'" data-action="detail-tab" data-tab="'+key+'">'+label+'</button>').join("")+'</div><section id="detail-tab-panel" role="tabpanel" aria-labelledby="tab-'+selected+'" class="tab-content">'+content+'</section>'+
 '<section class="subsection"><h2>Local audit trail</h2><div class="panel panel-body"><ul class="activity-list">'+detail.events.slice(0,5).map(e=>'<li><span class="activity-dot"></span><div>'+esc(e.message)+'<small>'+esc(datetime(e.created_at))+'</small></div></li>').join("")+'</ul></div></section></div>'+reviewSidebar(detail)+'</div>';
}
function agentsView(){
 return heading("The agent pipeline","Ten focused agents. Explicit handoffs. Evidence you can inspect.",false)+
 '<div class="info-banner" style="margin-bottom:23px">'+icon("info")+'<div><strong>Every finding has an evidence trail.</strong> The pipeline checks listing claims, review patterns, seller behavior, and supplied image metadata, then prepares a report for human review.</div></div>'+
 '<div class="flow-map">'+[["01 / INGEST","Structure the evidence","Listing normalization and UTC review cohorts."],["02 / DETECT","Cross-check signals","Five independent agents run concurrently."],["03 / AGGREGATE","Weigh the findings","Severity × confidence with missing-data coverage."],["04 / REPORT","Support the reviewer","Rank actions and preserve a complete agent trace."]].map((s,i)=>'<div class="flow-stage"><span class="eyebrow">'+s[0]+'</span><h3>'+s[1]+'</h3><p>'+s[2]+'</p></div>'+(i<3?'<span class="flow-arrow">'+icon("arrow")+'</span>':'')).join("")+'</div>'+
 traceCards(null,null)+'<div class="info-banner" style="margin-top:23px">'+icon("refresh")+'<div><strong>Failures remain visible.</strong> The orchestrator retries a failed analytical agent once, excludes unavailable evidence from weighted scoring, and marks the report as partial. See execution details in any listing’s Agent trace.</div></div>'+
 '<section class="subsection"><h2>How the trust score is calculated</h2><div class="panel panel-body dataset-note"><p>Each component starts at 100. A finding subtracts its configured impact multiplied by its heuristic confidence; component scores are clamped to 0–100. The final score is the weighted average of available components.</p><p><strong>Listing compliance 25% · Review authenticity 40% · Seller behavior 25% · Image metadata 10%.</strong></p><p>Unavailable components are excluded, then the remaining weights are normalized. Metadata-only image checks receive 40% of their weight in evidence coverage. Below 50% coverage, the result is marked insufficient evidence. Otherwise: high risk below 50, medium risk 50–74, low risk 75–100.</p><p>A high-severity finding with at least 85% heuristic confidence and impact 20 or more caps trust at 74. A health claim promising a cure or guaranteed outcome caps trust at 49. These caps prevent averaging away consequential signals. Confidence values are heuristic settings, not statistically calibrated probabilities.</p></div></section>';
}
function captureReviewDraft(){
 const notes=$("#review-notes"),status=$("#review-status");
 if(notes&&status&&state.detail)state.reviewDraft={id:state.detail.listing.id,notes:notes.value,status:status.value};
}
function dirtyReview(){
 const d=state.reviewDraft,detail=state.detail;
 return Boolean(d&&detail&&d.id===detail.listing.id&&(d.notes!==detail.notes||d.status!==detail.summary.status));
}
let previousURL=location.href,pendingURL=null,discardMode="import";
function showDiscard(mode,url=null){
 discardMode=mode;pendingURL=url;
 $("#discard-title").textContent=mode==="review"?"Discard unsaved review notes?":"Discard the import draft?";
 $("#discard-dialog p").textContent=mode==="review"?"Your unsaved notes and status changes will be cleared. Saved reviews remain in the audit trail.":"Your pasted JSON or selected file will be cleared.";
 $("#discard-dialog").showModal();
 $(".btn.primary",$("#discard-dialog")).focus();
}
async function renderRoute(focus=true){
 captureReviewDraft();
 const token=++state.routeToken,info=routeInfo(),main=$("#main"),focusInfo=!focus?preserveFocus():null;
 const label={overview:"Overview",listings:"Listing review",listing:"Listing evidence",agents:"Agent pipeline"}[info.view]||"Page not found";
 $("#breadcrumb-current").textContent=label;
 document.title=label+" — TrustLens";
 $$("[data-nav]").forEach(a=>{const active=a.dataset.nav===(info.view==="listing"?"listings":info.view);a.classList.toggle("active",active);if(active)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");});
 if(focus)main.innerHTML='<div class="loading-state" role="status"><span class="spinner"></span>Loading '+esc(label.toLowerCase())+'…</div>';
 try{
   if(!state.config)state.config=await api("/api/config");
   let html;
   if(info.view==="overview"){const data=await api("/api/overview");if(token!==state.routeToken)return;state.overview=data;html=overviewView(data);}
   else if(info.view==="listings"){const data=await api("/api/listings"+location.search);if(token!==state.routeToken)return;html=listView(data);}
   else if(info.view==="listing"&&info.id){
     const detail=await api("/api/listings/"+encodeURIComponent(info.id));
     if(token!==state.routeToken)return;
     if(state.reviewDraft&&state.reviewDraft.id!==detail.listing.id)state.reviewDraft=null;
     state.detail=detail;html=detailView(detail);
   }else if(info.view==="agents")html=agentsView();
   else html=stateView("Page not found","Choose a workspace view using the navigation.","go-overview","Open overview");
   if(token!==state.routeToken)return;
   main.innerHTML=html;
   if(state.overview)$("#queue-count").textContent=fmt(state.overview.totals.needs_review);
   if(focus){$("h1",main)?.focus({preventScroll:true});window.scrollTo(0,0);}else restoreFocus(focusInfo);
   previousURL=location.href;
 }catch(error){
   if(token!==state.routeToken)return;
   if(!focus&&main.children.length&&!$(".loading-state",main)){
     $(".route-error",main)?.remove();
     const div=document.createElement("div");div.className="form-error route-error";div.setAttribute("role","alert");
     div.innerHTML=esc(error.message)+' <button class="text-btn" data-action="retry">Retry</button>';main.prepend(div);
   }else main.innerHTML='<section class="panel">'+stateView("Could not load this view",error.message)+'</section>';
 }
}
async function refreshOverview(){state.overview=await api("/api/overview");$("#queue-count").textContent=fmt(state.overview.totals.needs_review);}
function setAnalyzing(busy){$$(".analyze-button").forEach(b=>{b.disabled=busy;b.setAttribute("aria-busy",String(busy));});}
async function startAnalysis(ids){
 if(state.job)return;
 setAnalyzing(true);
 try{
   const body=ids?{listing_ids:ids}:{};
   state.job=await api("/api/analyze",{method:"POST",body:JSON.stringify(body)});
   localStorage.setItem("trustlens-job",state.job.id);
   pollJob();
 }catch(error){
   setAnalyzing(false);
   const banner=$("#job-banner");banner.hidden=false;
   banner.innerHTML=icon("alert")+'<span>'+esc(error.message)+'</span><button class="text-btn" data-action="retry-analysis">Retry</button><button class="icon-btn" data-action="dismiss-job" aria-label="Dismiss analysis error">'+icon("close")+'</button>';
   notify(error.message,true);
 }
}
async function pollJob(){
 if(!state.job)return;
 const banner=$("#job-banner");banner.hidden=false;
 try{
   const job=await api("/api/jobs/"+state.job.id);state.job=job;
   banner.innerHTML='<span class="spinner"></span><span>Analyzing listings <strong>'+job.completed+' / '+job.total+'</strong>'+(job.current?' · '+esc(job.current):'')+'</span><span class="job-progress"><span style="width:'+(job.completed/job.total*100)+'%"></span></span>';
   setAnalyzing(true);
   if(["completed","partial"].includes(job.status)){
     state.job=null;localStorage.removeItem("trustlens-job");setAnalyzing(false);
     if(job.errors.length){banner.innerHTML=icon("alert")+'<span>Analysis finished with '+job.errors.length+' errors. '+esc(job.errors[0].message)+'</span><button class="text-btn" data-action="retry-analysis">Retry</button><button class="icon-btn" data-action="dismiss-job" aria-label="Dismiss analysis result">'+icon("close")+'</button>';}
     else{banner.hidden=true;notify("Analysis complete. "+job.total+" listing"+(job.total===1?"":"s")+" updated.");}
     await refreshOverview();await renderRoute(false);
   }else setTimeout(pollJob,400);
 }catch(error){
   banner.innerHTML=icon("alert")+'<span>'+esc(error.message)+'</span><button class="text-btn" data-action="retry-job">Check status</button><button class="text-btn" data-action="forget-job">Dismiss</button>';
 }
}
function openImport(){
 if(state.job){notify("Wait for the current analysis to finish before importing.");return;}
 $("#import-error").hidden=true;$("#import-dialog").showModal();$("#dataset-file").focus();
}
function closeImport(){
 if(state.importing)return;
 if($("#dataset-json").value.trim()||$("#dataset-file").files.length)showDiscard("import");
 else $("#import-dialog").close();
}
function clearImport(){
 $("#import-form").reset();$("#file-description").textContent=".json files · 16 MB maximum";
 $("#import-error").hidden=true;$("#dataset-json").removeAttribute("aria-invalid");$("#dataset-file").removeAttribute("aria-invalid");
}
function importError(message,field="dataset-json"){
 const error=$("#import-error");error.textContent=message;error.hidden=false;
 const input=document.getElementById(field);input.setAttribute("aria-invalid","true");input.setAttribute("aria-describedby","import-error");input.focus();
}
async function importDataset(event){
 event.preventDefault();if(state.importing)return;
 state.importing=true;
 const submitButton=$("#import-submit");submitButton.disabled=true;submitButton.setAttribute("aria-busy","true");
 let payload;
 try{
   const file=$("#dataset-file").files[0];
   let raw=$("#dataset-json").value;
   if(file){
     if(file.size>16*1024*1024)throw new Error("The file exceeds 16 MB. Split it into smaller datasets.");
     if(!file.name.toLowerCase().endsWith(".json"))throw new Error("Choose a .json file. ZIP files are for submission, not import.");
     raw=await file.text();
   }
   if(!raw.trim())throw new Error("Choose a JSON file or paste a dataset before importing.");
   if(new TextEncoder().encode(raw).length>16*1024*1024)throw new Error("The JSON exceeds 16 MB. Split it into smaller datasets.");
   try{payload=JSON.parse(raw);}catch{throw new Error('The JSON is invalid. Check quotes, commas, and the outer {"listings": [...]} object.');}
   if(!payload||!Array.isArray(payload.listings)||payload.listings.length===0)throw new Error('The JSON must contain a non-empty "listings" array.');
 }catch(error){state.importing=false;submitButton.disabled=false;submitButton.setAttribute("aria-busy","false");importError(error.message,$("#dataset-file").files.length?"dataset-file":"dataset-json");return;}
 state.importing=true;
 const button=$("#import-submit");button.disabled=true;button.setAttribute("aria-busy","true");button.textContent="Import & analyze";
 $("#import-error").hidden=true;
 try{
   const response=await api("/api/import",{method:"POST",body:JSON.stringify(payload)});
   clearImport();$("#import-dialog").close();
   await refreshOverview();
   if(routeInfo().view!=="listings")navigate("listings");else await renderRoute(false);
   notify("Imported "+response.imported+" listing"+(response.imported===1?"":"s")+". Starting analysis.");
   await startAnalysis(response.listing_ids);
 }catch(error){importError(error.message);}
 finally{state.importing=false;button.disabled=false;button.setAttribute("aria-busy","false");}
}
async function saveReview(event){
 event.preventDefault();if(state.reviewBusy||!state.detail)return;
 captureReviewDraft();const detail=state.detail,draft=state.reviewDraft;
 const button=$("#save-review");button.disabled=true;button.setAttribute("aria-busy","true");state.reviewBusy=true;
 $("#review-error").hidden=true;$("#review-feedback").textContent="";
 try{
   const response=await api("/api/listings/"+encodeURIComponent(detail.listing.id)+"/decision",{method:"POST",body:JSON.stringify({status:draft.status,notes:draft.notes,version:detail.summary.version})});
   state.detail=response;state.reviewDraft=null;await refreshOverview();
   if(routeInfo().id===detail.listing.id){$("#review-feedback").textContent="Review saved. Your decision is in the local audit trail.";$("#review-notes").value=response.notes;$("#review-status").value=response.summary.status;}
   notify("Review saved.");
 }catch(error){const el=$("#review-error");if(el){el.textContent=error.message;el.hidden=false;}notify(error.message,true);}
 finally{state.reviewBusy=false;if(button.isConnected){button.disabled=false;button.setAttribute("aria-busy","false");}}
}
function downloadReadable(){
 const d=state.detail,r=d?.report;if(!r)return;
 const lines=["# TrustLens evidence report","",d.listing.title,"Listing: "+d.listing.id,
 "Generated: "+r.generated_at,"Trust: "+r.scoring.trust_score+"/100","Risk: "+names[r.scoring.risk],
 "Evidence coverage: "+Math.round(r.scoring.coverage*100)+"%","Engine: "+r.report.engine,"",r.report.summary,
 "","## Findings","",...r.scoring.findings.flatMap(f=>["### "+f.title+" ("+f.severity+")",f.detail,
 "Evidence: "+JSON.stringify(f.evidence),"Action: "+f.action,"Heuristic confidence: "+Math.round(f.confidence*100)+"%",""]),
 "## Seller evidence request",sellerRequestText(d),"","## Reviewer record","Status: "+statusNames[d.summary.status],"Notes: "+d.notes,"",
 "## Limitations","",...r.report.limitations.map(l=>"- "+l),"","Human review required. No marketplace enforcement has been performed."];
 const blob=new Blob([lines.join("\n")],{type:"text/markdown;charset=utf-8"}),url=URL.createObjectURL(blob);
 const a=document.createElement("a");a.href=url;a.download=d.listing.id+"-trust-report.md";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 notify("Readable report downloaded.");
}
document.addEventListener("click",async event=>{
 const anchor=event.target.closest('a[href*="#"]');
 if(anchor&&anchor.getAttribute("href")!=="#main"){
   captureReviewDraft();
   const target=new URL(anchor.href),next=target.hash.slice(1);
   if(dirtyReview()&&next!=="listing/"+state.detail?.listing.id){event.preventDefault();showDiscard("review",target.href);return;}
 }
 const target=event.target.closest("[data-action]");if(!target||target.disabled)return;
 const action=target.dataset.action;
 try{
 if(action==="open-import")openImport();
 else if(action==="close-import")closeImport();
 else if(action==="keep-draft")$("#discard-dialog").close();
 else if(action==="discard-draft"){
   $("#discard-dialog").close();
   if(discardMode==="import"){clearImport();$("#import-dialog").close();}
   else{state.reviewDraft=null;state.detail=null;const url=pendingURL;pendingURL=null;if(url){history.pushState(null,"",url);await renderRoute();}}
 }
 else if(action==="load-template"){
   target.disabled=true;
   try{const example={id:"MY-001",title:"Product title",description:"Provide the product specifications, claims, warranty, and return terms.",category:"Electronics",price:999,currency:"INR",region:"IN",seller:{id:"SELLER-001",name:"Seller name",created_at:"2025-01-01T00:00:00Z"},reviews:[],images:[],certifications:[],price_history:[]};$("#dataset-file").value="";$("#file-description").textContent=".json files · 16 MB maximum";$("#dataset-json").value=JSON.stringify({listings:[example]},null,2);$("#dataset-json").focus();}finally{target.disabled=false;}
 }
 else if(action==="retry")renderRoute(false);
 else if(action==="go-overview")navigate("overview");
 else if(action==="analyze-all"||action==="retry-analysis"){if(action==="retry-analysis")$("#job-banner").hidden=true;startAnalysis();}
 else if(action==="analyze-one")startAnalysis([state.detail.listing.id]);
 else if(action==="retry-job")pollJob();
 else if(action==="forget-job"){state.job=null;localStorage.removeItem("trustlens-job");$("#job-banner").hidden=true;setAnalyzing(false);}
 else if(action==="dismiss-job")$("#job-banner").hidden=true;
 else if(action==="clear-search"){clearTimeout(searchTimer);setQuery("q","");setTimeout(()=>$("#listing-search")?.focus(),100);}
 else if(action==="reset-filters"){clearTimeout(searchTimer);const url=new URL(location.href);["q","risk","category","status","page"].forEach(k=>url.searchParams.delete(k));history.replaceState(null,"",url);await renderRoute(false);}
 else if(action==="clear-filter")setQuery(target.dataset.key,"");
 else if(action==="sort")setQuery("sort",target.dataset.sort);
 else if(action==="page")setQuery("page",target.dataset.page);
 else if(action==="detail-tab"){captureReviewDraft();setQuery("tab",target.dataset.tab);}
 else if(action==="review-page")setQuery("rp",target.dataset.page);
 else if(action==="export-markdown")downloadReadable();
 else if(action==="copy-seller-request")await copySellerRequest();
 }catch(error){notify(error.message,true);}
});
document.addEventListener("change",event=>{
 const target=event.target;
 if(target.matches("[data-filter]"))setQuery(target.dataset.filter,target.value);
 if(target.id==="dataset-file"){
   $("#dataset-json").value="";
   $("#file-description").textContent=target.files[0]?target.files[0].name+" · "+fmt(Math.round(target.files[0].size/1024))+" KB":".json files · 16 MB maximum";
   $("#import-error").hidden=true;target.removeAttribute("aria-invalid");
 }
 if(target.id==="review-status")captureReviewDraft();
});
function commitSearch(target){clearTimeout(searchTimer);if(target.isComposing)return;const value=target.value.trim();searchTimer=setTimeout(()=>setQuery("q",value),300);}
document.addEventListener("input",event=>{
 if(event.target.id==="listing-search"){
   const clear=$(".clear-search");if(clear)clear.hidden=!event.target.value;
   if(!event.isComposing)commitSearch(event.target);
 }
 if(event.target.id==="review-notes")captureReviewDraft();
 if(event.target.id==="dataset-json"){$("#dataset-file").value="";$("#file-description").textContent=".json files · 16 MB maximum";$("#import-error").hidden=true;event.target.removeAttribute("aria-invalid");}
});
document.addEventListener("compositionstart",event=>{if(event.target.id==="listing-search")clearTimeout(searchTimer);});
document.addEventListener("compositionend",event=>{if(event.target.id==="listing-search")commitSearch(event.target);});
document.addEventListener("keydown",event=>{
 if(event.target.id==="listing-search"&&event.key==="Enter"&&!event.isComposing){event.preventDefault();clearTimeout(searchTimer);setQuery("q",event.target.value.trim());}
 if(event.target.getAttribute("role")==="tab"&&["ArrowLeft","ArrowRight","Home","End"].includes(event.key)){
   event.preventDefault();const tabs=$$('[role="tab"]'),index=tabs.indexOf(event.target);
   const next=event.key==="Home"?0:event.key==="End"?tabs.length-1:(index+(event.key==="ArrowRight"?1:-1)+tabs.length)%tabs.length;
   tabs[next].click();setTimeout(()=>document.getElementById(tabs[next].id)?.focus(),100);
 }
});
document.addEventListener("submit",event=>{if(event.target.id==="import-form")importDataset(event);if(event.target.id==="review-form")saveReview(event);});
$("#import-dialog").addEventListener("cancel",event=>{event.preventDefault();closeImport();});
window.addEventListener("hashchange",()=>{
 captureReviewDraft();
 if(dirtyReview()&&routeInfo().id!==state.detail?.listing.id){const target=location.href;history.replaceState(null,"",previousURL);showDiscard("review",target);return;}
 clearTimeout(searchTimer);renderRoute();
});

window.addEventListener("beforeunload",event=>{captureReviewDraft();if(dirtyReview()||$("#dataset-json").value.trim()||$("#dataset-file").files.length){event.preventDefault();event.returnValue="";}});
async function boot(){
 hydrateIcons();
 try{
   [state.config,state.overview]=await Promise.all([api("/api/config"),api("/api/overview")]);
   await renderRoute();
   const job=localStorage.getItem("trustlens-job");
   if(job){try{const previous=await api("/api/jobs/"+job);if(["running","queued"].includes(previous.status)){state.job=previous;pollJob();}else localStorage.removeItem("trustlens-job");}catch{localStorage.removeItem("trustlens-job");}}
 }catch(error){$("#main").innerHTML='<section class="panel">'+stateView("Your workspace is unavailable",error.message)+'</section>';}
}
boot();
