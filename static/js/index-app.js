/* ═══════════════════════════════════════════════════════════════════
   OBIXConfig Doctor — index-app.js  v5.2 APEX
   Extracted from index.html · Pure JS · No Jinja2 dependencies
   Jinja2 data is injected via window.OBIX (set in index.html data bridge)
═══════════════════════════════════════════════════════════════════ */

/* ── Read OBIX data bridge (set by Jinja2 in index.html) ─────── */
let OBIX = window.OBIX || {
  analysis: false,
  pid: { pRoll:48, iRoll:90, dRoll:38, pPitch:52, iPitch:90, dPitch:40, pYaw:40, iYaw:90 },
  filter: { gLpf1:200, dLpf1:110, notch:2, ag:5 },
  charts: { hoverW:0, aggrW:0, peakW:0 },
  propRadar: null
};

/* ── Shorthand vars used across PRESETS / CLI builders ───────── */
let _pRoll  = OBIX.pid.pRoll,  _iRoll  = OBIX.pid.iRoll,  _dRoll  = OBIX.pid.dRoll;
let _pPitch = OBIX.pid.pPitch, _iPitch = OBIX.pid.iPitch, _dPitch = OBIX.pid.dPitch;
let _pYaw   = OBIX.pid.pYaw,   _iYaw   = OBIX.pid.iYaw;
let _gLpf1  = OBIX.filter.gLpf1, _dLpf1 = OBIX.filter.dLpf1;
let _notch  = OBIX.filter.notch,  _ag   = OBIX.filter.ag;
function _r(v){ return Math.max(1, Math.round(v)); }

/* ═══════════════════════════════════════════════════════════════
   LIVE PHYSICS ENGINE — updates HUD + Danger Zone + Checklist
   instantly as user types, no page reload needed
═══════════════════════════════════════════════════════════════ */

/* Module-level physics tables — created once, not per-keypress */
var _PHYS_MAX_PWR = {2.5:65,3:80,3.5:115,4:195,4.5:270,5:385,5.5:430,6:460,7:330,8:390,10:460};
var _PHYS_THRUST  = {2.5:130,3:170,3.5:280,4:400,4.5:540,5:730,5.5:760,6:720,7:640,7.5:620,8:680,10:700};
var _PHYS_WPG     = {2.5:0.38,3:0.35,3.5:0.24,4:0.19,4.5:0.17,5:0.155,5.5:0.165,6:0.20,7:0.108,8:0.095,10:0.085};
var _PHYS_SF      = {freestyle:1.55, racing:2.00, longrange:1.05};

function _physInterp(val, tbl) {
  var ks = Object.keys(tbl).map(Number).sort(function(a,b){return a-b;});
  if (val <= ks[0]) return tbl[ks[0]];
  if (val >= ks[ks.length-1]) return tbl[ks[ks.length-1]];
  for (var i = 0; i < ks.length-1; i++) {
    if (val >= ks[i] && val <= ks[i+1]) {
      var r = (val - ks[i]) / (ks[i+1] - ks[i]);
      return tbl[ks[i]] + r * (tbl[ks[i+1]] - tbl[ks[i]]);
    }
  }
  return tbl[ks[Math.floor(ks.length/2)]];
}

