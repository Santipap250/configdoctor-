// static/js/osd.js
(() => {
  // basic model
  const model = {
    width: 640,
    height: 360,
    items: []
  };

  // helpers
  const $ = sel => document.querySelector(sel);
  const $$ = sel => Array.from(document.querySelectorAll(sel));
  const canvas = $('#canvas');
  const itemCount = $('#itemCount');
  const canvasSizeLabel = $('#canvasSizeLabel');

  // init
  function init(){
    // initial size
    setCanvasSize(model.width, model.height);
    bindPalette();
    bindControls();
    renderAll();
  }

  function bindPalette(){
    document.querySelectorAll('.pal-item').forEach(btn => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.type;
        addItem(type);
      });
    });
  }

  function bindControls(){
    $('#btnResizeCanvas').addEventListener('click', () => {
      const w = parseInt($('#canvasW').value, 10) || 640;
      const h = parseInt($('#canvasH').value, 10) || 360;
      setCanvasSize(w, h);
      renderAll();
    });

    $('#btnClear').addEventListener('click', () => {
      if (!confirm('เคลียร์ชิ้นส่วนทั้งหมด?')) return;
      model.items = [];
      renderAll();
    });

    $('#btnExport').addEventListener('click', exportDownload);
    $('#btnExport2').addEventListener('click', exportDownload);
    $('#btnSaveServer').addEventListener('click', saveToServer);
    $('#btnCenter').addEventListener('click', centerAll);

    // apply prop changes
    $('#btnApplyProp').addEventListener('click', applyPropEdit);
    $('#btnDeleteProp').addEventListener('click', deleteSelected);

    // click on canvas to deselect
    canvas.addEventListener('pointerdown', (e) => {
      // if click empty space, deselect
      if (e.target === canvas) {
        selectItem(null);
      }
    });
  }

  function setCanvasSize(w,h){
    model.width = w; model.height = h;
    canvas.style.width = '100%';
    canvas.style.height = (h * (Math.min(900, canvas.clientWidth) / w)) + 'px';
    canvas.dataset.nativeW = w;
    canvas.dataset.nativeH = h;
    canvasSizeLabel.textContent = `${w}×${h}`;
  }

  // create item
  function addItem(type){
    const id = 'it' + Date.now();
    const item = {
      id, type, label: (type === 'text' ? 'TEXT' : type.toUpperCase()),
      x: Math.floor(model.width/2 - 40), y: Math.floor(model.height/2 - 10),
      size: 14, color: '#ffffff'
    };
    model.items.push(item);
    renderAll();
    selectItem(id);
  }

  // render whole canvas
  function renderAll(){
    // clear
    canvas.innerHTML = '';
    // place items
    model.items.forEach(it => {
      const el = document.createElement('div');
      el.className = 'osd-item';
      el.dataset.id = it.id;
      el.style.left = it.x + 'px';
      el.style.top = it.y + 'px';
      el.style.fontSize = it.size + 'px';
      el.style.color = it.color;
      el.innerText = it.label;
      if (selectedId === it.id) el.classList.add('selected');
      // pointer events
      el.addEventListener('pointerdown', onPointerDownItem);
      canvas.appendChild(el);
    });
    itemCount.textContent = `${model.items.length} items`;

    // scale canvas wrapper to fit native ratio
    updateScaleTransforms();
  }

  // scale helpers for display coordinates
  function updateScaleTransforms(){
    const nativeW = model.width;
    const nativeH = model.height;
    // compute scale to element width
    const rect = canvas.getBoundingClientRect();
    const scale = rect.width / nativeW;
    canvas.style.height = (nativeH * scale) + 'px';
    // set transform-origin for children positions: we'll convert absolute px to scaled px
    // reposition children to scaled coordinates
    canvas.querySelectorAll('.osd-item').forEach(el => {
      const id = el.dataset.id;
      const it = model.items.find(x=>x.id===id);
      if (!it) return;
      el.style.left = (it.x * scale) + 'px';
      el.style.top = (it.y * scale) + 'px';
      el.style.fontSize = (it.size * scale) + 'px';
    });
  }

  // selection
  let selectedId = null;
  function selectItem(id){
    selectedId = id;
    if (!id) {
      $('#propEditor').hidden = true;
      $('#noSelection').style.display = 'block';
    } else {
      $('#propEditor').hidden = false;
      $('#noSelection').style.display = 'none';
      const it = model.items.find(x=>x.id===id);
      if (!it) return;
      $('#propType').innerText = it.type;
      $('#propLabel').value = it.label;
      $('#propX').value = it.x;
      $('#propY').value = it.y;
      $('#propSize').value = it.size;
      $('#propColor').value = it.color;
    }
    renderAll();
  }

  function applyPropEdit(){
    if (!selectedId) return;
    const it = model.items.find(x=>x.id===selectedId);
    if (!it) return;
    it.label = $('#propLabel').value;
    it.x = parseFloat($('#propX').value) || it.x;
    it.y = parseFloat($('#propY').value) || it.y;
    it.size = parseFloat($('#propSize').value) || it.size;
    it.color = $('#propColor').value || it.color;
    renderAll();
  }

  function deleteSelected(){
    if (!selectedId) return;
    model.items = model.items.filter(x=>x.id!==selectedId);
    selectItem(null);
  }

  // pointer drag
  let dragState = null;
  function onPointerDownItem(e){
    e.stopPropagation();
    const el = e.currentTarget;
    const id = el.dataset.id;
    selectItem(id);
    el.setPointerCapture(e.pointerId);
    const start = {px: e.clientX, py: e.clientY, time: Date.now()};
    const it = model.items.find(x=>x.id===id);
    const scale = canvas.getBoundingClientRect().width / model.width;
    dragState = {id, start, ox: it.x, oy: it.y, scale};
    el.addEventListener('pointermove', onPointerMoveItem);
    el.addEventListener('pointerup', onPointerUpItem, {once:true});
  }

  function onPointerMoveItem(e){
    if (!dragState) return;
    const el = e.currentTarget;
    const ds = dragState;
    const dx = (e.clientX - ds.start.px) / ds.scale;
    const dy = (e.clientY - ds.start.py) / ds.scale;
    let nx = Math.round((ds.ox + dx));
    let ny = Math.round((ds.oy + dy));
    // snap grid
    if ($('#snapToGrid').checked){
      const g = parseInt($('#gridSize').value,10) || 8;
      nx = Math.round(nx / g) * g;
      ny = Math.round(ny / g) * g;
    }
    const it = model.items.find(x=>x.id===ds.id);
    if (!it) return;
    it.x = Math.max(0, Math.min(model.width - 4, nx));
    it.y = Math.max(0, Math.min(model.height - 4, ny));
    renderAll();
  }

  function onPointerUpItem(e){
    const el = e.currentTarget;
    el.removeEventListener('pointermove', onPointerMoveItem);
    dragState = null;
  }

  function centerAll(){
    model.items.forEach(it => {
      it.x = Math.round((model.width - (it.size*4)) / 2);
      it.y = Math.round((model.height - it.size) / 2);
    });
    renderAll();
  }

  // export: build payload
  function buildPayload(){
    return {
      width: model.width,
      height: model.height,
      items: model.items.map(it => ({
        type: it.type,
        label: it.label,
        x: Math.round(it.x),
        y: Math.round(it.y),
        size: Math.round(it.size),
        color: it.color
      }))
    };
  }

  // download helper
  function downloadText(filename, text){
    const a = document.createElement('a');
    const blob = new Blob([text], {type: 'text/plain;charset=utf-8'});
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  // generate text
  function genText(payload){
    return JSON.stringify(payload, null, 2);
  }

  // export: download local
  function exportDownload(){
    const fmt = $('#exportFormat').value;
    const payload = buildPayload();
    if (fmt === 'json'){
      downloadText('osd.json', genText(payload));
    } else if (fmt === 'cli'){
      // pseudo CLI generation
      let txt = '# OBIX OSD -> CLI (pseudo)\n';
      payload.items.forEach((it, i) => {
        txt += `// ${i+1} ${it.type} ${it.label} @${it.x},${it.y} size=${it.size}\n`;
        txt += `osd_add ${it.type} ${it.x} ${it.y} ${it.label} ${it.size}\n`;
      });
      downloadText('osd_cli.txt', txt);
    } else {
      downloadText('osd.txt', genText(payload));
    }
  }

  // save to server endpoint /osd/export?format=txt&save=1
  async function saveToServer(){
    const payload = buildPayload();
    const fmt = $('#exportFormat').value || 'txt';
    const q = new URLSearchParams({format: fmt, save: '1'});
    try {
      const res = await fetch('/osd/export?' + q.toString(), {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const j = await res.json();
      if (j && j.ok){
        alert('Save OK → ' + j.download_url);
      } else {
        alert('Save failed: ' + (j && j.error || res.status));
      }
    } catch (err){
      alert('Save error: ' + err);
    }
  }

  // init on DOM ready
  window.addEventListener('DOMContentLoaded', init);
  window.addEventListener('resize', () => {
    // re-compute scaling when window resize
    updateScaleTransforms();
  });

})();