// boss3d.mjs
// Place next to boss_battles.html. Requires ./libs/three.module.js and example loaders in ./libs/ (see instructions).

import * as THREE from './libs/three.module.js';
import { GLTFLoader } from './libs/GLTFLoader.js';
import { DRACOLoader } from './libs/DRACOLoader.js';
import { OrbitControls } from './libs/OrbitControls.js';

const container = document.getElementById('arena');
const logEl = document.getElementById('battle-log');
function log(text){ const d=document.createElement('div'); d.textContent = `[${new Date().toLocaleTimeString()}] ${text}`; logEl.appendChild(d); logEl.scrollTop = logEl.scrollHeight; }

// UI state
let maxBossHealth = 1400, bossHealth = maxBossHealth, bossAlive = true, skillPoints = 12, currentPhase = 1;
function updateUI(){
  const percent = Math.max(0, Math.floor((bossHealth/maxBossHealth)*100));
  document.getElementById('boss-health-fill').style.width = percent + '%';
  document.getElementById('boss-health-text').textContent = `${bossHealth} / ${maxBossHealth}`;
  const fill = document.getElementById('boss-health-fill');
  if (percent > 70) fill.style.background = '#e74c3c';
  else if (percent > 40) fill.style.background = '#f39c12';
  else fill.style.background = '#c0392b';
  document.getElementById('skill-points').textContent = skillPoints;
}
updateUI();

function getTokenFromStorageOrCookie(){
  try{ const t = localStorage.getItem('access_token'); if (t) return t; } catch(e){}
  try {
    const cookies = document.cookie.split(';').map(s=>s.trim());
    for (const c of cookies) if (c.startsWith('access_token=')) return decodeURIComponent(c.split('=')[1]);
  } catch(e){}
  return null;
}

function webglAvailable(){
  try {
    const canvas = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
  } catch(e){ return false; }
}