(function(){
  let STYLE_PID = {
    freestyle: { roll:{p:48,i:90,d:38}, pitch:{p:52,i:90,d:40}, yaw:{p:40,i:90} },
    racing:    { roll:{p:55,i:85,d:42}, pitch:{p:60,i:85,d:44}, yaw:{p:45,i:80} },
    longrange: { roll:{p:38,i:85,d:22}, pitch:{p:40,i:85,d:24}, yaw:{p:32,i:82} },
  };

  let SIZE_CLASSES = {
    2.5:'2.5" Micro', 3:'3" Whoop', 3.5:'3.5" Cinewhoop', 4:'4" Mini',
    5:'5" Freestyle', 6:'6" Heavy', 7:'7" Mid-LR', 7.5:'7.5" Mid-LR', 8:'8" LR', 10:'10" Long Range'
  };

  function g(id){ return document.getElementById(id); }
  function sv(id,v){ let e=g(id); if(e) e.textContent=v; }
  function sc(el,cls){ el.classList.remove('green','amber','red','blue','ok','warn','bad'); if(cls) el.classList.add(cls); }

  window.liveCalc = function(){
    let size   = parseFloat((g('f_size')||{}).value)   || 5.0;
    let weight = parseFloat((g('f_weight')||{}).value)  || 750;
    let prop   = parseFloat((g('f_prop')||{}).value)    || 5.0;
    let pitch  = parseFloat((g('f_pitch')||{}).value)   || 4.0;
    let cells  = parseInt((g('battery-select')||{}).value) || 4;
    let mah    = parseFloat((g('f_mah')||{}).value)     || 1500;
    let kv     = parseFloat((g('f_kv')||{}).value)      || 0;
    let style  = (g('f_style')||{}).value || 'freestyle';

    let volt   = cells * 3.7;
    let maxRPM = kv > 0 ? kv * cells * 3.85 * 0.80 : 0;
    let tipSpeed = kv > 0 ? (Math.PI * prop * 0.0254 * maxRPM) / 60 : 0;

    /* ── Physics (uses module-level tables + _physInterp) ── */
    let motorCount = 4;
    let totalThrust, cellScale;
    if (kv > 0) {
      let cellEff = 1.0 + (cells - 4) * 0.055;
      let effMax  = Math.max(0.40, 0.55 - (prop - 5.0) * 0.015);
      let maxPwr  = Math.min(_physInterp(prop, _PHYS_MAX_PWR) * (1 + (cells-4)/4.0*0.22), 1000);
      let gPerW   = 4.7 * (0.9 + prop * 0.02) * cellEff;
      totalThrust = gPerW * effMax * maxPwr * motorCount;
    } else {
      cellScale   = cells <= 4 ? (0.55 + cells * 0.1125) : (1.0 + (cells-4) * 0.18);
      totalThrust = _physInterp(prop, _PHYS_THRUST) * cellScale * motorCount;
    }
    let twr = weight > 0 ? Math.min(totalThrust / weight, 12.0) : 0;

    let maxPwrMotor   = Math.min(_physInterp(prop, _PHYS_MAX_PWR) * (1 + (cells-4)/4.0*0.22), 1000);
    let peakW         = maxPwrMotor * motorCount;
    let hoverThrottle = twr > 0 ? Math.sqrt(1/twr) : 0.5;
    let wPerG         = _physInterp(prop, _PHYS_WPG);
    let hoverW        = wPerG * weight;
    let sf            = _PHYS_SF[style] || 1.55;
    let avgW          = hoverW * sf;

    /* Flight time: usable Wh / avgW × 60 */
    let packV    = cells * 3.7;
    let battWh   = (mah / 1000) * packV;
    let usableWh = battWh * 0.85;
    let ftSafe   = avgW > 0.1 ? Math.min(30, Math.max(0, Math.round((usableWh / avgW) * 60 * 10)/10)) : 0;

    let hoverCurrent = packV > 0 ? hoverW / packV : 0;
    let peakCurrentTotal = packV > 0 ? peakW / packV : 0;
    let cBurst = mah > 0 ? Math.min(200, Math.round(peakCurrentTotal / (mah/1000) * 10)/10) : 0;
    let escA = Math.max(20, Math.ceil((peakCurrentTotal / motorCount) * 1.5 / 5) * 5);

    /* ── HUD ── */
    let twrDisp = twr > 0 ? twr.toFixed(2)+':1' : '—';
    let twrColor = twr >= 3.5 ? 'green' : twr >= 2.0 ? 'amber' : twr > 0 ? 'red' : '';
    sv('h_twr', twrDisp);
    let twrEl = g('h_twr'); if(twrEl){ sc(twrEl,''); twrEl.classList.add(twrColor||'blue'); }
    let hbTwr = g('hb_twr');
    if(hbTwr){ hbTwr.style.width = Math.min(100,twr/6*100)+'%'; hbTwr.style.background = twrColor=='green'?'var(--green)':twrColor=='amber'?'var(--amber)':'var(--red)'; }

    let tipDisp = tipSpeed > 0 ? Math.round(tipSpeed)+' m/s' : '— m/s';
    let tipColor = tipSpeed > 290 ? 'red' : tipSpeed > 265 ? 'amber' : tipSpeed > 0 ? 'green' : '';
    sv('h_tip', tipDisp);
    let tipEl = g('h_tip'); if(tipEl){ sc(tipEl,''); if(tipColor) tipEl.classList.add(tipColor); }
    let hbTip = g('hb_tip');
    if(hbTip){ hbTip.style.width = Math.min(100,tipSpeed/350*100)+'%'; hbTip.style.background = tipColor=='green'?'var(--green)':tipColor=='amber'?'var(--amber)':'var(--red)'; }

    let rpmDisp = maxRPM > 0 ? Math.round(maxRPM/1000*10)/10+'k RPM' : '— RPM';
    sv('h_rpm', rpmDisp);
    let hbRpm = g('hb_rpm');
    if(hbRpm){ hbRpm.style.width = Math.min(100,maxRPM/80000*100)+'%'; }

    let ftDisp = ftSafe > 0.1 ? ftSafe.toFixed(1)+' min' : '— min';
    let ftColor = ftSafe > 6 ? 'green' : ftSafe > 3 ? 'amber' : ftSafe > 0 ? 'red' : '';
    sv('h_ft', ftDisp);
    let ftEl = g('h_ft'); if(ftEl){ sc(ftEl,''); if(ftColor) ftEl.classList.add(ftColor); }
    let hbFt = g('hb_ft');
    if(hbFt){ hbFt.style.width = Math.min(100,ftSafe/15*100)+'%'; hbFt.style.background = ftColor=='green'?'var(--green)':ftColor=='amber'?'var(--amber)':'var(--red)'; }

    /* ── DANGER ZONE NEEDLE ── */
    let needle = g('dzNeedle');
    if(needle){
      let pct = tipSpeed > 0 ? Math.min(95, Math.max(3, tipSpeed/350*100)) : 15;
      needle.style.left = pct+'%';
      needle.setAttribute('data-val', tipSpeed > 0 ? Math.round(tipSpeed)+' m/s' : 'N/A');
    }
    let dzStatus = g('dzStatus');
    if(dzStatus && tipSpeed > 0){
      if(tipSpeed > 290){
        dzStatus.innerHTML = '<strong style="color:var(--red);">⛔ DANGER: '+Math.round(tipSpeed)+'m/s — เกิน 290 m/s compressibility loss รุนแรง</strong><br><span style="font-size:10px;color:var(--muted2);">ลด KV หรือเปลี่ยน prop เล็กลง / pitch ต่ำลง</span>';
      } else if(tipSpeed > 265){
        dzStatus.innerHTML = '<strong style="color:var(--amber);">⚠️ WARNING: '+Math.round(tipSpeed)+'m/s — ใกล้ขีดจำกัด (265 m/s)</strong><br><span style="font-size:10px;color:var(--muted2);">efficiency ลดที่ full throttle · balance prop ให้ดี</span>';
      } else {
        dzStatus.innerHTML = '<strong style="color:var(--green);">✅ SAFE: '+Math.round(tipSpeed)+'m/s — ปลอดภัย (&lt;265 m/s)</strong><br><span style="font-size:10px;color:var(--muted2);">Tip speed อยู่ในเกณฑ์ subsonic เต็มที่</span>';
      }
    }

    /* ── DRONE SVG ── */
    let motorColor = tipSpeed > 290 ? 'rgba(255,68,85,0.7)' : tipSpeed > 265 ? 'rgba(255,183,0,0.7)' : 'rgba(0,255,136,0.5)';
    ['dv_m1','dv_m2','dv_m3','dv_m4'].forEach(function(id){
      let el = g(id); if(el) el.setAttribute('stroke', motorColor);
    });
    const classKey = [2.5,3,3.5,4,5,6,7,7.5,8,10].find(function(k){ return Math.abs(size-k) < 0.26; }) || size;
    sv('dv_class', SIZE_CLASSES[classKey] || size+'" Custom');
    sv('dv_volt', volt.toFixed(1)+'V');
    sv('dv_kvv', kv > 0 ? Math.round(maxRPM).toLocaleString()+' RPM (loaded)' : 'กรอก KV');
    sv('dv_wclass', weight<250?'Ultra-Light':weight<500?'Light':weight<800?'Medium':weight<1500?'Heavy':'X-Heavy');
    sv('dv_esc', escA+'A recommended');
    let sizeLbl = g('dv_sizelbl'); if(sizeLbl) sizeLbl.textContent = size+'" · '+(style||'').toUpperCase();

    /* ── PRE-FLIGHT CHECKS ── */
    function setChk(idx, status, val){
      let item = g('chk'+idx); let valEl = g('chk'+idx+'v');
      if(!item) return;
      item.className = 'chk-item ' + status;
      if(valEl){
        valEl.textContent = val;
        valEl.className = 'chk-val ' + (status==='ok'?'green':status==='warn'?'amber':'red');
      }
    }
    if(kv > 0 && tipSpeed > 0) setChk(0, tipSpeed>300?'bad':tipSpeed>250?'warn':'ok', Math.round(tipSpeed)+' m/s');
    else setChk(0, 'ok', 'กรอก KV');
    setChk(1, cBurst>80?'bad':cBurst>50?'warn':'ok', mah>0?Math.round(cBurst)+'C req':'—');
    setChk(2, twr<1.2?'bad':twr<2.0?'warn':'ok', twr>0?twr.toFixed(2)+':1':'—');
    setChk(3, ftSafe<2?'bad':ftSafe<4?'warn':'ok', ftSafe>0?ftSafe.toFixed(1)+' min':'—');
    setChk(4, escA>80?'warn':'ok', escA+'A+');

    /* ── LIVE BUILD SCORE ── */
    let s_twr  = twr > 0 ? Math.min(100, Math.max(0, (twr-0.5)/5*100)) : 0;
    let s_ft   = ftSafe > 0 ? Math.min(100, ftSafe/12*100) : 0;
    let s_tip  = tipSpeed > 0 ? Math.min(100, Math.max(0, (1-(tipSpeed-100)/250)*100)) : 70;
    let s_c    = cBurst > 0 ? Math.min(100, Math.max(0, (1-cBurst/120)*100)) : 70;
    let s_eff  = twr > 3 ? 85 : twr > 2 ? 70 : twr > 0 ? 45 : 50;
    let s_safe = (tipSpeed<265||tipSpeed===0) && twr>1.5 ? 88 : twr>1.2 ? 55 : 30;
    const scores = [s_twr, s_ft, s_tip, s_c, s_eff, s_safe];
    const weights = [0.25,0.20,0.20,0.15,0.10,0.10];
    let total = Math.round(scores.reduce(function(a,s,i){ return a+s*weights[i]; }, 0));
    let grade = total>=92?'S':total>=85?'A+':total>=78?'A':total>=70?'B+':total>=60?'B':'C';
    let gColor = total>=78?'var(--green)':total>=55?'var(--amber)':'var(--red)';

    let sn = g('liveScoreNum'); if(sn){ sn.textContent = total>0?total:'—'; sn.style.color = gColor; }
    let sg = g('liveScoreGrade'); if(sg){ sg.textContent = total>0?grade:'—'; sg.style.color = gColor; }
    let ring = g('liveScoreRing');
    if(ring && total>0){
      let circ = 326.7;
      ring.style.strokeDashoffset = circ - (total/100*circ);
      ring.style.stroke = gColor;
    }
    let scoreColors = scores.map(function(s){ return s>=70?'var(--green)':s>=45?'var(--amber)':'var(--red)'; });
    scores.forEach(function(s,i){
      let bar = g('lsb'+i); let pct = g('lsp'+i);
      if(bar){ bar.style.width = s.toFixed(0)+'%'; bar.style.background = scoreColors[i]; }
      if(pct) pct.textContent = total>0 ? s.toFixed(0)+'%' : '—';
    });
    if(total > 0) setChk(5, total<55?'bad':total<70?'warn':'ok', grade+' ('+total+')');
    else setChk(5, 'ok', '—');
  };

  /* applyPreset — fills form fields */
  let PRESETS_LIVE = {
    '2.5_micro':   {size:2.5,  weight:80,   battery:'3S', prop_size:2.5, pitch:2.0, blades:'2', style:'freestyle', motor_kv:3500,  battery_mAh:300},
    '3_whoop':     {size:3.0,  weight:120,  battery:'3S', prop_size:3.0, pitch:2.0, blades:'2', style:'freestyle', motor_kv:2500,  battery_mAh:450},
    '3.5_cine':    {size:3.5,  weight:350,  battery:'4S', prop_size:3.5, pitch:2.5, blades:'2', style:'longrange', motor_kv:3500,  battery_mAh:850},
    '4_mini':      {size:4.0,  weight:420,  battery:'4S', prop_size:4.0, pitch:3.0, blades:'2', style:'freestyle', motor_kv:2800,  battery_mAh:850},
    '5_4s_freestyle': {size:5.0,weight:720,battery:'4S',prop_size:5.0,pitch:4.0,blades:'3',style:'freestyle',motor_kv:2306,battery_mAh:1500},
    '5_4s_racing':    {size:5.0,weight:650,battery:'4S',prop_size:5.1,pitch:4.5,blades:'3',style:'racing',motor_kv:2550,battery_mAh:1300},
    '5_4s_smooth':    {size:5.0,weight:800,battery:'4S',prop_size:5.0,pitch:3.5,blades:'2',style:'longrange',motor_kv:1950,battery_mAh:1800},
    '5_4s_bangers':   {size:5.0,weight:710,battery:'4S',prop_size:5.1,pitch:4.1,blades:'3',style:'freestyle',motor_kv:2450,battery_mAh:1500},
    '5_5s_freestyle': {size:5.0,weight:730,battery:'5S',prop_size:5.0,pitch:4.0,blades:'3',style:'freestyle',motor_kv:1900,battery_mAh:1300},
    '5_5s_racing':    {size:5.0,weight:660,battery:'5S',prop_size:5.1,pitch:4.6,blades:'3',style:'racing',motor_kv:2000,battery_mAh:1100},
    '5_5s_dji':       {size:5.0,weight:780,battery:'5S',prop_size:5.0,pitch:4.0,blades:'3',style:'freestyle',motor_kv:1750,battery_mAh:1300},
    '5_6s_freestyle': {size:5.0,weight:750,battery:'6S',prop_size:5.0,pitch:4.0,blades:'3',style:'freestyle',motor_kv:1750,battery_mAh:1100},
    '5_6s_racing':    {size:5.0,weight:680,battery:'6S',prop_size:5.1,pitch:4.6,blades:'3',style:'racing',motor_kv:1900,battery_mAh:1000},
    '5_6s_lr':        {size:5.0,weight:800,battery:'6S',prop_size:5.0,pitch:3.8,blades:'2',style:'longrange',motor_kv:1600,battery_mAh:1500},
    '1s_nano':        {size:1.0,weight:22,battery:'1S',prop_size:1.0,pitch:1.0,blades:'4',style:'freestyle',motor_kv:19000,battery_mAh:250},
    '1.5_tiny':       {size:1.5,weight:30,battery:'1S',prop_size:1.5,pitch:1.2,blades:'4',style:'freestyle',motor_kv:12500,battery_mAh:300},
    '2_nano_2s':      {size:2.0,weight:60,battery:'2S',prop_size:2.0,pitch:1.5,blades:'3',style:'freestyle',motor_kv:8000,battery_mAh:350},
    '2.5_micro_2s':   {size:2.5,weight:75,battery:'2S',prop_size:2.5,pitch:2.0,blades:'3',style:'freestyle',motor_kv:6000,battery_mAh:400},
    '2.5_micro_3s':   {size:2.5,weight:80,battery:'3S',prop_size:2.5,pitch:2.0,blades:'2',style:'freestyle',motor_kv:4500,battery_mAh:400},
    '3_whoop_1s':     {size:3.0,weight:85,battery:'1S',prop_size:3.0,pitch:2.0,blades:'4',style:'freestyle',motor_kv:8500,battery_mAh:550},
    '3_whoop_2s':     {size:3.0,weight:90,battery:'2S',prop_size:3.0,pitch:2.0,blades:'2',style:'freestyle',motor_kv:5500,battery_mAh:500},
    '3_whoop_3s':     {size:3.0,weight:120,battery:'3S',prop_size:3.0,pitch:2.0,blades:'2',style:'freestyle',motor_kv:3500,battery_mAh:550},
    '3.5_cine_3s':    {size:3.5,weight:280,battery:'3S',prop_size:3.5,pitch:2.5,blades:'2',style:'longrange',motor_kv:2750,battery_mAh:750},
    '3.5_cine_4s':    {size:3.5,weight:300,battery:'4S',prop_size:3.5,pitch:2.5,blades:'2',style:'longrange',motor_kv:2500,battery_mAh:650},
    '4_mini_3s':      {size:4.0,weight:380,battery:'3S',prop_size:4.0,pitch:3.0,blades:'2',style:'freestyle',motor_kv:2800,battery_mAh:850},
    '4_mini_4s_free': {size:4.0,weight:420,battery:'4S',prop_size:4.0,pitch:3.0,blades:'2',style:'freestyle',motor_kv:2500,battery_mAh:850},
    '4_mini_4s_race': {size:4.0,weight:400,battery:'4S',prop_size:4.0,pitch:3.5,blades:'3',style:'racing',motor_kv:2600,battery_mAh:750},
    '6_4s_heavy':     {size:6.0,weight:900,battery:'4S',prop_size:6.0,pitch:4.0,blades:'3',style:'freestyle',motor_kv:1700,battery_mAh:2200},
    '6_6s_standard':  {size:6.0,weight:850,battery:'6S',prop_size:6.0,pitch:4.0,blades:'3',style:'freestyle',motor_kv:1750,battery_mAh:1300},
    '6_6s_cine':      {size:6.0,weight:950,battery:'6S',prop_size:6.0,pitch:3.8,blades:'2',style:'longrange',motor_kv:1600,battery_mAh:1500},
    '7_4s_midlr':     {size:7.0,weight:1000,battery:'4S',prop_size:7.0,pitch:3.5,blades:'2',style:'longrange',motor_kv:1300,battery_mAh:3000},
    '7_6s_midlr':     {size:7.0,weight:1100,battery:'6S',prop_size:7.0,pitch:3.5,blades:'2',style:'longrange',motor_kv:1200,battery_mAh:2200},
    '7.5_6s_midlr':   {size:7.5,weight:1200,battery:'6S',prop_size:7.5,pitch:3.0,blades:'2',style:'longrange',motor_kv:1100,battery_mAh:2500},
    '7_6s_freestyle': {size:7.0,weight:1050,battery:'6S',prop_size:7.0,pitch:4.0,blades:'3',style:'freestyle',motor_kv:1300,battery_mAh:2000},
    '8_6s_lr':        {size:8.0,weight:1400,battery:'6S',prop_size:8.0,pitch:3.5,blades:'2',style:'longrange',motor_kv:1000,battery_mAh:3000},
    '8_6s_hd':        {size:8.0,weight:1600,battery:'6S',prop_size:8.0,pitch:3.5,blades:'2',style:'longrange',motor_kv:900,battery_mAh:3500},
    '8_7s_ultra':     {size:8.0,weight:1500,battery:'7S',prop_size:8.0,pitch:3.5,blades:'2',style:'longrange',motor_kv:900,battery_mAh:2500},
    '10_6s_lr':       {size:10.0,weight:1800,battery:'6S',prop_size:10.0,pitch:4.5,blades:'2',style:'longrange',motor_kv:800,battery_mAh:4000},
    '10_6s_heavy':    {size:10.0,weight:2200,battery:'6S',prop_size:10.0,pitch:4.5,blades:'2',style:'longrange',motor_kv:700,battery_mAh:5000},
    '10_7s_ultra':    {size:10.0,weight:1900,battery:'7S',prop_size:10.0,pitch:4.5,blades:'2',style:'longrange',motor_kv:750,battery_mAh:3500},
    '12_6s_ultra':    {size:12.0,weight:2500,battery:'6S',prop_size:12.0,pitch:5.0,blades:'2',style:'longrange',motor_kv:600,battery_mAh:6000},
    '5_freestyle':    {size:5.0,weight:720,battery:'4S',prop_size:5.0,pitch:4.0,blades:'3',style:'freestyle',motor_kv:2306,battery_mAh:1500},
    '6_heavy5':       {size:6.0,weight:850,battery:'6S',prop_size:6.0,pitch:4.0,blades:'3',style:'freestyle',motor_kv:1750,battery_mAh:1800},
    '7_midlr':        {size:7.0,weight:1100,battery:'6S',prop_size:7.0,pitch:3.5,blades:'2',style:'longrange',motor_kv:1200,battery_mAh:3000},
    '10_lr':          {size:10.0,weight:1800,battery:'6S',prop_size:10.0,pitch:4.5,blades:'2',style:'longrange',motor_kv:800,battery_mAh:4000}
  };

  window.onPresetSelect = function(key){
    if(!key) return;
    applyPreset(key, null);
  };

  window.togglePresetGroup = function(idx, btn){
    document.querySelectorAll('.preset-cat-btn').forEach(function(b){ b.style.borderColor='rgba(255,255,255,0.1)'; b.style.color='var(--muted2)'; });
    btn.style.borderColor='rgba(0,255,136,0.4)'; btn.style.color='var(--green)';
  };

  window.applyPreset = function(key, chip){
    document.querySelectorAll('.pmini').forEach(function(c){ c.classList.remove('active'); });
    if(chip) chip.classList.add('active');
    let p = PRESETS_LIVE[key]; if(!p) return;
    let ps = document.getElementById('preset-select');
    if(ps) ps.value = key;
    function sf(sel,v){ let el=document.querySelector(sel); if(el && v!==undefined && v!==null) el.value=v; }
    sf('input[name="size"]', p.size);
    sf('input[name="weight"]', p.weight);
    sf('select[name="battery"]', p.battery);
    sf('input[name="prop_size"]', p.prop_size);
    sf('input[name="pitch"]', p.pitch);
    sf('select[name="blades"]', p.blades);
    sf('select[name="style"]', p.style);
    if(p.motor_kv){ sf('input[name="motor_kv"]', p.motor_kv); }
    if(p.battery_mAh){ sf('input[name="battery_mAh"]', p.battery_mAh); }
    liveCalc();
    showToast('✅ ' + key + ' โหลดแล้ว');
  };

  /* ── Debounce: prevent liveCalc firing every keystroke (causes input lag) ── */
  function _debounce(fn, ms = 500) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => {
      requestAnimationFrame(() => fn.apply(this, args));
    }, ms);
  };
}

