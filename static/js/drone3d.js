/**
 * drone3d.js — OBIXConfig Doctor · Real-Time 3D FPV Drone Viewer
 * Three.js r128 · Procedural model · Orbit controls · Neon HUD
 * Author: OBIXConfig Lab · v5.3
 */

(function () {
  'use strict';

  /* ── Configuration ────────────────────────────────────────── */
  const CFG = {
    autoRotateSpeed:   0.004,   // rad/frame idle
    dampingFactor:     0.08,
    minDistance:       2.2,
    maxDistance:       9.0,
    fov:               52,
    motorIdleRPM:      12000,
    motorMaxRPM:       45000,
    propSpinSpeed:     0.22,    // idle prop spin
    telemetryInterval: 120,     // ms between fake telemetry updates
  };

  /* ── Color Themes ─────────────────────────────────────────── */
  const THEMES = {
    cyan: {
      frame:   0x0a1a2e,
      frameE:  0x001a33,
      arm:     0x0d1f30,
      motor:   0x111a24,
      motorE:  0x00e5ff,
      prop:    0x00e5ff,
      propE:   0x00e5ff,
      light1:  0x00e5ff,
      light2:  0x0088ff,
      light3:  0x00ffcc,
      cssVar:  '#00e5ff',
    },
    green: {
      frame:   0x061a0f,
      frameE:  0x001a08,
      arm:     0x0a1e10,
      motor:   0x0d1a10,
      motorE:  0x00ff9d,
      prop:    0x00ff9d,
      propE:   0x00ff9d,
      light1:  0x00ff9d,
      light2:  0x00cc66,
      light3:  0x00ffcc,
      cssVar:  '#00ff9d',
    },
    gold: {
      frame:   0x1a1200,
      frameE:  0x1a0e00,
      arm:     0x1e1500,
      motor:   0x1a1200,
      motorE:  0xffcc00,
      prop:    0xffaa00,
      propE:   0xffcc00,
      light1:  0xffcc00,
      light2:  0xff8800,
      light3:  0xffee66,
      cssVar:  '#ffcc00',
    },
    purple: {
      frame:   0x130a20,
      frameE:  0x0d0520,
      arm:     0x160d28,
      motor:   0x14091e,
      motorE:  0xb060ff,
      prop:    0xaa44ff,
      propE:   0xcc77ff,
      light1:  0xb060ff,
      light2:  0x7722ff,
      light3:  0xff44cc,
      cssVar:  '#b060ff',
    },
    red: {
      frame:   0x200608,
      frameE:  0x200206,
      arm:     0x240a0c,
      motor:   0x1e0608,
      motorE:  0xff2244,
      prop:    0xff3355,
      propE:   0xff4466,
      light1:  0xff2244,
      light2:  0xff6600,
      light3:  0xff0066,
      cssVar:  '#ff3355',
    },
  };

  let currentTheme = 'cyan';

  /* ── State ────────────────────────────────────────────────── */
  let renderer, scene, camera, drone, propellers = [];
  let isUserInteracting = false;
  let autoRotateEnabled = true;
  let lastInteractionTime = 0;
  let frameId;
  let spherical     = { theta: 0.4, phi: 1.2, radius: 5.5 };
  let sphericalTarget = { theta: 0.4, phi: 1.2, radius: 5.5 };
  let pointer       = { x: 0, y: 0, button: -1 };
  let lights        = {};
  let glowMeshes    = [];
  let materials     = {};   // keyed by category
  let telemetryTimer;
  let initialized   = false;
  let canvasWrap;
  let resizeObserver;

  /* ── DOM references ───────────────────────────────────────── */
  const $ = id => document.getElementById(id);
  const el = {
    wrap:      () => document.querySelector('.d3-canvas-wrap'),
    loading:   () => document.querySelector('.d3-loading'),
    motorFill: i  => document.querySelector(`.d3-motor-fill[data-m="${i}"]`),
    motorRpm:  i  => document.querySelector(`.d3-motor-rpm[data-m="${i}"]`),
    roll:      ()  => $('d3Roll'),
    pitch:     ()  => $('d3Pitch'),
    yaw:       ()  => $('d3Yaw'),
    voltage:   ()  => $('d3Voltage'),
    throttle:  ()  => $('d3Throttle'),
    rssi:      ()  => $('d3Rssi'),
    temp:      ()  => $('d3Temp'),
  };

  /* ── Helpers ──────────────────────────────────────────────── */
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function deg(r) { return (r * 180 / Math.PI).toFixed(1); }

  function sphericalToCartesian(s) {
    const sinPhi = Math.sin(s.phi);
    return {
      x: s.radius * sinPhi * Math.sin(s.theta),
      y: s.radius * Math.cos(s.phi),
      z: s.radius * sinPhi * Math.cos(s.theta),
    };
  }

  /* ══════════════════════════════════════════════════════════
     THREE.JS SCENE SETUP
     ══════════════════════════════════════════════════════════ */
  function initScene(canvas) {
    const W = canvasWrap.clientWidth;
    const H = canvasWrap.clientHeight;

    /* Renderer */
    renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W, H, false);
    renderer.setClearColor(0x010810, 1);
    renderer.shadowMap.enabled = false;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;

    /* Scene */
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x010810, 0.045);

    /* Camera */
    camera = new THREE.PerspectiveCamera(CFG.fov, W / H, 0.1, 80);
    const cp = sphericalToCartesian(spherical);
    camera.position.set(cp.x, cp.y, cp.z);
    camera.lookAt(0, 0, 0);

    /* Grid helper - subtle */
    const grid = new THREE.GridHelper(12, 16, 0x001a33, 0x001a33);
    grid.position.y = -1.4;
    scene.add(grid);

    /* Ambient */
    const ambientLight = new THREE.AmbientLight(0x020d1a, 1.0);
    scene.add(ambientLight);

    /* Directional key light */
    const dirLight = new THREE.DirectionalLight(0x4488cc, 0.6);
    dirLight.position.set(3, 6, 4);
    scene.add(dirLight);

    /* Neon point lights (at motor positions) */
    const T = THEMES[currentTheme];
    lights.motor = [];
    const mPos = [[1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1]];
    mPos.forEach((p, i) => {
      const colors = [T.light1, T.light2, T.light3, T.light1];
      const pl = new THREE.PointLight(colors[i % colors.length], 1.8, 3.5);
      pl.position.set(p[0] * 1.05, p[1] + 0.1, p[2] * 1.05);
      scene.add(pl);
      lights.motor.push(pl);
    });

    /* Center top fill */
    lights.top = new THREE.PointLight(T.light2, 0.8, 6);
    lights.top.position.set(0, 2, 0);
    scene.add(lights.top);

    /* Bottom rim */
    lights.bot = new THREE.PointLight(T.light3, 0.4, 5);
    lights.bot.position.set(0, -1.8, 0);
    scene.add(lights.bot);

    /* Build drone */
    buildDrone();
    scene.add(drone);

    /* Ground reflection plane */
    const reflGeo = new THREE.PlaneGeometry(10, 10);
    const reflMat = new THREE.MeshStandardMaterial({
      color: 0x000d1a,
      metalness: 0.9,
      roughness: 0.6,
      transparent: true,
      opacity: 0.5,
    });
    const refl = new THREE.Mesh(reflGeo, reflMat);
    refl.rotation.x = -Math.PI / 2;
    refl.position.y = -1.4;
    scene.add(refl);

    /* Shadow blob under drone */
    const blobGeo = new THREE.CircleGeometry(1.0, 32);
    const blobMat = new THREE.MeshBasicMaterial({
      color: 0x000000,
      transparent: true,
      opacity: 0.45,
    });
    const blob = new THREE.Mesh(blobGeo, blobMat);
    blob.rotation.x = -Math.PI / 2;
    blob.position.y = -1.38;
    scene.add(blob);

    /* Starfield */
    buildStarfield();
  }

  /* ── Drone model ─────────────────────────────────────────── */
  function buildDrone() {
    const T = THEMES[currentTheme];
    drone = new THREE.Group();
    materials = {};

    /* ─ Materials ─ */
    const frameMat = new THREE.MeshStandardMaterial({
      color: T.frame,
      emissive: T.frameE,
      emissiveIntensity: 0.6,
      metalness: 0.85,
      roughness: 0.25,
    });
    const armMat = new THREE.MeshStandardMaterial({
      color: T.arm,
      emissive: new THREE.Color(T.motorE).multiplyScalar(0.06),
      emissiveIntensity: 1,
      metalness: 0.9,
      roughness: 0.2,
    });
    const motorMat = new THREE.MeshStandardMaterial({
      color: T.motor,
      emissive: T.motorE,
      emissiveIntensity: 0.9,
      metalness: 0.95,
      roughness: 0.15,
    });
    const propMat = new THREE.MeshStandardMaterial({
      color: T.prop,
      emissive: T.propE,
      emissiveIntensity: 0.7,
      metalness: 0.3,
      roughness: 0.4,
      transparent: true,
      opacity: 0.88,
    });
    const glowMat = new THREE.MeshBasicMaterial({
      color: T.motorE,
      transparent: true,
      opacity: 0.12,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const stackMat = new THREE.MeshStandardMaterial({
      color: 0x0a1520,
      emissive: T.motorE,
      emissiveIntensity: 0.1,
      metalness: 0.7,
      roughness: 0.3,
    });
    const camMat = new THREE.MeshStandardMaterial({
      color: 0x050e18,
      emissive: 0x001122,
      emissiveIntensity: 1,
      metalness: 0.9,
      roughness: 0.2,
    });
    const ledMat = new THREE.MeshBasicMaterial({
      color: T.motorE,
      transparent: true,
      opacity: 0.95,
    });

    materials.frame = frameMat;
    materials.arm   = armMat;
    materials.motor = motorMat;
    materials.prop  = propMat;
    materials.glow  = glowMat;
    materials.led   = ledMat;

    /* ─ Center frame (top plate) ─ */
    const topPlateGeo = new THREE.BoxGeometry(0.7, 0.06, 0.7);
    const topPlate = new THREE.Mesh(topPlateGeo, frameMat);
    topPlate.position.y = 0.08;
    drone.add(topPlate);

    /* Bottom plate */
    const botPlateGeo = new THREE.BoxGeometry(0.65, 0.05, 0.65);
    const botPlate = new THREE.Mesh(botPlateGeo, frameMat);
    botPlate.position.y = -0.08;
    drone.add(botPlate);

    /* FC/ESC stack */
    const stackGeo = new THREE.BoxGeometry(0.36, 0.28, 0.36);
    const stack = new THREE.Mesh(stackGeo, stackMat);
    stack.position.y = 0.04;
    drone.add(stack);

    /* Stack PCB detail lines (emissive strips) */
    const stripGeo = new THREE.BoxGeometry(0.38, 0.015, 0.015);
    const stripMat = new THREE.MeshBasicMaterial({ color: T.motorE, transparent: true, opacity: 0.7 });
    [-0.06, 0, 0.06].forEach(z => {
      const s = new THREE.Mesh(stripGeo, stripMat);
      s.position.set(0, 0.19, z);
      drone.add(s);
    });

    /* Capacitor bump */
    const capGeo = new THREE.CylinderGeometry(0.045, 0.045, 0.12, 8);
    const capMat = new THREE.MeshStandardMaterial({ color: 0x102030, metalness: 0.8, roughness: 0.3 });
    const cap = new THREE.Mesh(capGeo, capMat);
    cap.position.set(0.16, 0.12, 0.08);
    drone.add(cap);

    /* FPV Camera */
    const camBodyGeo = new THREE.BoxGeometry(0.14, 0.16, 0.1);
    const camBody = new THREE.Mesh(camBodyGeo, camMat);
    camBody.position.set(0, 0.1, 0.42);
    camBody.rotation.x = THREE.MathUtils.degToRad(30);
    drone.add(camBody);

    /* Camera lens */
    const lensGeo = new THREE.CylinderGeometry(0.045, 0.05, 0.06, 12);
    const lensMat = new THREE.MeshStandardMaterial({
      color: 0x001020,
      emissive: 0x002244,
      emissiveIntensity: 2,
      metalness: 1,
      roughness: 0.05,
    });
    const lens = new THREE.Mesh(lensGeo, lensMat);
    lens.rotation.x = Math.PI / 2;
    lens.position.set(0, 0.1, 0.48);
    drone.add(lens);

    /* Camera mount */
    const cmountGeo = new THREE.BoxGeometry(0.18, 0.04, 0.04);
    const cmount = new THREE.Mesh(cmountGeo, frameMat);
    cmount.position.set(0, 0.02, 0.36);
    drone.add(cmount);

    /* ─ Arms (X-quad configuration) ─ */
    const armDirs = [
      { x:  1, z:  1 },
      { x: -1, z:  1 },
      { x:  1, z: -1 },
      { x: -1, z: -1 },
    ];

    propellers = [];
    glowMeshes = [];

    armDirs.forEach((dir, i) => {
      const angle = Math.atan2(dir.x, dir.z);
      const armLen = 1.0;

      /* Arm tube */
      const armGeo = new THREE.BoxGeometry(0.07, 0.045, armLen);
      const arm = new THREE.Mesh(armGeo, armMat);
      arm.position.set(dir.x * armLen * 0.42, 0, dir.z * armLen * 0.42);
      arm.rotation.y = angle;
      drone.add(arm);

      /* Motor can */
      const mPos = { x: dir.x * armLen * 0.88, y: 0.04, z: dir.z * armLen * 0.88 };
      const motorCanGeo = new THREE.CylinderGeometry(0.1, 0.095, 0.1, 12);
      const motorCan = new THREE.Mesh(motorCanGeo, motorMat);
      motorCan.position.set(mPos.x, mPos.y, mPos.z);
      drone.add(motorCan);

      /* Motor base ring */
      const ringGeo = new THREE.TorusGeometry(0.1, 0.012, 8, 24);
      const ring = new THREE.Mesh(ringGeo, motorMat);
      ring.position.set(mPos.x, mPos.y - 0.052, mPos.z);
      drone.add(ring);

      /* LED dot on motor */
      const ledGeo = new THREE.SphereGeometry(0.022, 6, 6);
      const led = new THREE.Mesh(ledGeo, ledMat);
      led.position.set(mPos.x, mPos.y + 0.06, mPos.z);
      drone.add(led);

      /* Propeller group */
      const propGroup = new THREE.Group();
      propGroup.position.set(mPos.x, mPos.y + 0.07, mPos.z);

      /* 2 blades per prop */
      for (let b = 0; b < 2; b++) {
        const bladeGeo = new THREE.BoxGeometry(0.54, 0.012, 0.065);
        // taper: scale X ends
        const blade = new THREE.Mesh(bladeGeo, propMat.clone());
        blade.rotation.y = (b * Math.PI);
        blade.rotation.z = THREE.MathUtils.degToRad(3); // slight pitch
        propGroup.add(blade);
      }

      /* Hub disc */
      const hubGeo = new THREE.CylinderGeometry(0.045, 0.045, 0.02, 10);
      const hub = new THREE.Mesh(hubGeo, motorMat);
      propGroup.add(hub);

      /* Blade tip glow discs */
      const tipGeo = new THREE.CircleGeometry(0.55, 16);
      const tip = new THREE.Mesh(tipGeo, materials.glow);
      tip.position.y = 0.006;
      propGroup.add(tip);

      drone.add(propGroup);
      propellers.push({ group: propGroup, dir: i % 2 === 0 ? 1 : -1, speed: CFG.propSpinSpeed });
      glowMeshes.push(tip);

      /* Motor glow halo */
      const haloGeo = new THREE.CircleGeometry(0.22, 16);
      const haloMat = new THREE.MeshBasicMaterial({
        color: T.motorE,
        transparent: true,
        opacity: 0.09,
        side: THREE.DoubleSide,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      const halo = new THREE.Mesh(haloGeo, haloMat);
      halo.rotation.x = -Math.PI / 2;
      halo.position.set(mPos.x, mPos.y + 0.08, mPos.z);
      drone.add(halo);
      glowMeshes.push(halo);
    });

    /* ─ VTX Antenna ─ */
    const antGeo = new THREE.CylinderGeometry(0.012, 0.012, 0.5, 6);
    const antMat = new THREE.MeshStandardMaterial({ color: 0x1a2030, metalness: 0.7, roughness: 0.4 });
    const ant = new THREE.Mesh(antGeo, antMat);
    ant.position.set(0.15, 0.48, -0.28);
    ant.rotation.z = THREE.MathUtils.degToRad(15);
    drone.add(ant);

    /* Antenna tip */
    const tipGeo = new THREE.SphereGeometry(0.022, 6, 6);
    const tipMat = new THREE.MeshBasicMaterial({ color: T.motorE, transparent: true, opacity: 0.9 });
    const antTip = new THREE.Mesh(tipGeo, tipMat);
    antTip.position.set(0.19, 0.74, -0.32);
    drone.add(antTip);

    /* ─ Body LED strips (under frame) ─ */
    [[-0.24, 0], [0.24, 0], [0, -0.24], [0, 0.24]].forEach(([x, z]) => {
      const lGeo = new THREE.BoxGeometry(0.28, 0.01, 0.01);
      const lMat = new THREE.MeshBasicMaterial({ color: T.motorE, transparent: true, opacity: 0.8 });
      const l = new THREE.Mesh(lGeo, lMat);
      l.position.set(x, -0.115, z);
      drone.add(l);
    });

    /* ─ Landing pads / standoffs ─ */
    [[0.26, 0.26], [-0.26, 0.26], [0.26, -0.26], [-0.26, -0.26]].forEach(([x, z]) => {
      const stGeo = new THREE.CylinderGeometry(0.022, 0.022, 0.2, 6);
      const stMat = new THREE.MeshStandardMaterial({ color: 0x0d1a24, metalness: 0.8, roughness: 0.3 });
      const st = new THREE.Mesh(stGeo, stMat);
      st.position.set(x, -0.21, z);
      drone.add(st);
    });

    drone.position.y = 0.25;
  }

  /* ── Starfield ───────────────────────────────────────────── */
  function buildStarfield() {
    const count = 420;
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 22 + Math.random() * 20;
      const theta = Math.random() * Math.PI * 2;
      const phi   = Math.acos(2 * Math.random() - 1);
      pos[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);
    }
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const mat = new THREE.PointsMaterial({
      color: 0xaaccdd,
      size: 0.045,
      transparent: true,
      opacity: 0.55,
      sizeAttenuation: true,
    });
    scene.add(new THREE.Points(geo, mat));
  }

  /* ── Theme swap ──────────────────────────────────────────── */
  function applyTheme(name) {
    if (!THEMES[name]) return;
    currentTheme = name;
    const T = THEMES[name];

    /* Remove old drone, add new */
    scene.remove(drone);
    buildDrone();
    scene.add(drone);

    /* Update lights */
    const cols = [T.light1, T.light2, T.light3, T.light1];
    lights.motor.forEach((pl, i) => {
      pl.color.setHex(cols[i % cols.length]);
    });
    lights.top.color.setHex(T.light2);
    lights.bot.color.setHex(T.light3);

    /* Update UI accent */
    document.querySelectorAll('.d3-color-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.theme === name);
    });
  }

  /* ── Render loop ─────────────────────────────────────────── */
  let prevTime = 0;
  function animate(time) {
    frameId = requestAnimationFrame(animate);
    const dt = Math.min((time - prevTime) / 16.67, 3);
    prevTime = time;

    /* Auto-rotate logic */
    const idleMs = time - lastInteractionTime;
    if (!isUserInteracting && idleMs > 1800) {
      autoRotateEnabled = true;
    }
    if (autoRotateEnabled && !isUserInteracting) {
      sphericalTarget.theta += CFG.autoRotateSpeed * dt;
    }

    /* Damped spherical lerp */
    spherical.theta  = lerp(spherical.theta,  sphericalTarget.theta,  CFG.dampingFactor * dt * 6);
    spherical.phi    = lerp(spherical.phi,    sphericalTarget.phi,    CFG.dampingFactor * dt * 6);
    spherical.radius = lerp(spherical.radius, sphericalTarget.radius, CFG.dampingFactor * dt * 6);

    spherical.phi = clamp(spherical.phi, 0.25, 2.5);
    spherical.radius = clamp(spherical.radius, CFG.minDistance, CFG.maxDistance);

    const cp = sphericalToCartesian(spherical);
    camera.position.set(cp.x, cp.y, cp.z);
    camera.lookAt(0, 0.15, 0);

    /* Prop spin */
    const t = time * 0.001;
    propellers.forEach((p, i) => {
      p.group.rotation.y += p.dir * p.speed * dt;
    });

    /* Glow pulse on halo meshes */
    glowMeshes.forEach((m, i) => {
      m.material.opacity = 0.06 + Math.sin(t * 2.5 + i * 0.8) * 0.05;
    });

    /* Light pulse */
    if (lights.motor) {
      lights.motor.forEach((pl, i) => {
        pl.intensity = 1.6 + Math.sin(t * 3.1 + i * 1.57) * 0.3;
      });
    }

    /* Attitude update for UI */
    if (drone) {
      updateAttitudeUI();
    }

    renderer.render(scene, camera);
  }

  function updateAttitudeUI() {
    const roll  = el.roll();
    const pitch = el.pitch();
    const yaw   = el.yaw();
    if (!roll) return;

    const r = deg(spherical.theta % (Math.PI * 2) - Math.PI);
    const p = deg(spherical.phi - Math.PI / 2);
    const y = deg((spherical.theta * 2) % (Math.PI * 2) - Math.PI);
    roll.textContent  = r + '°';
    pitch.textContent = p + '°';
    yaw.textContent   = y + '°';
  }

  /* ── Fake telemetry ──────────────────────────────────────── */
  let _throttle = 45, _voltage = 16.1, _rssi = 89, _temp = 32;
  function updateTelemetry() {
    _throttle = clamp(_throttle + (Math.random() - 0.48) * 4, 30, 95);
    _voltage  = clamp(_voltage  + (Math.random() - 0.52) * 0.05, 14.4, 16.8);
    _rssi     = clamp(_rssi     + (Math.random() - 0.5) * 3, 70, 99);
    _temp     = clamp(_temp     + (Math.random() - 0.49) * 1, 28, 55);

    const v  = el.voltage();
    const th = el.throttle();
    const rs = el.rssi();
    const tm = el.temp();
    if (v)  { v.textContent  = _voltage.toFixed(1) + 'V'; v.className = 'd3-telem-val' + (_voltage < 14.8 ? ' warn' : ''); }
    if (th) th.textContent = Math.round(_throttle) + '%';
    if (rs) { rs.textContent = Math.round(_rssi) + '%'; rs.className = 'd3-telem-val' + (_rssi < 75 ? ' warn' : ''); }
    if (tm) { tm.textContent = Math.round(_temp) + '°C'; tm.className = 'd3-telem-val' + (_temp > 48 ? ' hot' : _temp > 42 ? ' warn' : ''); }

    /* Motor RPMs */
    for (let i = 0; i < 4; i++) {
      const base = CFG.motorIdleRPM + _throttle / 100 * (CFG.motorMaxRPM - CFG.motorIdleRPM);
      const rpm  = Math.round(base + (Math.random() - 0.5) * 800);
      const pct  = ((rpm - CFG.motorIdleRPM) / (CFG.motorMaxRPM - CFG.motorIdleRPM) * 100).toFixed(0);
      const fill = document.querySelector(`.d3-motor-fill[data-m="${i}"]`);
      const rpmEl= document.querySelector(`.d3-motor-rpm[data-m="${i}"]`);
      if (fill) fill.style.width = pct + '%';
      if (rpmEl) rpmEl.textContent = (rpm / 1000).toFixed(1) + 'k';

      /* Sync prop speed to throttle */
      if (propellers[i]) {
        propellers[i].speed = 0.08 + (_throttle / 100) * 0.38;
      }
    }
  }

  /* ── Resize handler ──────────────────────────────────────── */
  function onResize() {
    if (!canvasWrap || !renderer) return;
    const W = canvasWrap.clientWidth;
    const H = canvasWrap.clientHeight;
    renderer.setSize(W, H, false);
    camera.aspect = W / H;
    camera.updateProjectionMatrix();
  }

  /* ── Pointer events (custom orbit) ──────────────────────── */
  function onPointerDown(e) {
    isUserInteracting = true;
    autoRotateEnabled = false;
    lastInteractionTime = performance.now();
    const c = e.touches ? e.touches[0] : e;
    pointer = { x: c.clientX, y: c.clientY, button: e.button || 0 };
  }

  function onPointerMove(e) {
    if (!isUserInteracting) return;
    const c = e.touches ? e.touches[0] : e;
    const dx = c.clientX - pointer.x;
    const dy = c.clientY - pointer.y;
    pointer.x = c.clientX;
    pointer.y = c.clientY;

    if (pointer.button === 2 || (e.touches && e.touches.length === 2)) {
      /* Pan */
    } else {
      /* Orbit */
      sphericalTarget.theta -= dx * 0.008;
      sphericalTarget.phi   += dy * 0.008;
    }
    lastInteractionTime = performance.now();
  }

  function onPointerUp() {
    isUserInteracting = false;
    lastInteractionTime = performance.now();
  }

  let _pinchDist0 = 0;
  function onTouchStart(e) {
    if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      _pinchDist0 = Math.sqrt(dx * dx + dy * dy);
    }
  }

  function onTouchMove(e) {
    if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const delta = _pinchDist0 - dist;
      sphericalTarget.radius += delta * 0.012;
      _pinchDist0 = dist;
    }
    e.preventDefault();
  }

  function onWheel(e) {
    e.preventDefault();
    sphericalTarget.radius += e.deltaY * 0.004;
    lastInteractionTime = performance.now();
  }

  function onContextMenu(e) { e.preventDefault(); }

  /* ── Bind events ─────────────────────────────────────────── */
  function bindEvents(wrap) {
    wrap.addEventListener('mousedown',   onPointerDown, { passive: true });
    wrap.addEventListener('mousemove',   onPointerMove, { passive: true });
    wrap.addEventListener('mouseup',     onPointerUp,   { passive: true });
    wrap.addEventListener('mouseleave',  onPointerUp,   { passive: true });
    wrap.addEventListener('touchstart',  onPointerDown, { passive: true });
    wrap.addEventListener('touchstart',  onTouchStart,  { passive: true });
    wrap.addEventListener('touchmove',   onPointerMove, { passive: false });
    wrap.addEventListener('touchmove',   onTouchMove,   { passive: false });
    wrap.addEventListener('touchend',    onPointerUp,   { passive: true });
    wrap.addEventListener('wheel',       onWheel,       { passive: false });
    wrap.addEventListener('contextmenu', onContextMenu, { passive: false });

    /* Color theme buttons */
    document.querySelectorAll('.d3-color-btn').forEach(btn => {
      btn.addEventListener('click', () => applyTheme(btn.dataset.theme));
    });
  }

  /* ── Main init ───────────────────────────────────────────── */
  function init() {
    if (initialized) return;
    if (typeof THREE === 'undefined') {
      console.error('[drone3d] THREE.js not loaded');
      return;
    }

    canvasWrap = document.querySelector('.d3-canvas-wrap');
    if (!canvasWrap) return;

    const canvas = canvasWrap.querySelector('canvas');
    if (!canvas) return;

    initialized = true;
    initScene(canvas);
    bindEvents(canvasWrap);

    /* Resize observer */
    resizeObserver = new ResizeObserver(onResize);
    resizeObserver.observe(canvasWrap);

    /* Start telemetry updates */
    telemetryTimer = setInterval(updateTelemetry, CFG.telemetryInterval);
    updateTelemetry();

    /* Hide loading overlay */
    setTimeout(() => {
      const ld = document.querySelector('.d3-loading');
      if (ld) ld.classList.add('hidden');
    }, 600);

    /* Section reveal */
    document.getElementById('drone-3d').classList.add('d3-revealed');

    /* Start render */
    animate(0);
  }

  /* ── Intersection Observer — lazy init ───────────────────── */
  function setup() {
    const section = document.getElementById('drone-3d');
    if (!section) return;

    const io = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !initialized) {
          init();
          io.disconnect();
        }
      });
    }, { threshold: 0.15 });

    io.observe(section);
  }

  /* ── Boot ────────────────────────────────────────────────── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
  } else {
    setup();
  }

  /* ── Cleanup on page unload ──────────────────────────────── */
  window.addEventListener('beforeunload', () => {
    if (frameId) cancelAnimationFrame(frameId);
    if (telemetryTimer) clearInterval(telemetryTimer);
    if (resizeObserver) resizeObserver.disconnect();
    if (renderer) renderer.dispose();
  });

  /* ── Public API (optional) ───────────────────────────────── */
  window.Drone3D = { applyTheme };

})();