// Fallback wiring (no 3D)
function wireButtonsWithout3D(){
  const logLocal = (m)=>{ const d=document.createElement('div'); d.textContent='['+new Date().toLocaleTimeString()+'] '+m; logEl.appendChild(d); logEl.scrollTop=logEl.scrollHeight; };
  let mMax = 1400, hp = mMax, alive = true, sp = 12;
  function upd(){ const pct = Math.max(0, Math.floor((hp/mMax)*100)); document.getElementById('boss-health-fill').style.width = pct + '%'; document.getElementById('boss-health-text').textContent = hp+' / '+mMax; document.getElementById('skill-points').textContent = sp; }
  upd();
  async function sendAttack(dmg, isSpecial){
    try {
      const token = getTokenFromStorageOrCookie(); if (!token) { logLocal('No auth token'); return null; }
      const res = await fetch('/battles/group/attack',{ method:'POST', headers:{ 'Authorization':'Bearer '+token, 'Content-Type':'application/json' }, body: JSON.stringify({ damage:dmg, special: !!isSpecial })});
      if (!res.ok){ logLocal('Server call failed: ' + res.status); return null; }
      return await res.json();
    } catch(e){ logLocal('Network error'); return null; }
  }
  document.getElementById('attack-btn').addEventListener('click', async ()=>{
    if (!alive) return; const dmg = 60 + Math.floor(Math.random()*40); hp = Math.max(0, hp - dmg); upd(); logLocal('⚔️ Attack '+dmg); if (hp<=0){ alive=false; logLocal('🏆 Boss defeated (no-3d)'); }
    const s = await sendAttack(dmg, false); if (s) { if (typeof s.boss_health === 'number'){ hp = s.boss_health; upd(); } }
  });
  document.getElementById('special-btn').addEventListener('click', async ()=>{
    if (!alive) return; if (sp < 4){ logLocal('❌ Not enough SP'); return; } sp -= 4; upd(); const dmg = 180 + Math.floor(Math.random()*90); hp = Math.max(0, hp - dmg); upd(); logLocal('💥 Special '+dmg); if (hp<=0){ alive=false; logLocal('🏆 Boss defeated (no-3d)'); }
    const s = await sendAttack(dmg, true); if (s) { if (typeof s.boss_health === 'number'){ hp = s.boss_health; upd(); } }
  });
  document.getElementById('heal-btn').addEventListener('click', async ()=>{ const s = await (async ()=>{ try{ const token = getTokenFromStorageOrCookie(); if (!token){ logLocal('No auth token'); return null; } const r = await fetch('/battles/group/heal',{method:'POST', headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'}}); if (!r.ok){ logLocal('Heal failed: '+r.status); return null; } return await r.json(); }catch(e){ logLocal('Network error'); return null; } })(); if (s) { if (typeof s.boss_health === 'number'){ hp = s.boss_health; upd(); } logLocal('❤️ Healed (no-3d)'); } });
  document.getElementById('reset-btn').addEventListener('click', ()=>{ hp = mMax; alive = true; sp = 12; upd(); logLocal('↺ Reset (no-3d)'); });
}

// Main flow
if (!webglAvailable()){
  log('WebGL unavailable — 3D disabled, UI still works.');
  wireButtonsWithout3D();
} else {
  initThreeAndWS();
}

function initThreeAndWS(){
  // renderer
  const renderer = new THREE.WebGLRenderer({ antialias:true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(container.clientWidth, container.clientHeight);
  try { renderer.outputColorSpace = THREE.SRGBColorSpace; } catch(e){} // older r's might not have this property
  while (container.firstChild) container.removeChild(container.firstChild);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x02040a);
  scene.fog = new THREE.FogExp2(0x000000, 0.0009);

  const camera = new THREE.PerspectiveCamera(50, container.clientWidth/container.clientHeight, 0.1, 4000);
  camera.position.set(0,38,160);

  let controls = null;
  try { controls = new OrbitControls(camera, renderer.domElement); controls.target.set(0,-6,0); controls.update(); } catch(e){ console.warn('OrbitControls failed', e); }

  const hemi = new THREE.HemisphereLight(0xffffff, 0x111122, 0.6); scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 1.0); dir.position.set(60,120,40); scene.add(dir);

  const ground = new THREE.Mesh(new THREE.CircleGeometry(170,64), new THREE.MeshStandardMaterial({ color:0x071219, roughness:0.95 }));
  ground.rotation.x = -Math.PI/2; ground.position.y = -28; scene.add(ground);

  const effects = new THREE.Group(); scene.add(effects);
  const shockMat = new THREE.MeshBasicMaterial({ color:0x88b7ff, transparent:true, opacity:0.0, side:THREE.DoubleSide });
  const shock = new THREE.Mesh(new THREE.RingGeometry(36,40,64), shockMat); shock.rotation.x=-Math.PI/2; shock.position.y=-6; scene.add(shock);

  const draco = new DRACOLoader();
  const gltfLoader = new GLTFLoader();
  gltfLoader.setDRACOLoader(draco);

  const mixers = [];
  const clock = new THREE.Clock();

  // procedural boss (fallback)
  const procGroup = new THREE.Group();
  const geo = new THREE.IcosahedronGeometry(32,2);
  const mat = new THREE.MeshStandardMaterial({ color:0x552222, roughness:0.6, metalness:0.2 });
  const procMesh = new THREE.Mesh(geo, mat); procGroup.add(procMesh);
  procGroup.position.set(0,-6,-10); scene.add(procGroup);
  let bossNode = procGroup;

  // model candidates (tries local first)
  const bossCandidates = ['/models/local-boss.glb',
    'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/RiggedFigure/glTF-Binary/RiggedFigure.glb',
    'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/Fox/glTF-Binary/Fox.glb'
  ];
  const playerCandidates = ['/models/local-player.glb',
    'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/RobotExpressive/glTF-Binary/RobotExpressive.glb'
  ];

  // loader helpers
  function loadWithTimeout(url, ms=3000){
    return new Promise((resolve)=>{
      let done=false;
      const timer = setTimeout(()=>{ if (!done){ done = true; resolve(null); } }, ms);
      try {
        gltfLoader.load(url, (gltf)=>{ if (done) return; done = true; clearTimeout(timer); resolve({url,gltf}); }, undefined, ()=>{ if (done) return; done=true; clearTimeout(timer); resolve(null); });
      } catch(e){ if (!done){ done=true; clearTimeout(timer); resolve(null); } }
    });
  }
  async function tryCandidates(cands, perTry=3000, overall=6000){
    const overallTimer = new Promise(res=> setTimeout(()=> res(null), overall));
    const attempt = (async()=>{ for (const u of cands){ const r = await loadWithTimeout(u, perTry); if (r) return r; } return null; })();
    return await Promise.race([overallTimer, attempt]);
  }

  // load models and ensure fallback motion
  (async ()=>{
    log('Loading models (timeout 6s each set)...');
    const [bossRes, playerRes] = await Promise.all([ tryCandidates(bossCandidates,3000,6000), tryCandidates(playerCandidates,3000,6000) ]);

    if (bossRes && bossRes.gltf){
      try {
        scene.remove(procGroup);
        bossNode = bossRes.gltf.scene || bossRes.gltf.scenes[0];
        bossNode.traverse(n => { if (n.isMesh){ n.castShadow=true; n.frustumCulled=false; }});
        bossNode.position.set(0,-6,-10);
        bossNode.scale.set(1.6,1.6,1.6);
        scene.add(bossNode);
        if (bossRes.gltf.animations && bossRes.gltf.animations.length){
          const m = new THREE.AnimationMixer(bossNode);
          bossRes.gltf.animations.forEach(a=> m.clipAction(a).play());
          mixers.push(m);
          log('Loaded boss model with animations: ' + bossRes.url);
        } else {
          bossNode.userData.fallbackMotion = true;
          log('Loaded boss model (no animations) — using fallback motion. ' + bossRes.url);
        }
      } catch(e){
        console.warn('add boss model err', e);
        log('Loaded boss model but display failed, using procedural fallback.');
        if (!scene.children.includes(procGroup)) scene.add(procGroup);
        bossNode = procGroup;
        bossNode.userData.fallbackMotion = true;
      }
    } else {
      log('Boss model not loaded — using procedural boss.');
      bossNode = procGroup;
      bossNode.userData.fallbackMotion = true;
    }

    if (playerRes && playerRes.gltf){
      try {
        const playerNode = playerRes.gltf.scene || playerRes.gltf.scenes[0];
        playerNode.traverse(n=>{ if (n.isMesh){ n.castShadow=true; n.frustumCulled=false; }});
        playerNode.position.set(-40,-6,18); playerNode.scale.set(1.3,1.3,1.3);
        scene.add(playerNode);
        if (playerRes.gltf.animations && playerRes.gltf.animations.length){
          const m = new THREE.AnimationMixer(playerNode);
          const acts = playerRes.gltf.animations.map(a => m.clipAction(a));
          const idle = acts.find(a => a._clip && /idle/i.test(a._clip.name)) || acts[0];
          if (idle) idle.play();
          mixers.push(m);
          log('Loaded player with animations: ' + playerRes.url);
        } else {
          playerNode.userData.fallbackMotion = true;
          log('Loaded player (no animations) — fallback motion enabled.');
        }
      } catch(e){ console.warn('player add err', e); log('Player loaded but display failed.'); }
    } else {
      log('Player model not loaded — using placeholder.');
    }

    // status overlay
    try {
      let statusOverlay = document.getElementById('three-status-overlay');
      if (!statusOverlay){
        statusOverlay = document.createElement('div');
        statusOverlay.id = 'three-status-overlay';
        statusOverlay.style.position = 'absolute';
        statusOverlay.style.left = '12px';
        statusOverlay.style.bottom = '12px';
        statusOverlay.style.background = 'rgba(0,0,0,0.45)';
        statusOverlay.style.padding = '6px 8px';
        statusOverlay.style.borderRadius = '6px';
        statusOverlay.style.fontSize = '12px';
        statusOverlay.style.zIndex = 9999;
        container.appendChild(statusOverlay);
      }
      statusOverlay.textContent = `Boss: ${bossRes && bossRes.url ? '✓' : '✗'}   Player: ${playerRes && playerRes.url ? '✓' : '✗'}`;
    } catch(e){}
  })().catch(e => { console.error('Model flow failed:', e); log('Model flow failed, using procedural visuals.'); bossNode = procGroup; bossNode.userData.fallbackMotion = true; });

  // sprite texture
  function makeSprite(){ const s=128; const c=document.createElement('canvas'); c.width=c.height=s; const ctx=c.getContext('2d'); const g=ctx.createRadialGradient(s/2,s/2,0,s/2,s/2,s/2); g.addColorStop(0,'rgba(255,255,255,1)'); g.addColorStop(0.2,'rgba(255,220,120,0.95)'); g.addColorStop(0.55,'rgba(255,140,60,0.6)'); g.addColorStop(1,'rgba(0,0,0,0)'); ctx.fillStyle=g; ctx.fillRect(0,0,s,s); return new THREE.CanvasTexture(c); }
  const spriteTex = makeSprite();
  function spawnBurst(power=1){ const count=Math.floor(14*power); for (let i=0;i<count;i++){ const mat=new THREE.SpriteMaterial({ map:spriteTex, transparent:true, blending:THREE.AdditiveBlending }); const sp=new THREE.Sprite(mat); sp.scale.set(8+Math.random()*10*power,8+Math.random()*10*power,1); sp.position.set((Math.random()-0.5)*18,(Math.random()*18)-2,(Math.random()-0.5)*18); sp.userData={ vel:new THREE.Vector3((Math.random()-0.5)*80*power,18+Math.random()*60*power,(Math.random()-0.5)*80*power) }; effects.add(sp); setTimeout(()=>{ try{ effects.remove(sp); sp.material.map.dispose(); sp.material.dispose(); }catch(e){} }, 1400 + Math.random()*800);} }

  // guaranteed animate (fallback motion shown)
  function animate(){
    const dt = clock.getDelta();
    const elapsed = clock.getElapsedTime();

    try {
      if (mixers && mixers.length) mixers.forEach(m => { try { m.update(dt); } catch(e) {} });
    } catch(e){ console.warn('mixer err', e); }

    try {
      if (bossNode){
        const fb = bossNode.userData && bossNode.userData.fallbackMotion;
        if (fb){
          bossNode.rotation.y += 0.8 * dt;
          bossNode.position.y = -6 + Math.sin(elapsed * 1.8) * 2.0;
        }
      }
      scene.traverse(obj => {
        if (obj.userData && obj.userData.fallbackMotion && obj !== bossNode){
          obj.rotation.y += 1.2 * dt;
        }
      });
    } catch(e){ console.warn('fallback motion err', e); }

    try {
      effects.children.forEach(c=>{ if (c.userData && c.userData.vel) c.position.addScaledVector(c.userData.vel, dt); if (c.material) c.material.opacity = Math.max(0, (c.material.opacity || 1) - dt*1.6); });
      shock.material.opacity = Math.max(0, shock.material.opacity - dt*0.9);
    } catch(e){ console.warn('effects err', e); }

    if (controls) try{ controls.update(); } catch(e){}

    try { renderer.render(scene, camera); } catch(e){ console.error('render failed', e); }
    requestAnimationFrame(animate);
  }
  animate();

  window.addEventListener('resize', ()=>{ try{ renderer.setSize(container.clientWidth, container.clientHeight); camera.aspect = container.clientWidth / container.clientHeight; camera.updateProjectionMatrix(); } catch(e){} });

  // ---------- UI logic and server calls ----------
  async function sendAttackToServer(damage, isSpecial){
    try { const token = getTokenFromStorageOrCookie(); if (!token) { log('No authentication token found'); return null; } const res = await fetch('/battles/group/attack', { method:'POST', headers:{ 'Authorization':'Bearer '+token, 'Content-Type':'application/json' }, body: JSON.stringify({ damage, special: !!isSpecial }) }); if (!res.ok){ log('Server call failed: ' + res.status); return null; } return await res.json(); } catch(e){ console.warn('Server fetch error', e); log('Network error - check connection'); return null; }
  }
  async function sendHealToServer(){ try { const token = getTokenFromStorageOrCookie(); if (!token) { log('No authentication token found'); return null; } const res = await fetch('/battles/group/heal', { method:'POST', headers:{ 'Authorization':'Bearer '+token, 'Content-Type':'application/json' } }); if (!res.ok){ log('Heal failed: ' + res.status); return null; } return await res.json(); } catch(e){ console.warn('Heal fetch error', e); log('Network error - check connection'); return null; } }

  function applyDamageLocal(damage, isSpecial){
    if (!bossAlive) return;
    bossHealth = Math.max(0, bossHealth - damage);
    updateUI();
    try { if (bossNode && bossNode.scale){ const orig = bossNode.scale.clone(); bossNode.scale.multiplyScalar(1.05); setTimeout(()=> { bossNode.scale.copy(orig); }, 160); } } catch(e){ console.warn('pulse error', e); }
    spawnBurst(isSpecial?1.6:1.0);
    shock.material.opacity = 0.9 * (isSpecial?1.4:1.0);
    log((isSpecial?'💥 SPECIAL':'⚔️ Attack') + ` ${damage} dmg`);
    if (bossHealth <= 0){ bossAlive=false; onBossDefeated(); } else { const pct = bossHealth/maxBossHealth*100; const newPhase = (pct>70)?1:(pct>40)?2:3; if (newPhase !== currentPhase){ currentPhase=newPhase; document.getElementById('boss-phase').textContent = currentPhase; log('⚠️ Phase -> '+currentPhase); } }
  }

  function mergeServerState(data){
    if (!data) return;
    try {
      const health = data.boss_health ?? data.bossHealth ?? data.hp ?? data.health ?? null;
      if (typeof health === 'number'){ bossHealth = health; updateUI(); if (bossHealth <= 0 && bossAlive){ bossAlive=false; onBossDefeated(); } }
      if (typeof data.skill_points === 'number'){ skillPoints = data.skill_points; updateUI(); }
      if (data.battle_status) document.getElementById('battle-status').textContent = data.battle_status;
      if (data.message) log(data.message);
    } catch(e){ console.warn('merge error', e); }
  }

  async function handleAttackClick(){ if (!bossAlive) return; const damage = 60 + Math.floor(Math.random()*40); applyDamageLocal(damage, false); const serverData = await sendAttackToServer(damage, false); if (serverData) mergeServerState(serverData); if (wsClient && wsClient.readyState === WebSocket.OPEN) try{ wsClient.send(JSON.stringify({ type:'attack', damage, special:false })); }catch(e){} }
  async function handleSpecialClick(){ if (!bossAlive) return; if (skillPoints < 4){ log('❌ Not enough SP'); return; } skillPoints -= 4; updateUI(); const damage = 180 + Math.floor(Math.random()*90); applyDamageLocal(damage, true); const serverData = await sendAttackToServer(damage, true); if (serverData) mergeServerState(serverData); if (wsClient && wsClient.readyState === WebSocket.OPEN) try{ wsClient.send(JSON.stringify({ type:'attack', damage, special:true })); }catch(e){} }
  async function handleHealClick(){ const serverData = await sendHealToServer(); if (serverData) { mergeServerState(serverData); log('❤️ Healed group for 120 HP'); } else { log('Heal action failed'); } }
  function handleResetClick(){ bossHealth = maxBossHealth; bossAlive = true; skillPoints = 12; currentPhase = 1; document.getElementById('battle-status').textContent = 'Idle'; if (bossNode && !scene.children.includes(bossNode)) scene.add(bossNode); bossNode && bossNode.scale && bossNode.scale.set(1,1,1); updateUI(); log('🔁 Battle reset (local)'); }

  document.getElementById('attack-btn').addEventListener('click', handleAttackClick);
  document.getElementById('special-btn').addEventListener('click', handleSpecialClick);
  document.getElementById('heal-btn').addEventListener('click', handleHealClick);
  document.getElementById('reset-btn').addEventListener('click', handleResetClick);

  function onBossDefeated(){ log('🏆 Boss defeated!'); document.getElementById('battle-status').textContent = 'Victory'; let s=1.0; const vanish = setInterval(()=>{ if (!bossNode){ clearInterval(vanish); return; } bossNode.rotation.y += 0.6; bossNode.scale.multiplyScalar(0.92); s *= 0.92; if (s < 0.03){ clearInterval(vanish); try{ scene.remove(bossNode); }catch(e){} } }, 28); }

  // WebSocket client (connects to /ws?token=<JWT>)
  let wsClient = null;
  (function initWebSocket(){
    let retry=1000, maxRetry=30000;
    const token = getTokenFromStorageOrCookie();
    if (!token){ log('No token for WebSocket — skipping WS connect'); return; }
    const proto = (location.protocol === 'https:') ? 'wss:' : 'ws:';
    const base = `${proto}//${location.host}/ws`;
    function url(){ return `${base}?token=${encodeURIComponent(token)}`; }
    function connect(){
      try { wsClient = new WebSocket(url()); } catch(e){ log('WS init failed: '+String(e)); schedule(); return; }
      wsClient.onopen = ()=>{ log('WebSocket connected'); retry = 1000; try{ wsClient.send(JSON.stringify({ type:'request_state' })); }catch(e){} };
      wsClient.onmessage = (ev)=>{ try{ const msg = JSON.parse(ev.data); if (msg.type==='chat') log(`[chat] ${msg.from||'server'}: ${msg.text||''}`); else if (msg.type==='attack'){ const dmg = Number(msg.damage||0); if (dmg) { applyDamageLocal(dmg, !!msg.special); log('Remote attack: '+dmg); } } else if (msg.type==='state_update' || msg.type==='state'){ mergeServerState(msg.state||msg); log('State update'); } else log('WS: '+ev.data); } catch(e){ console.warn('WS parse err', e); } };
      wsClient.onclose = (ev)=>{ log(`WebSocket closed (code=${ev.code}) — reconnect in ${Math.floor(retry/1000)}s`); schedule(); };
      wsClient.onerror = (err)=>{ console.warn('WS error', err); try{ wsClient.close(); }catch(e){} };
    }
    function schedule(){ setTimeout(()=>{ retry = Math.min(maxRetry, Math.floor(retry*1.5)); connect(); }, retry); }
    connect();
  })();

} // end initThreeAndWS