const _debouncedCalc = _debounce(liveCalc, 500);

  let inputs = document.querySelectorAll('input[type=number], select');
  inputs.forEach(function(el){
    if(el.tagName === 'SELECT'){
      el.addEventListener('change', liveCalc);      // select: immediate
    } else {
      el.addEventListener('input',  _debouncedCalc); // typing: debounced 120ms
      el.addEventListener('change', liveCalc);       // blur/enter: immediate
    }
  });

  /* initial run */
  liveCalc();
})();

/* ─── UI HELPERS ──────────────────────────────────────────────── */
function toggleConcept(){
  document.getElementById('conceptBox').classList.toggle('open');
}

/* ── Result 3-Tab navigation ── */
function switchRTab(btn, paneId) {
  document.querySelectorAll('.rtab-btn').forEach(function(b){ b.classList.remove('active'); b.setAttribute('aria-selected','false'); });
  document.querySelectorAll('.rtab-pane').forEach(function(p){ p.classList.remove('active'); });
  btn.classList.add('active');
  btn.setAttribute('aria-selected','true');
  let pane = document.getElementById(paneId);
  if(pane){ pane.classList.add('active'); }
  if(paneId==='rt-deep'){ setTimeout(function(){ if(window.renderRadar) renderRadar(); }, 50); }
}

