class SkyWatchRadar extends HTMLElement {
  static getStubConfig() { return { type: "custom:skywatch-radar" }; }
  static getConfigElement() { return document.createElement("ha-form"); }
  setConfig(config) {
    this.config = { title: "SkyWatch Radar", refresh_seconds: 2, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._filters = { labels: true, tracks: true, airborne: false };
    this._rangeKm = null;
    this._blips = new Map();
    this._lastSweep = null;
    this._borders = [];
    this._coastlines = [];
    this._lakes = [];
    this._worldRequestKey = null;
    this._centerMode = false;
    this._previewCenter = null;
    this._dragStart = null;
    this._centerSaving = false;
    this._suppressPickUntil = 0;
    this._render();
  }
  set hass(hass) {
    this._hass = hass;
    if (!this._started) { this._started = true; this._start(); }
    this._updateStatus();
  }
  disconnectedCallback() { clearInterval(this._timer); cancelAnimationFrame(this._frame); }
  getCardSize() { return 8; }
  _start() {
    this._fetch();
    this._timer = setInterval(() => this._fetch(), Math.max(1, this.config.refresh_seconds) * 1000);
    const tick = () => { this._sweep = (performance.now() / 35) % 360; this._draw(); this._frame = requestAnimationFrame(tick); };
    tick();
  }
  async _loadWorldTiles(center) {
    if (!center) return;
    const radius = Math.min(250, Math.max(10, Number(center.radius_km) || 250));
    const latMargin = radius / 111.32 + .3;
    const lonMargin = Math.min(179, radius / (111.32 * Math.max(.08, Math.cos(center.lat * Math.PI / 180))) + .3);
    const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
    const latStart = Math.floor((clamp(center.lat - latMargin, -90, 89.999) + 90) / 10), latEnd = Math.floor((clamp(center.lat + latMargin, -90, 89.999) + 90) / 10);
    const lonStart = Math.floor((clamp(center.lon - lonMargin, -180, 179.999) + 180) / 10), lonEnd = Math.floor((clamp(center.lon + lonMargin, -180, 179.999) + 180) / 10);
    const names = []; for(let lat=latStart;lat<=latEnd;lat++)for(let lon=lonStart;lon<=lonEnd;lon++)names.push(`${lat}_${lon}`);
    const key = names.join(","); if (key === this._worldRequestKey) return; this._worldRequestKey = key;
    const tiles = await Promise.all(names.map(async name => { try { const response = await fetch(`/skywatch-radar-assets/world/${name}.json?v=2.1.1`, {cache:"force-cache"}); return response.ok ? await response.json() : null; } catch (_) { return null; } }));
    if (this._worldRequestKey !== key) return;
    this._borders = tiles.flatMap(tile => Array.isArray(tile?.borders) ? tile.borders : []);
    this._coastlines = tiles.flatMap(tile => Array.isArray(tile?.coastlines) ? tile.coastlines : []);
    this._lakes = tiles.flatMap(tile => Array.isArray(tile?.lakes) ? tile.lakes : []);
    this._draw();
  }
  async _fetch() {
    if (!this._hass?.connection) return;
    try {
      this._payload = await this._hass.connection.sendMessagePromise({ type: "skywatch_radar/aircraft", entry_id: this.config.entry_id });
      if (!this._rangeKm) this._rangeKm = Math.min(150, this._payload.center?.radius_km || 150);
      this._loadWorldTiles(this._payload.center);
      if (this._previewCenter && Math.abs(this._payload.center.lat-this._previewCenter.lat)<.00001 && Math.abs(this._payload.center.lon-this._previewCenter.lon)<.00001) { this._previewCenter=null; this._centerSaving=false; }
      this._error = null;
    } catch (error) { this._error = error?.message || "WebSocket niet beschikbaar"; }
    this._updateStatus(); this._draw();
  }
  _render() {
    this.shadowRoot.innerHTML = `<style>
      :host{display:block} ha-card{overflow:hidden;background:#06120d;color:#d7ffe8;min-height:500px}
      header{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:#092419;border-bottom:1px solid #185e42;font:600 15px system-ui}
      .live{font-size:11px;color:#77f7b1}.bad{color:#ff9978}.stage{position:relative;aspect-ratio:1.28;min-height:420px;background:radial-gradient(circle,#092519 0,#04100b 72%)} canvas{position:absolute;inset:0;width:100%;height:100%;touch-action:manipulation}
      .controls{position:absolute;top:9px;left:9px;display:flex;gap:5px;flex-wrap:wrap}.controls button{background:#0d3525;color:#b9ffd4;border:1px solid #2b8a60;border-radius:14px;padding:4px 8px;font-size:11px}.controls button.off{opacity:.45}.controls button.active{background:#1c704a;color:#fff}
      .detail,.legend{position:absolute;right:9px;top:9px;max-width:245px;background:#061b12f2;border:1px solid #2b8a60;border-radius:8px;padding:9px;font:12px system-ui;display:none;line-height:1.35}.detail.show,.legend.show{display:block}.detail b,.legend b{display:block;color:#8cffbf;margin-bottom:4px}.detail .grid,.legend .grid{display:grid;grid-template-columns:auto 1fr;gap:2px 7px}.detail .key,.legend .key{color:#8eae9c}.detail .alert{color:#ff9978;font-weight:700}.legend{max-width:270px}.legend .example{font:600 11px ui-monospace,SFMono-Regular,Consolas,monospace;color:#d7ffe8;margin:3px 0 6px}.legend .note{color:#8eae9c;margin-top:6px}.foot{padding:7px 13px;font:11px system-ui;color:#92b9a2;display:flex;justify-content:space-between;gap:10px}.foot a{color:#8cffbf}
      @media(max-width:600px){.stage{min-height:360px;aspect-ratio:1}.detail{top:auto;bottom:8px;right:8px}.controls{max-width:85%}}
    </style><ha-card><header><span>◉ ${this.config.title}</span><span id="status" class="live">verbinden…</span></header><div class="stage"><canvas></canvas><div class="controls"><button data-f="labels">labels</button><button data-f="tracks">sporen</button><button data-f="airborne">in vlucht</button><button data-r="-">− bereik</button><button data-r="+">+ bereik</button><button data-center>centrum</button><button data-legend>legenda</button></div><div class="detail"></div><div class="legend"><b>Contactlabel</b><div class="example">KLM300<br>260&nbsp;&nbsp;450<br>140&nbsp;&nbsp;+00<br>B762</div><div class="grid"><span class="key">Regel 1</span><span>callsign</span><span class="key">Regel 2</span><span>flight level (×100 ft) · grondsnelheid in knopen</span><span class="key">Regel 3</span><span>koers in graden · verticale snelheid (×100 ft/min)</span><span class="key">Regel 4</span><span>ICAO-vliegtuigtype</span></div><div class="note">--- betekent: waarde niet ontvangen. De heldere pijl is een recente radarblip.</div></div></div><div class="foot"><span id="meta">Cache via Home Assistant</span><span><a href="https://adsb.fi/" target="_blank" rel="noreferrer">ADSB.fi</a> · <a href="https://www.naturalearthdata.com/" target="_blank" rel="noreferrer">kaart: Natural Earth</a> · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OSM</a></span></div></ha-card>`;
    this._canvas = this.shadowRoot.querySelector("canvas"); this._detail = this.shadowRoot.querySelector(".detail"); this._legend=this.shadowRoot.querySelector(".legend");
    this.shadowRoot.querySelectorAll("[data-f]").forEach(b => b.onclick = () => { const f=b.dataset.f; this._filters[f]=!this._filters[f]; b.classList.toggle("off",!this._filters[f]); this._draw(); });
    this.shadowRoot.querySelectorAll("[data-r]").forEach(b => b.onclick = () => { const max=this._payload?.center?.radius_km||400; this._rangeKm=Math.max(10,Math.min(max,this._rangeKm+(b.dataset.r==='+'?10:-10))); this._draw(); });
    this._centerButton=this.shadowRoot.querySelector("[data-center]"); this._centerButton.onclick=()=>{this._centerMode=!this._centerMode;this._previewCenter=null;this._centerButton.classList.toggle("active",this._centerMode);this._canvas.style.cursor=this._centerMode?"grab":"default";this._draw();};
    this._legendButton=this.shadowRoot.querySelector("[data-legend]"); this._legendButton.onclick=()=>{const visible=this._legend.classList.toggle("show");this._legendButton.classList.toggle("active",visible);if(visible)this._detail.classList.remove("show");};
    this._canvas.addEventListener("click", e => this._pick(e));
    this._canvas.addEventListener("pointerdown", e => this._beginCenterDrag(e));
    this._canvas.addEventListener("pointermove", e => this._moveCenterDrag(e));
    this._canvas.addEventListener("pointerup", e => this._endCenterDrag(e));
    this._canvas.addEventListener("pointercancel", () => this._cancelCenterDrag());
    new ResizeObserver(() => this._draw()).observe(this._canvas);
  }
  _updateStatus() {
    const status=this.shadowRoot?.querySelector("#status"), meta=this.shadowRoot?.querySelector("#meta"), p=this._payload;
    if (!status || !meta) return;
    if (this._centerSaving) { status.textContent="centrum bijwerken…"; status.className="live"; meta.textContent="Nieuwe regio laden via ADSB.fi…"; return; }
    if (this._error) { status.textContent="offline"; status.className="bad"; meta.textContent=this._error; return; }
    const s=p?.status; status.textContent=s?.online ? "● live" : "● cache/storing"; status.className=s?.online?"live":"bad";
    meta.textContent=`${p?.aircraft?.length ?? 0} toestellen · ${this._rangeKm ?? "–"} km · centrale poll ${s?.poll_interval_seconds ?? 10}s${p?.stale ? " · verouderde cache" : ""}`;
  }
  _geometry() {
    const rect=this._canvas.getBoundingClientRect(), dpr=devicePixelRatio||1; this._canvas.width=rect.width*dpr;this._canvas.height=rect.height*dpr;
    const c=this._canvas.getContext("2d");c.setTransform(dpr,0,0,dpr,0,0); return {c,w:rect.width,h:rect.height,cx:rect.width/2,cy:rect.height/2,r:Math.min(rect.width,rect.height)*.43};
  }
  _center() { return this._previewCenter||this._payload?.center; }
  _project(lat,lon,g) {
    const center=this._center();if(!center)return null;const y=(lat-center.lat)*111.32;const x=(lon-center.lon)*111.32*Math.cos(center.lat*Math.PI/180);return {x:g.cx+x/this._rangeKm*g.r,y:g.cy-y/this._rangeKm*g.r};
  }
  _bearing(p,g) { return (Math.atan2(p.x-g.cx,g.cy-p.y)*180/Math.PI+360)%360; }
  _sweepPassed(bearing) { if(this._lastSweep===null)return false;const before=(this._lastSweep-bearing+360)%360,after=(this._sweep-bearing+360)%360;return after<before; }
  _esc(value) { return String(value ?? "–").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]); }
  _drawBorders(c,g) {
    if (!this._borders.length && !this._coastlines.length && !this._lakes.length) return;
    c.save(); c.beginPath(); c.arc(g.cx,g.cy,g.r,0,Math.PI*2); c.clip();
    c.strokeStyle="rgba(144,235,180,.85)"; c.lineWidth=1.15;
    for (const line of this._lakes) { c.beginPath(); let drawn=false; for (const point of line) { if(!Array.isArray(point)||point.length<2) continue; const p=this._project(point[1],point[0],g); if(!p) continue; if(drawn)c.lineTo(p.x,p.y);else{c.moveTo(p.x,p.y);drawn=true;} } if(drawn)c.stroke(); }
    c.strokeStyle="rgba(144,235,180,.85)"; c.lineWidth=1.45;
    for (const line of this._coastlines) { c.beginPath(); let drawn=false; for (const point of line) { if(!Array.isArray(point)||point.length<2) continue; const p=this._project(point[1],point[0],g); if(!p) continue; if(drawn)c.lineTo(p.x,p.y);else{c.moveTo(p.x,p.y);drawn=true;} } if(drawn)c.stroke(); }
    c.strokeStyle="rgba(112,205,149,.62)"; c.lineWidth=1.15; c.setLineDash([5,4]);
    for (const line of this._borders) { c.beginPath(); let drawn=false; for (const point of line) { if(!Array.isArray(point)||point.length<2) continue; const p=this._project(point[1],point[0],g); if(!p) continue; if(drawn)c.lineTo(p.x,p.y);else{c.moveTo(p.x,p.y);drawn=true;} } if(drawn)c.stroke(); }
    c.setLineDash([]); c.restore();
  }
  _draw() {
    if(!this._canvas||!this._payload)return; const g=this._geometry(),{c,cx,cy,r}=g;c.clearRect(0,0,g.w,g.h);
    c.strokeStyle="#1f744e";c.lineWidth=1;for(let i=1;i<=4;i++){c.beginPath();c.arc(cx,cy,r*i/4,0,Math.PI*2);c.stroke();c.fillStyle="#77c69b";c.font="10px system-ui";c.fillText(`${Math.round(this._rangeKm*i/4)} km`,cx+4,cy-r*i/4+12)}
    c.beginPath();c.moveTo(cx-r,cy);c.lineTo(cx+r,cy);c.moveTo(cx,cy-r);c.lineTo(cx,cy+r);c.stroke(); c.fillStyle="#baffd6";c.font="11px system-ui";c.fillText("N",cx-4,cy-r-6);
    this._drawBorders(c,g);
    c.save();c.translate(cx,cy);c.rotate((this._sweep-90)*Math.PI/180);const gr=c.createLinearGradient(0,0,r,0);gr.addColorStop(0,"rgba(38,255,130,.15)");gr.addColorStop(1,"rgba(38,255,130,0)");c.fillStyle=gr;c.beginPath();c.moveTo(0,0);c.arc(0,0,r,-.035,.035);c.fill();c.strokeStyle="#57ff9e";c.beginPath();c.moveTo(0,0);c.lineTo(r,0);c.stroke();c.restore();
    this._visible=[]; const now=performance.now(); for(const a of this._payload.aircraft||[]){if(a.distance_km>this._rangeKm|| (this._filters.airborne && !a.altitude_ft))continue;const p=this._project(a.lat,a.lon,g);if(!p)continue;this._visible.push({a,p}); if(this._sweepPassed(this._bearing(p,g)))this._blips.set(a.hex,now); const blipAge=now-(this._blips.get(a.hex)||-Infinity),flashing=blipAge>=0&&blipAge<750; if(this._filters.tracks&&a.track?.length>1){c.strokeStyle="rgba(94,255,167,.38)";c.beginPath();a.track.forEach((q,i)=>{const t=this._project(q[0],q[1],g);if(i)c.lineTo(t.x,t.y);else c.moveTo(t.x,t.y)});c.stroke()}c.save();c.translate(p.x,p.y);c.rotate(((a.track_deg||0)-90)*Math.PI/180);if(flashing){c.shadowColor="rgba(217,255,141,.65)";c.shadowBlur=7}c.fillStyle=flashing?"#ffffff":a.emergency!=="none"?"#ff795d":"#a8ffcf";c.beginPath();c.moveTo(5,0);c.lineTo(-3,-3);c.lineTo(-1,0);c.lineTo(-3,3);c.closePath();c.fill();c.restore();if(this._filters.labels){const call=a.flight||a.registration||a.hex,fl=a.altitude_ft===null?"---":String(Math.max(0,Math.round(a.altitude_ft/100))).padStart(3,"0"),gs=a.groundspeed_kt===null?"---":String(Math.round(a.groundspeed_kt)).padStart(3,"0"),course=a.track_deg===null?"---":String(Math.round(a.track_deg)).padStart(3,"0"),rate=a.vertical_rate_fpm===null?"---":`${a.vertical_rate_fpm>=0?"+":"-"}${String(Math.round(Math.abs(a.vertical_rate_fpm)/100)).padStart(2,"0")}`,type=(a.type||"----").toUpperCase(),rows=[call,`${fl}  ${gs}`,`${course}  ${rate}`,type],lx=p.x+11,ly=p.y-22;c.font="9px ui-monospace, SFMono-Regular, Consolas, monospace";const lw=Math.max(...rows.map(row=>c.measureText(row).width));c.fillStyle="rgba(3,20,12,.72)";c.fillRect(lx-3,ly-9,lw+6,42);c.fillStyle="#d7ffe8";rows.forEach((row,i)=>c.fillText(row,lx,ly+i*10));}} this._lastSweep=this._sweep;
    c.fillStyle="#79ffae";c.beginPath();c.arc(cx,cy,3,0,Math.PI*2);c.fill();if(this._centerMode){const center=this._center();c.strokeStyle="#d9ff8d";c.lineWidth=1.5;c.beginPath();c.moveTo(cx-8,cy);c.lineTo(cx+8,cy);c.moveTo(cx,cy-8);c.lineTo(cx,cy+8);c.stroke();c.fillStyle="#d9ff8d";c.font="10px system-ui";c.fillText(`nieuw centrum ${center.lat.toFixed(4)}, ${center.lon.toFixed(4)}`,cx+10,cy+16);}
  }
  _beginCenterDrag(e) { if(!this._centerMode||!this._payload?.center)return; e.preventDefault();const rect=this._canvas.getBoundingClientRect();this._dragStart={x:e.clientX-rect.left,y:e.clientY-rect.top,center:{...this._payload.center},rect};this._canvas.setPointerCapture?.(e.pointerId);this._canvas.style.cursor="grabbing"; }
  _moveCenterDrag(e) { const start=this._dragStart;if(!start)return;const x=e.clientX-start.rect.left,y=e.clientY-start.rect.top,dx=x-start.x,dy=y-start.y,r=Math.min(start.rect.width,start.rect.height)*.43,lat=start.center.lat+dy/r*this._rangeKm/111.32,lon=start.center.lon-dx/r*this._rangeKm/(111.32*Math.cos(start.center.lat*Math.PI/180));this._previewCenter={lat:Math.max(-90,Math.min(90,lat)),lon:((lon+540)%360)-180,radius_km:start.center.radius_km};this._draw(); }
  _endCenterDrag(e) { const start=this._dragStart;if(!start)return;this._dragStart=null;this._canvas.releasePointerCapture?.(e.pointerId);this._canvas.style.cursor="grab";const center=this._previewCenter;if(!center||Math.hypot(e.clientX-start.rect.left-start.x,e.clientY-start.rect.top-start.y)<6){this._previewCenter=null;this._draw();return;}this._suppressPickUntil=performance.now()+300;if(!window.confirm(`Radarcentrum opslaan op ${center.lat.toFixed(5)}, ${center.lon.toFixed(5)}? Nieuwe vliegtuigdata wordt binnen circa 10 seconden geladen.`)){this._previewCenter=null;this._draw();return;}this._saveCenter(center); }
  _cancelCenterDrag() { this._dragStart=null;this._previewCenter=null;this._canvas.style.cursor=this._centerMode?"grab":"default";this._draw(); }
  async _saveCenter(center) { this._centerSaving=true;this._centerMode=false;this._centerButton?.classList.remove("active");this._canvas.style.cursor="default";this._updateStatus();try{await this._hass.connection.sendMessagePromise({type:"skywatch_radar/set_center",entry_id:this.config.entry_id,latitude:center.lat,longitude:center.lon});}catch(error){this._centerSaving=false;this._previewCenter=null;this._error=error?.message||"Centrum kon niet worden opgeslagen";this._updateStatus();this._draw();} }
  _pick(e) { if(this._centerMode||performance.now()<this._suppressPickUntil)return;const rect=this._canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;let hit=null,best=22;for(const v of this._visible||[]){const d=Math.hypot(v.p.x-x,v.p.y-y);if(d<best){best=d;hit=v.a}}if(!hit){this._detail.classList.remove("show");return}this._legend?.classList.remove("show");this._legendButton?.classList.remove("active");const row=(k,v)=>`<span class="key">${k}</span><span>${this._esc(v)}</span>`;const identity=hit.flight||hit.registration||hit.hex;this._detail.innerHTML=`<b>${this._esc(identity)}</b><div>${this._esc(hit.description||hit.type||"Onbekend type")}</div><div class="grid">${row("Registratie",hit.registration)}${row("ICAO",hit.hex)}${row("Hoogte",`${hit.altitude_ft??"–"} ft`)}${row("Snelheid",`${hit.groundspeed_kt??"–"} kt`)}${row("Koers",`${hit.track_deg??"–"}°`)}${row("Verticale snelheid",`${hit.vertical_rate_fpm??"–"} ft/min`)}${row("Squawk",hit.squawk||"–")}${row("Categorie",hit.category||"–")}${row("Afstand",`${hit.distance_km} km`)}${row("Laatste positie",`${hit.seen_position_seconds??"–"} s`)}${hit.nav_altitude_ft!==null&&hit.nav_altitude_ft!==undefined?row("Geselecteerde hoogte",`${hit.nav_altitude_ft} ft`):""}${hit.signal_dbfs!==null&&hit.signal_dbfs!==undefined?row("Signaal",`${hit.signal_dbfs} dBFS`):""}</div>${hit.emergency!=="none"?`<div class="alert">NOOD: ${this._esc(hit.emergency)}</div>`:""}`;this._detail.classList.add("show"); }
}
customElements.define("skywatch-radar",SkyWatchRadar);
window.customCards=window.customCards||[];window.customCards.push({type:"skywatch-radar",name:"SkyWatch Radar",description:"Canvas ADSB.fi-radar met een centrale Home Assistant-cache"});