function switchTab(btn, paneId) {
  let card = btn.closest('.tpanel');
  card.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.remove('active'); });
  card.querySelectorAll('.tab-pane').forEach(function(p){ p.classList.remove('active'); });
  btn.classList.add('active');
  let pane = document.getElementById(paneId);
  if(pane){ pane.classList.add('active'); if(paneId==='t-radar') renderRadar(); }
}

function sauceTab(idx, btn) {
  const panels = [document.getElementById('sauce-panel-0'), document.getElementById('sauce-panel-1'), document.getElementById('sauce-panel-2')];
  panels.forEach(function(p){ if(p) p.style.display='none'; });
  if(panels[idx]) panels[idx].style.display='block';
  let tabs = document.querySelectorAll('.sauce-tab');
  tabs.forEach(function(t){ t.classList.remove('active'); });
  if(btn) btn.classList.add('active');
}

function copyEl(id) {
  let el = document.getElementById(id);
  if(!el) return;
  let text = el.innerText || el.textContent;
  navigator.clipboard.writeText(text)
    .then(function(){ showToast('✓ คัดลอกแล้ว!'); })
    .catch(function(){
      let ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta);
      ta.select(); document.execCommand('copy');
      document.body.removeChild(ta);
      showToast('✓ คัดลอกแล้ว!');
    });
}

function showToast(msg) {
  let t = document.getElementById('toast');
  if(!t) return;
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(function(){ t.classList.remove('show'); }, 3000);
}

function copyAdvJSON(){
  let el = document.getElementById('advJSON');
  if(el){ navigator.clipboard.writeText(el.textContent).then(function(){ showToast('✓ JSON copied'); }); }
}

/* ─── SAUCE CLI SYNTAX HIGHLIGHTER ───────────────────────────── */
/* Called inline from HTML inside {% if analysis.secret_sauce %} */
window.highlightSauceCLI = function() {
  let box = document.getElementById('sauceCLIBox');
  if(!box) return;
  let html = box.innerHTML
    .replace(/(&lt;|<)!--(.*?)--(&gt;|>)/g, '<span style="color:#6a9955;font-style:italic;"><!--$2--></span>')
    .replace(/(^|\n)(# ══.*?)(\n|$)/g, '$1<span style="color:#ff8c00;font-weight:700;">$2</span>$3')
    .replace(/(^|\n)(# ───.*?)(\n|$)/g, '$1<span style="color:#ffb700;font-weight:600;">$2</span>$3')
    .replace(/(^|\n)(# .*?)(\n|$)/g, '$1<span style="color:#6a9955;">$2</span>$3')
    .replace(/(^|\n)(set )(\S+)/g, '$1$2<span style="color:#00ff88;">$3</span>');
  box.innerHTML = html;
};

/* ─── DRAWER ──────────────────────────────────────────────────── */
(function(){
  let btn = document.getElementById('hamburgerBtn');
  let drawer = document.getElementById('drawer');
  let overlay = document.getElementById('overlay');
  let closeBtn = document.getElementById('closeDrawer');
  function openDrawer(){
    btn && btn.setAttribute('aria-expanded','true');
    drawer && drawer.classList.add('open');
    overlay && overlay.classList.add('open');
    document.addEventListener('keydown', onEsc);
  }
  function closeDrawer(){
    btn && btn.setAttribute('aria-expanded','false');
    drawer && drawer.classList.remove('open');
    overlay && overlay.classList.remove('open');
    document.removeEventListener('keydown', onEsc);
    btn && btn.focus();
  }
  function onEsc(e){ if(e.key==='Escape') closeDrawer(); }
  btn && btn.addEventListener('click', function(){ btn.getAttribute('aria-expanded')==='true' ? closeDrawer() : openDrawer(); });
  overlay && overlay.addEventListener('click', closeDrawer);
  closeBtn && closeBtn.addEventListener('click', closeDrawer);
})();

/* ─── PRESET SELECT (dropdown sync) ─────────────────────────── */
/* NOTE: presetMap removed — PRESETS_LIVE above (43 entries) already handles
   the #preset-select change event via window.onPresetSelect / applyPreset().
   Having two listeners caused: (a) liveCalc called twice per change,
   (b) data inconsistency — e.g. 5_freestyle weight was 750 here vs 720 in PRESETS_LIVE. */

/* ═══════════════════════════════════════════════════════════
   PRESET CLI PROFILES
═══════════════════════════════════════════════════════════ */
let PRESETS = {
  beginner: {
    label:'BEGINNER', color:'var(--green)',
    title:'Beginner — ปลอดภัย เหมาะสำหรับมือใหม่',
    desc:'ลด P 10% · D 15% · Throttle cap 80% · Filter นุ่มกว่าปกติ — บินนิ่ง ควบคุมง่าย ไม่แดง',
    stats:[
      {v:'×0.90 P',c:'blue',l:'P GAIN'},
      {v:'×0.85 D',c:'blue',l:'D GAIN'},
      {v:'80%',c:'amber',l:'THROTTLE'},
      {v:'Soft',c:'green',l:'FILTER'},
    ],
    tips:[
      {i:'🟢',t:'<b>Throttle limit 80%</b> — ป้องกันพลิกคว่ำกะทันหัน เหมาะฝึก hover และ line ตรง'},
      {i:'🔵',t:'<b>Filter นุ่มขึ้น 15%</b> — ลด noise รับโทษด้าน response เล็กน้อย ดีสำหรับ motor ใหม่'},
      {i:'🟡',t:'<b>iterm_relax = RP</b> — ป้องกัน I-term windup ตอน flip/roll ลด bounce-back'},
      {i:'⚡',t:'<b>RPM Filter ON</b> — เปิด bidirectional dshot ต้องการ ESC รองรับ DSHOT600'},
      {i:'⚠️',t:'ทดสอบ hover ก่อนทำ trick — ถ้า oscillate ให้ลด P เพิ่ม 5% อีกรอบ'},
    ],
    cli: function(){
      return [
        '# OBIXConfig Doctor v5 — BEGINNER SAFE PRESET',
        '# สำหรับมือใหม่ · Throttle 80% · Filter นุ่ม · RPM Filter ON',
        '',
        '# ── PID ──',
        'set p_roll            = '+_r(_pRoll*0.90),
        'set i_roll            = '+_r(_iRoll*0.95),
        'set d_roll            = '+_r(_dRoll*0.85),
        'set f_roll            = 0',
        'set p_pitch           = '+_r(_pPitch*0.90),
        'set i_pitch           = '+_r(_iPitch*0.95),
        'set d_pitch           = '+_r(_dPitch*0.85),
        'set f_pitch           = 0',
        'set p_yaw             = '+_r(_pYaw*0.88),
        'set i_yaw             = '+_r(_iYaw),
        '',
        '# ── Filter (soft) ──',
        'set gyro_lpf1_static_hz    = '+_r(_gLpf1*0.80),
        'set gyro_lpf2_static_hz    = '+_r(_gLpf1*1.6),
        'set dterm_lpf1_static_hz   = '+_r(_dLpf1*0.80),
        'set dterm_lpf2_static_hz   = '+_r(_dLpf1*1.4),
        'set dyn_notch_count        = '+Math.max(1,_notch),
        'set dyn_notch_min_hz       = 80',
        'set dyn_notch_max_hz       = 350',
        '',
        '# ── RPM Filter ──',
        'set motor_pwm_protocol     = DSHOT600',
        'set dshot_bidir            = ON',
        'set motor_poles            = 14',
        'set rpm_filter_harmonics   = 3',
        'set rpm_filter_min_hz      = 100',
        '',
        '# ── Throttle & Safety ──',
        'set throttle_limit_percent = 80',
        'set throttle_limit_type    = SCALE',
        'set tpa_rate               = 15',
        'set tpa_breakpoint         = 1500',
        '',
        '# ── Iterm & Feedforward ──',
        'set iterm_relax            = RP',
        'set iterm_relax_type       = SETPOINT',
        'set anti_gravity_gain      = '+Math.max(2,_ag-2),
        'set feedforward_averaging  = 4_POINT',
        'set feedforward_smooth_factor = 35',
        '',
        'save'
      ].join('\n');
    }
  },
  freestyle: {
    label:'FREESTYLE', color:'var(--blue)',
    title:'Freestyle — ค่าวิเคราะห์ full, response ดี, RPM filter',
    desc:'ค่าจากการวิเคราะห์เต็มรูปแบบ — iterm_relax, FF averaging, TPA คำนวณตาม TWR',
    stats:[
      {v:'Full',c:'blue',l:'PID'},
      {v:'DSHOT600',c:'green',l:'PROTOCOL'},
      {v:'BiDir',c:'green',l:'RPM FILTER'},
      {v:'2_POINT',c:'blue',l:'FF AVG'},
    ],
    tips:[
      {i:'🎯',t:'<b>PID ครบชุด</b> — ใช้ค่าจากการวิเคราะห์ size/weight/battery เต็มรูปแบบ'},
      {i:'⚡',t:'<b>DSHOT600 + BiDir</b> — RPM Filter แม่นยำ ลด noise ได้สูงสุด'},
      {i:'🔵',t:'<b>TPA (Throttle PID Attenuation)</b> — ลด P/D ที่ throttle สูง ป้องกัน oscillate ตอน punch'},
      {i:'🟢',t:'<b>FF 2_POINT averaging</b> — ลด noise จาก RC stick feedforward ดีกับ RC ทุกแบรนด์'},
      {i:'⚠️',t:'ปรับ TPA breakpoint ตาม hover throttle ของคุณ ถ้า hover ~40% → breakpoint 1450'},
    ],
    cli: function(){
      return [
        '# OBIXConfig Doctor v5 — FREESTYLE FULL TUNE',
        '# ค่าวิเคราะห์จาก size/weight/battery/style',
        '',
        '# ── PID ──',
        'set p_roll            = '+_pRoll,
        'set i_roll            = '+_iRoll,
        'set d_roll            = '+_dRoll,
        'set f_roll            = 80',
        'set p_pitch           = '+_pPitch,
        'set i_pitch           = '+_iPitch,
        'set d_pitch           = '+_dPitch,
        'set f_pitch           = 85',
        'set p_yaw             = '+_pYaw,
        'set i_yaw             = '+_iYaw,
        '',
        '# ── Filter (balanced) ──',
        'set gyro_lpf1_static_hz    = '+_gLpf1,
        'set gyro_lpf2_static_hz    = '+_r(_gLpf1*2),
        'set dterm_lpf1_static_hz   = '+_dLpf1,
        'set dterm_lpf2_static_hz   = '+_r(_dLpf1*1.6),
        'set dyn_notch_count        = '+_notch,
        'set dyn_notch_min_hz       = 100',
        'set dyn_notch_max_hz       = 500',
        '',
        '# ── RPM Filter ──',
        'set motor_pwm_protocol     = DSHOT600',
        'set dshot_bidir            = ON',
        'set motor_poles            = 14',
        'set rpm_filter_harmonics   = 3',
        'set rpm_filter_min_hz      = 100',
        '',
        '# ── TPA ──',
        'set tpa_rate               = 12',
        'set tpa_breakpoint         = 1450',
        '',
        '# ── Iterm & FF ──',
        'set iterm_relax            = RP',
        'set iterm_relax_type       = SETPOINT',
        'set anti_gravity_gain      = '+_ag,
        'set feedforward_averaging  = 2_POINT',
        'set feedforward_smooth_factor = 25',
        '',
        'save'
      ].join('\n');
    }
  },
  racing: {
    label:'RACING', color:'var(--red)',
    title:'Racing — P/D สูง, Response ไว, Filter เร็ว',
    desc:'P สูง 15% · D สูง 12% · Filter เร็วขึ้น — สำหรับ racing gate/track ที่ต้องการ response ทันที',
    stats:[
      {v:'+15% P',c:'red',l:'P GAIN'},
      {v:'+12% D',c:'red',l:'D GAIN'},
      {v:'Fast',c:'amber',l:'FILTER'},
      {v:'Race',c:'red',l:'MODE'},
    ],
    tips:[
      {i:'🏁',t:'<b>P สูงขึ้น 15%</b> — ตอบสนองทันทีตาม stick input เหมาะ gate racing ที่ต้องการ precision'},
      {i:'🔴',t:'<b>Filter เร็วขึ้น 20%</b> — latency ต่ำลง แต่ motor อาจร้อนขึ้น ตรวจ motor temp หลังบิน'},
      {i:'⚠️',t:'<b>ห้ามใช้กับมือใหม่</b> — oscillate ง่ายถ้า motor เก่าหรือ prop ไม่สมดุล'},
      {i:'🟡',t:'<b>TPA 20%</b> — ลด P ที่ throttle สูง ป้องกัน punch oscillation'},
      {i:'💡',t:'แนะนำ balance prop ทุกครั้งก่อนบิน racing tune'},
    ],
    cli: function(){
      return [
        '# OBIXConfig Doctor v5 — RACING TUNE',
        '# High P/D · Fast filter · Low latency',
        '',
        '# ── PID ──',
        'set p_roll            = '+_r(_pRoll*1.15),
        'set i_roll            = '+_r(_iRoll*0.90),
        'set d_roll            = '+_r(_dRoll*1.12),
        'set f_roll            = 100',
        'set p_pitch           = '+_r(_pPitch*1.15),
        'set i_pitch           = '+_r(_iPitch*0.90),
        'set d_pitch           = '+_r(_dPitch*1.12),
        'set f_pitch           = 105',
        'set p_yaw             = '+_r(_pYaw*1.10),
        'set i_yaw             = '+_r(_iYaw*0.88),
        '',
        '# ── Filter (fast) ──',
        'set gyro_lpf1_static_hz    = '+_r(_gLpf1*1.25),
        'set gyro_lpf2_static_hz    = '+_r(_gLpf1*2.5),
        'set dterm_lpf1_static_hz   = '+_r(_dLpf1*1.20),
        'set dterm_lpf2_static_hz   = '+_r(_dLpf1*2.0),
        'set dyn_notch_count        = 2',
        'set dyn_notch_min_hz       = 150',
        'set dyn_notch_max_hz       = 700',
        '',
        '# ── RPM Filter ──',
        'set motor_pwm_protocol     = DSHOT600',
        'set dshot_bidir            = ON',
        'set motor_poles            = 14',
        'set rpm_filter_harmonics   = 3',
        'set rpm_filter_min_hz      = 150',
        '',
        '# ── TPA ──',
        'set tpa_rate               = 20',
        'set tpa_breakpoint         = 1400',
        '',
        'set feedforward_averaging  = 2_POINT',
        'set iterm_relax            = RP',
        '',
        'save'
      ].join('\n');
    }
  },
  longrange: {
    label:'LONG RANGE', color:'#a050ff',
    title:'Long Range — นิ่ง, ประหยัดแบต, Wind rejection สูง',
    desc:'P/D ต่ำ 20% · I สูง 15% · Filter นุ่ม — บินตรง wind rejection ดี ประหยัด current',
    stats:[
      {v:'–20% P/D',c:'blue',l:'PID'},
      {v:'+15% I',c:'green',l:'I GAIN'},
      {v:'Smooth',c:'green',l:'FILTER'},
      {v:'LR',c:'blue',l:'MODE'},
    ],
    tips:[
      {i:'🗺️',t:'<b>I สูงขึ้น</b> — ต้านลมได้ดี โดรนบินตรงแม้มีลมแรง เหมาะ 7"-10" frame'},
      {i:'🔋',t:'<b>Filter นุ่มลง</b> — ลด motor noise ช่วยประหยัด current เพิ่ม flight time'},
      {i:'🟢',t:'<b>P/D ต่ำลง</b> — บินนิ่ง ไม่ jitter ลด motor temp สำหรับ long range'},
      {i:'💡',t:'Anti-gravity gain สูงขึ้น — ช่วย I term ตอบสนองเร็วเมื่อเปลี่ยน throttle'},
      {i:'⚠️',t:'ไม่เหมาะกับ freestyle trick — response ช้าเจตนา เพื่อ LR efficiency'},
    ],
    cli: function(){
      return [
        '# OBIXConfig Doctor v5 — LONG RANGE TUNE',
        '# Low P/D · High I · Soft filter · Wind rejection',
        '',
        '# ── PID ──',
        'set p_roll            = '+_r(_pRoll*0.80),
        'set i_roll            = '+_r(_iRoll*1.15),
        'set d_roll            = '+_r(_dRoll*0.80),
        'set f_roll            = 40',
        'set p_pitch           = '+_r(_pPitch*0.80),
        'set i_pitch           = '+_r(_iPitch*1.15),
        'set d_pitch           = '+_r(_dPitch*0.80),
        'set f_pitch           = 45',
        'set p_yaw             = '+_r(_pYaw*0.85),
        'set i_yaw             = '+_r(_iYaw*1.10),
        '',
        '# ── Filter (smooth) ──',
        'set gyro_lpf1_static_hz    = '+_r(_gLpf1*0.75),
        'set gyro_lpf2_static_hz    = '+_r(_gLpf1*1.4),
        'set dterm_lpf1_static_hz   = '+_r(_dLpf1*0.75),
        'set dterm_lpf2_static_hz   = '+_r(_dLpf1*1.3),
        'set dyn_notch_count        = '+Math.max(2,_notch),
        'set dyn_notch_min_hz       = 70',
        'set dyn_notch_max_hz       = 400',
        '',
        '# ── RPM Filter ──',
        'set motor_pwm_protocol     = DSHOT600',
        'set dshot_bidir            = ON',
        'set motor_poles            = 14',
        'set rpm_filter_harmonics   = 3',
        'set rpm_filter_min_hz      = 80',
        '',
        '# ── LR specific ──',
        'set anti_gravity_gain      = '+_r(_ag*1.4),
        'set iterm_relax            = RPY',
        'set tpa_rate               = 8',
        'set tpa_breakpoint         = 1600',
        '',
        'save'
      ].join('\n');
    }
  },
  cinematic: {
    label:'CINEMATIC', color:'var(--amber)',
    title:'Cinematic — เรียบนิ่งที่สุด สำหรับ film/photo',
    desc:'P/D ต่ำมาก 35% · Filter นุ่มมาก · Expo สูง — ภาพนิ่ง ไม่มี jitter สำหรับถ่ายทำ',
    stats:[
      {v:'–35% P',c:'amber',l:'P GAIN'},
      {v:'Max',c:'amber',l:'FILTER'},
      {v:'Slow',c:'green',l:'RESPONSE'},
      {v:'Film',c:'amber',l:'MODE'},
    ],
    tips:[
      {i:'🎬',t:'<b>PID ต่ำมาก</b> — โดรนเคลื่อนไหวเนียน ไม่มี oscillation ที่กล้องจะจับได้'},
      {i:'🟡',t:'<b>Filter นุ่มสุดขีด</b> — latency สูงขึ้นแต่ไม่ใช่ปัญหาสำหรับ cinematic ที่ไม่ต้องการ agility'},
      {i:'⚠️',t:'ไม่เหมาะบินใกล้สิ่งกีดขวาง — response ช้า ต้องการพื้นที่โล่ง'},
      {i:'🎯',t:'แนะนำ RC rates ต่ำ + expo สูง (0.7+) เพื่อ smooth input ที่สุด'},
      {i:'💡',t:'ใส่ND filter บนกล้อง + ใช้ shutter rule 180° เพื่อภาพ cinematic ที่สมบูรณ์'},
    ],
    cli: function(){
      return [
        '# OBIXConfig Doctor v5 — CINEMATIC TUNE',
        '# Ultra smooth · Low PID · Max filter · Film production',
        '',
        '# ── PID ──',
        'set p_roll            = '+_r(_pRoll*0.65),
        'set i_roll            = '+_r(_iRoll*1.10),
        'set d_roll            = '+_r(_dRoll*0.65),
        'set f_roll            = 20',
        'set p_pitch           = '+_r(_pPitch*0.65),
        'set i_pitch           = '+_r(_iPitch*1.10),
        'set d_pitch           = '+_r(_dPitch*0.65),
        'set f_pitch           = 25',
        'set p_yaw             = '+_r(_pYaw*0.70),
        'set i_yaw             = '+_r(_iYaw*1.10),
        '',
        '# ── Filter (max smooth) ──',
        'set gyro_lpf1_static_hz    = '+_r(_gLpf1*0.60),
        'set gyro_lpf2_static_hz    = '+_r(_gLpf1*1.2),
        'set dterm_lpf1_static_hz   = '+_r(_dLpf1*0.60),
        'set dterm_lpf2_static_hz   = '+_r(_dLpf1*1.1),
        'set dyn_notch_count        = '+Math.max(3,_notch),
        'set dyn_notch_min_hz       = 60',
        'set dyn_notch_max_hz       = 350',
        '',
        '# ── RPM Filter ──',
        'set motor_pwm_protocol     = DSHOT600',
        'set dshot_bidir            = ON',
        'set rpm_filter_harmonics   = 3',
        'set rpm_filter_min_hz      = 70',
        '',
        '# ── Cinematic settings ──',
        'set anti_gravity_gain      = '+_r(_ag*1.5),
        'set iterm_relax            = RPY',
        'set tpa_rate               = 5',
        'set tpa_breakpoint         = 1700',
        '',
        'save'
      ].join('\n');
    }
  }
};

let PRESET_INFO = {
  beginner:   {badge:'🟢 SAFE',      bStyle:'background:rgba(0,255,136,0.1);border-color:rgba(0,255,136,0.4);color:var(--green)'},
  freestyle:  {badge:'🔵 BALANCED',  bStyle:'background:rgba(0,170,255,0.1);border-color:rgba(0,170,255,0.4);color:var(--blue)'},
  racing:     {badge:'🔴 AGGRESSIVE',bStyle:'background:rgba(255,68,85,0.1);border-color:rgba(255,68,85,0.4);color:var(--red)'},
  longrange:  {badge:'🟣 EFFICIENT', bStyle:'background:rgba(160,80,255,0.1);border-color:rgba(160,80,255,0.4);color:#a050ff'},
  cinematic:  {badge:'🟡 SMOOTH',    bStyle:'background:rgba(255,183,0,0.1);border-color:rgba(255,183,0,0.4);color:var(--amber)'},
};

function selectPreset(type, btn) {
  document.querySelectorAll('.ptab').forEach(function(t){ t.className='ptab'; });
  btn.className = 'ptab active';
  let p = PRESETS[type]; let info = PRESET_INFO[type]; if(!p) return;
  document.getElementById('picBadge').textContent = info.badge;
  document.getElementById('picBadge').setAttribute('style', info.bStyle+';display:inline-block;font-family:var(--font-d);font-size:8px;letter-spacing:.1em;padding:3px 10px;border-radius:4px;margin-bottom:8px;border:1px solid;');
  document.getElementById('picTitle').textContent = p.title;
  document.getElementById('picDesc').textContent  = p.desc;
  let statsHtml = p.stats.map(function(s){ return '<div class="pstat"><span class="pstat-val '+s.c+'">'+s.v+'</span><span class="pstat-lbl">'+s.l+'</span></div>'; }).join('');
  document.getElementById('picStats').innerHTML = statsHtml;
  let tipsHtml = p.tips.map(function(t){ return '<div class="ptip"><span class="ptip-icon">'+t.i+'</span><span>'+t.t+'</span></div>'; }).join('');
  document.getElementById('picTips').innerHTML = tipsHtml;
  document.getElementById('cliOutput').textContent = p.cli();
}
function showPreset(type){ let btn = document.querySelector('.ptab[data-preset="'+type+'"]'); if(btn) selectPreset(type,btn); }

/* ─── DONATE AMOUNT BUTTONS ──────────────────────────────────── */
document.querySelectorAll('.amt-btn').forEach(function(btn){
  btn.addEventListener('click', function(){
    document.querySelectorAll('.amt-btn').forEach(function(b){ b.classList.remove('selected'); });
    this.classList.add('selected');
  });
});

/* ─── CHARTS (analysis only — data from window.OBIX) ─────────── */
(function(){
  let tEl = document.getElementById('thrustChart');
  if(tEl && typeof Chart !== 'undefined'){
    let _hoverW = OBIX.charts.hoverW;
    let _aggrW  = OBIX.charts.aggrW;
    let _peakW  = OBIX.charts.peakW;
    if(_hoverW || _aggrW || _peakW){
      new Chart(tEl, {
        type: 'bar',
        data: {
          labels: ['Hover', 'Aggressive', 'Peak'],
          datasets: [{
            label: 'Power (W)',
            data: [_hoverW, _aggrW, _peakW],
            backgroundColor: ['rgba(0,255,136,0.35)', 'rgba(255,183,0,0.35)', 'rgba(255,68,85,0.35)'],
            borderColor: ['#00ff88','#ffb700','#ff4455'],
            borderWidth: 1, borderRadius: 6
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display:false }, tooltip:{ callbacks:{ label:function(c){ return c.raw+'W'; }}}},
          scales: {
            y: { beginAtZero:true, grid:{ color:'rgba(255,255,255,0.04)' }, ticks:{ color:'#3d5470', font:{family:'JetBrains Mono'}, callback:function(v){ return v+'W'; }}},
            x: { grid:{ display:false }, ticks:{ color:'#3d5470', font:{family:'JetBrains Mono'} }}
          }
        }
      });
    }
  }

  /* Prop noise radar chart — data from window.OBIX.propRadar */
  if(OBIX.propRadar && typeof Chart !== 'undefined'){
    let nEl = document.getElementById('noiseChart');
    if(nEl){
      let pr = OBIX.propRadar;
      new Chart(nEl, {
        type: 'radar',
        data: {
          labels: ['Motor Load', 'Noise', 'Grip', 'Efficiency', 'Speed'],
          datasets: [{
            label: 'Prop Profile',
            data: [pr.motorLoad, pr.noise, pr.grip, pr.efficiency, pr.pitchSpeed],
            backgroundColor: 'rgba(0,170,255,0.12)',
            borderColor: '#00aaff',
            pointBackgroundColor: '#00aaff',
            borderWidth: 2
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend:{ display:false } },
          scales: { r: { beginAtZero:true, max:8, grid:{ color:'rgba(255,255,255,0.05)' }, ticks:{ display:false }, pointLabels:{ color:'#3d5470', font:{ size:10, family:'JetBrains Mono' } }}}
        }
      });
    }
  }

  /* Counter animation */
  document.querySelectorAll('.qs-stat-val.counter').forEach(function(el){
    let target = parseFloat(el.textContent);
    if(isNaN(target)) return;
    let startTime = null; let dur = 800;
    function step(ts){
      if(!startTime) startTime = ts;
      let prog = Math.min((ts-startTime)/dur, 1);
      let eased = 1 - Math.pow(1-prog, 3);
      el.textContent = (target * eased).toFixed(target%1===0?0:2);
      if(prog<1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
})();

/* ─── RADAR CHART ─────────────────────────────────────────────── */
let radarChartInst = null;
function renderRadar(){
  let d = document.getElementById('radarData');
  if(!d || radarChartInst) return;
  const vals = [
    parseInt(d.dataset.power||0),
    parseInt(d.dataset.flight||0),
    parseInt(d.dataset.noise||0),
    parseInt(d.dataset.tip||0),
    parseInt(d.dataset.motor||0),
    parseInt(d.dataset.eff||0),
  ];
  let ctx2 = document.getElementById('radarChart');
  if(!ctx2 || typeof Chart === 'undefined') return;
  radarChartInst = new Chart(ctx2, {
    type: 'radar',
    data: {
      labels: ['Power','Flight Time','Low Noise','Tip Safety','Motor Health','Efficiency'],
      datasets: [{
        data: vals,
        backgroundColor: 'rgba(0,255,136,.10)',
        borderColor: '#00ff88', borderWidth: 2,
        pointBackgroundColor: ['#00ff88','#58a6ff','#a78bfa','#f1b65a','#f87171','#2dd4bf'],
        pointRadius: 4, pointHoverRadius: 6,
      }]
    },
    options: {
      scales: { r: { min:0, max:100, ticks:{ stepSize:25, display:false }, grid:{ color:'rgba(255,255,255,.07)' }, pointLabels:{ color:'rgba(200,215,225,.7)', font:{ size:10, family:"'Sarabun', sans-serif" }}, angleLines:{ color:'rgba(255,255,255,.07)' }}},
      plugins: { legend:{ display:false }, tooltip:{ callbacks:{ label:function(c){ return c.raw+'%'; }}}},
      animation: { duration:900 }
    }
  });
}

/* ─── SCORE RING ANIMATE ON LOAD ─────────────────────────────── */
(function(){
  let ring = document.getElementById('score-ring-circle');
  if(!ring) return;
  let final = parseFloat(ring.getAttribute('stroke-dashoffset'));
  let circ = 339.3;
  ring.setAttribute('stroke-dashoffset', circ);
  setTimeout(function(){
    ring.style.transition = 'stroke-dashoffset 1.2s cubic-bezier(.2,.8,.3,1)';
    ring.setAttribute('stroke-dashoffset', final);
  }, 350);
})();

/* ─── PARTICLE BURST ON ANALYZE ──────────────────────────────── */
(function(){
  let btn = document.getElementById('btnAnalyze');
  if(!btn || btn.dataset.particlesBound === '1') return;

  btn.dataset.particlesBound = '1';

  btn.addEventListener('click', function(e){
    if(btn.disabled) return; // skip burst after locked
    const colors = ['#00ff88','#00aaff','#00e5ff','#00cc6a','#ffffff'];

    for(let i=0; i<22; i++){
      let spark = document.createElement('div');
      let color = colors[Math.floor(Math.random()*colors.length)];
      let size = 3 + Math.random()*4;

      spark.style.cssText = [
        'position:fixed',
        'left:'+e.clientX+'px',
        'top:'+e.clientY+'px',
        'width:'+size+'px',
        'height:'+size+'px',
        'border-radius:50%',
        'background:'+color,
        'pointer-events:none',
        'z-index:9999',
        'box-shadow:0 0 '+(size*2)+'px '+color
      ].join(';');

      document.body.appendChild(spark);

      let angle = (i/22)*Math.PI*2 + Math.random()*0.3;
      let dist = 50 + Math.random()*80;
      let tx = Math.cos(angle)*dist;
      let ty = Math.sin(angle)*dist;

      spark.animate(
        [
          {transform:'translate(0,0) scale(1)', opacity:1},
          {transform:'translate('+tx+'px,'+ty+'px) scale(0)', opacity:0}
        ],
        {duration:600, easing:'cubic-bezier(0,.9,.57,1)'}
      ).onfinish = function(){
        this.effect.target.remove();
      };
    }
  });
})();

/* ─── INIT PRESET VIEW ───────────────────────────────────────── */
(function(){
  let initBtn = document.querySelector('.ptab[data-preset="beginner"]');
  if(initBtn) selectPreset('beginner', initBtn);
})();

/* ─── THEME TOGGLE ───────────────────────────────────────────── */
function toggleTheme(){
  let b = document.body;
  let isDark = !b.classList.contains('light');
  b.classList.toggle('light', isDark);
  localStorage.setItem('obix-theme', isDark ? 'light' : 'dark');
}
(function(){
  let t = localStorage.getItem('obix-theme');
  if(t === 'light') document.body.classList.add('light');
})();

/* ─── HUD VALUE FLASH on change ──────────────────────────────── */
(function(){
  let prev = {};
  const flash = function(id, newVal){
    if(prev[id] === newVal) return;
    prev[id] = newVal;
    let el = document.getElementById(id);
    if(!el) return;
    el.style.transition = 'none';
    el.style.transform = 'scale(1.12)';
    el.style.filter = 'brightness(1.4)';
    setTimeout(function(){
      el.style.transition = 'transform .3s ease, filter .3s ease';
      el.style.transform = '';
      el.style.filter = '';
    }, 120);
  };
  /* FIX: Use guard flag to prevent re-wrapping on bfcache restore or double-load.
     Named function expression prevents chained recursion if script runs twice. */
  if (!window.__liveCalcFlashWrapped && typeof window.liveCalc === 'function') {
    window.__liveCalcFlashWrapped = true;
    const _coreCalc = window.liveCalc;
    let _flashTimer;
    window.liveCalc = function obixLiveCalcWithFlash() {
      _coreCalc();
      clearTimeout(_flashTimer);
      _flashTimer = setTimeout(function() {
        ['h_twr', 'h_tip', 'h_rpm', 'h_ft'].forEach(function(id) {
          let el = document.getElementById(id);
          if (el) flash(id, el.textContent);
        });
      }, 250);
    };
  }
})();

/* ─── PANEL SCROLL REVEAL ────────────────────────────────────── */
(function(){
  if(!('IntersectionObserver' in window)) return;
  const obs = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting){
        e.target.style.opacity = '1';
        e.target.style.transform = 'none';
        obs.unobserve(e.target);
      }
    });
  }, {threshold:0.08});
  document.querySelectorAll('.tpanel, .inst-panel').forEach(function(el){
    obs.observe(el);
  });
})();

/* ══ TOOL DOCK FILTER ════════════════════════════════════════════ */
function dockFilter(btn, cat) {
  document.querySelectorAll('.dock-tab').forEach(function(t){
    t.classList.remove('active');
    t.setAttribute('aria-pressed', 'false');
  });
  btn.classList.add('active');
  btn.setAttribute('aria-pressed', 'true');
  document.querySelectorAll('.dtool[data-cat]').forEach(function(el){
    el.classList.toggle('hidden', cat !== 'all' && el.getAttribute('data-cat') !== cat);
  });
}

/* ═══ v5.2 Battery Pills · Style Cards · CLI Snippet ════════════ */
window.setBatt = function(s, btn) {
  let sel = document.getElementById('battery-select');
  if (sel) { sel.value = s; }
  document.querySelectorAll('.batt-pill').forEach(function(b) { b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  liveCalc();
};
window.syncBattPills = function(val) {
  let map = {'3S':'bp-3s','4S':'bp-4s','5S':'bp-5s','6S':'bp-6s','7S':'bp-7s','8S':'bp-8s'};
  document.querySelectorAll('.batt-pill').forEach(function(b) {
    b.classList.remove('active');
    if (map[val] && b.classList.contains(map[val])) b.classList.add('active');
  });
};

window.setStyle = function(style, card) {
  let sel = document.getElementById('f_style');
  if (sel) { sel.value = style; }
  document.querySelectorAll('.style-card').forEach(function(c) { c.classList.remove('active'); });
  if (card) card.classList.add('active');
  liveCalc();
};
window.syncStyleCards = function(val) {
  document.querySelectorAll('.style-card').forEach(function(c) {
    c.classList.remove('active');
    if ((val==='freestyle' && c.classList.contains('s-free')) ||
        (val==='racing'    && c.classList.contains('s-race')) ||
        (val==='longrange' && c.classList.contains('s-lr')))
      c.classList.add('active');
  });
};

window.copyCliSnippet = function(el) {
  let txt = el.textContent || el.innerText || '';
  if (navigator.clipboard) {
    navigator.clipboard.writeText(txt.trim()).then(function() {
      let orig = el.style.background;
      el.style.background = 'rgba(0,255,136,0.25)';
      setTimeout(function() { el.style.background = orig; }, 500);
      showToast('✅ CLI copied — paste in Betaflight!');
    });
  }
};

/* ─── INIT pills + cards on page load ─────────────────────────── */
(function() {
  let battSel = document.getElementById('battery-select');
  if (battSel) syncBattPills(battSel.value || '4S');
  let styleSel = document.getElementById('f_style');
  if (styleSel) syncStyleCards(styleSel.value || 'freestyle');
})();

/* ═══════════════════════════════════════════════════════════════════
   SAFE FORM SUBMIT GUARD  v5.2
   ─────────────────────────────────────────────────────────────────
   Prevents double-submit and loops on the main analyze form.
   Uses AbortController for any future AJAX refactor.
   Guard flag (window.__analyzeBound) ensures this runs only once
   even if index-app.js is accidentally loaded twice.
═══════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  if (window.__analyzeBound) return;
  window.__analyzeBound = true;

  const form = document.getElementById('analyzeForm');
  const btn  = document.getElementById('btnAnalyze');

  if (!form || !btn) return;

  let locked = false;
  const original = btn.innerHTML;

  form.addEventListener('submit', function (e) {
    if (locked) {
      e.preventDefault();
      e.stopImmediatePropagation();
      return false;
    }

    locked = true;

    btn.disabled = true;
    btn.setAttribute('aria-disabled', 'true');
    btn.style.pointerEvents = 'none';
    btn.style.opacity = '0.6';
    btn.innerHTML = '⏳ กำลังวิเคราะห์…';
  }, true);

  window.addEventListener('pageshow', function (ev) {
    if (ev.persisted) {
      locked = false;
      btn.disabled = false;
      btn.removeAttribute('aria-disabled');
      btn.style.pointerEvents = '';
      btn.style.opacity = '';
      btn.innerHTML = original;
    }
  });
})();


/* ═══════════════════════════════════════════════════════════
   CONFIG WIZARD — Size Chip Selector
═══════════════════════════════════════════════════════════ */
window.setSizeChip = function(chip) {
  // Deactivate all chips
  document.querySelectorAll('.sz-chip').forEach(c => c.classList.remove('active'));
  chip.classList.add('active');

  var sz    = parseFloat(chip.dataset.sz  || 5.0);
  var w     = parseFloat(chip.dataset.w   || 720);
  var prop  = parseFloat(chip.dataset.prop  || sz);
  var pitch = parseFloat(chip.dataset.pitch || 4.0);
  var kv    = parseInt(chip.dataset.kv || 0);

  // Update hidden form fields
  var setVal = function(id, v) { var el = document.getElementById(id); if(el) el.value = v; };
  setVal('f_size',   sz);
  setVal('f_prop',   prop);
  setVal('f_pitch',  pitch);
  setVal('f_weight', w);

  // Update visible inputs
  var setVis = function(id, v) { var el = document.getElementById(id); if(el) el.value = v; };
  setVis('f_weight_vis',  w);
  setVis('f_prop_vis',    prop);
  setVis('f_pitch_vis',   pitch);
  if(kv) setVis('f_kv', kv);

  // Update prop display
  var disp = document.getElementById('sz_prop_disp');
  if(disp) disp.textContent = prop + '"×' + pitch + 'p';

  // Trigger live calc
  if(window.liveCalc) liveCalc();
};

/* Sync size chip on page load if form has pre-filled value */
(function(){
  var sizeEl = document.getElementById('f_size');
  if(!sizeEl || !sizeEl.value) return;
  var sz = parseFloat(sizeEl.value);
  var best = null, bestDiff = 99;
  document.querySelectorAll('.sz-chip').forEach(function(c){
    var d = Math.abs(parseFloat(c.dataset.sz) - sz);
    if(d < bestDiff){ bestDiff = d; best = c; }
  });
  if(best && bestDiff < 0.5){
    document.querySelectorAll('.sz-chip').forEach(c => c.classList.remove('active'));
    best.classList.add('active');
  }
  // Update prop display
  var propEl = document.getElementById('f_prop');
  var pitchEl = document.getElementById('f_pitch');
  var disp = document.getElementById('sz_prop_disp');
  if(disp && propEl && pitchEl) disp.textContent = propEl.value + '"×' + pitchEl.value + 'p';
})();

/* ═══════════════════════════════════════════════════════════
   RESULTS — Expandable Explanations
═══════════════════════════════════════════════════════════ */
window.toggleStatExp = function(id) {
  var el = document.getElementById(id);
  if(!el) return;
  var isOpen = el.style.display === 'block';
  // Close all stat-exp
  document.querySelectorAll('.stat-exp').forEach(function(e){ e.style.display='none'; });
  if(!isOpen) el.style.display = 'block';
};

window.togglePidTip = function(id) {
  var el = document.getElementById(id);
  if(!el) return;
  var isOpen = el.style.display === 'block';
  document.querySelectorAll('.pid-tip-box').forEach(function(e){ e.style.display='none'; });
  if(!isOpen) el.style.display = 'block';
};

window.toggleFltTip = function(id) {
  var el = document.getElementById(id);
  if(!el) return;
  var isOpen = el.style.display === 'block';
  document.querySelectorAll('.flt-tip-box').forEach(function(e){ e.style.display='none'; });
  if(!isOpen) el.style.display = 'block';
};

/* ═══════════════════════════════════════════════════════════
   mAh hint updater
═══════════════════════════════════════════════════════════ */
(function(){
  function updateMahHint(){
    var mahEl  = document.getElementById('f_mah');
    var battEl = document.getElementById('battery-select');
    var hint   = document.getElementById('mah_hint');
    if(!mahEl || !battEl || !hint) return;

    var mah   = parseInt(mahEl.value) || 1500;
    var cells = parseInt((battEl.value||'4S').replace(/[Ss]/,'')) || 4;
    var wt    = parseFloat((document.getElementById('f_weight')||{}).value) || 720;

    // Rough flight time estimate: usable Wh / avg_power * 60
    var packV    = cells * 3.7;
    var wh       = (mah / 1000) * packV * 0.85;
    var wPerG    = cells <= 2 ? 0.38 : cells <= 3 ? 0.32 : cells <= 4 ? 0.20 : cells <= 6 ? 0.16 : 0.14;
    var hoverW   = wPerG * wt;
    var avgW     = hoverW * 1.55;
    var ft       = avgW > 1 ? Math.round((wh / avgW) * 60 * 10) / 10 : 0;
    hint.textContent = ft > 0 ? '≈ ' + ft + ' min' : '';
  }
  var mahEl  = document.getElementById('f_mah');
  var battEl = document.getElementById('battery-select');
  if(mahEl)  mahEl.addEventListener('input', updateMahHint);
  if(battEl) battEl.addEventListener('change', updateMahHint);
  updateMahHint();
})();

/* Prop/pitch sync from advanced inputs */
(function(){
  var propVis  = document.getElementById('f_prop_vis');
  var pitchVis = document.getElementById('f_pitch_vis');
  function syncPropDisp(){
    var disp = document.getElementById('sz_prop_disp');
    if(!disp) return;
    var p  = (propVis  && propVis.value)  ? propVis.value  : (document.getElementById('f_prop')||{}).value  || '5.0';
    var pi = (pitchVis && pitchVis.value) ? pitchVis.value : (document.getElementById('f_pitch')||{}).value || '4.0';
    disp.textContent = p + '"×' + pi + 'p';
  }
  if(propVis)  propVis.addEventListener('input', syncPropDisp);
  if(pitchVis) pitchVis.addEventListener('input', syncPropDisp);
})();
