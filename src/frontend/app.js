(function () {
    const statusEl = document.getElementById('status');
    const fpsEl = document.getElementById('fps');
    const logEl = document.getElementById('log');
    const videoImg = document.getElementById('video');
    const snapBtn = document.getElementById('snap');
    const zoomInput = document.getElementById('zoom');
    const autoreconnectEl = document.getElementById('autoreconnect');
    const fullscreenBtn = document.getElementById('fullscreen');
    const overlayEl = document.getElementById('overlay');

    let overlayCanvas = null;
    let overlayCtx = null;
    let lastMeta = null;

    let ws = null;
    let lastFrameTime = 0;
    let fps = 0;
    let frameTimes = [];
    let lastBlobUrl = null;
    let reconnectTimer = null;

    function log(msg, type = 'info') {
        const li = document.createElement('li');
        const time = new Date().toLocaleTimeString();
        li.innerHTML = `<div>${time} — ${msg}</div>`;
        li.className = type === 'error' ? 'error' : '';
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.textContent = type === 'error' ? 'ERR' : 'INFO';
        li.appendChild(badge);
        logEl.insertBefore(li, logEl.firstChild);
    }

    function setStatus(s) { statusEl.textContent = s; }

    function updateFps(now) {
        let resizeObserver = null;
        if (lastFrameTime) {
            const dt = now - lastFrameTime;
            frameTimes.push(dt);
            if (frameTimes.length > 20) frameTimes.shift();
            const avg = frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length;
            fps = Math.round(1000 / avg);
            fpsEl.textContent = `FPS: ${fps}`;
        }
        lastFrameTime = now;
    }

    async function startStream() {
        if (ws) return;
        const url = document.getElementById('url').value || null;
        const proto = (location.protocol === 'https:') ? 'wss:' : 'ws:';
        ws = new WebSocket(proto + '//' + location.host + '/ws/stream');
        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
            setStatus('Connected');
            // send start request (auth removed from UI)
            ws.send(JSON.stringify({ url: url }));
            log('Stream started');
            if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
            // show loader until first frame arrives
            const loader = document.getElementById('loader');
            if (loader) loader.classList.remove('hidden');
        };

        ws.onmessage = (evt) => {
            const now = Date.now();
            if (typeof evt.data === 'string') {
                    try {
                        const j = JSON.parse(evt.data);
                        if (j.type === 'detections') {
                            lastMeta = j;
                            drawDetections(j);
                        } else if (j.error) {
                            log('Error: ' + j.error, 'error');
                        } else {
                            log(JSON.stringify(j));
                        }
                    } catch (e) { }
                    return;
                }
            const blob = new Blob([evt.data], { type: 'image/jpeg' });
            const urlObj = URL.createObjectURL(blob);
            // revoke previous blob only after new image loaded
            const prev = lastBlobUrl;
            lastBlobUrl = urlObj;
            videoImg.src = urlObj;
            videoImg.onload = () => {
                if (prev) try { URL.revokeObjectURL(prev); } catch (e) { }
                updateFps(now);
                // hide loader when first frame loaded
                const loader = document.getElementById('loader');
                if (loader && !loader.classList.contains('hidden')) loader.classList.add('hidden');
                ensureOverlayCanvas();
                // redraw any pending meta
                if (lastMeta) drawDetections(lastMeta);
            };
        };

        ws.onclose = () => {
            setStatus('Disconnected');
            ws = null;
            log('Stream stopped');
            // auto-reconnect
            if (autoreconnectEl.checked) {
                log('Attempting reconnect in 2s...');
                reconnectTimer = setTimeout(() => { startStream(); }, 2000);
            }
        };

        ws.onerror = (e) => { log('WebSocket error', 'error'); };
    }

    function stopStream() {
        if (ws) { ws.close(); ws = null; }
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    }

    function snapshot() {
        try {
            const canvas = document.createElement('canvas');
            const w = videoImg.naturalWidth || videoImg.width;
            const h = videoImg.naturalHeight || videoImg.height;
            if (!w || !h) { log('No image available for snapshot', 'error'); return; }
            canvas.width = w; canvas.height = h;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(videoImg, 0, 0, w, h);
            const data = canvas.toDataURL('image/jpeg', 0.9);
            const a = document.createElement('a');
            a.href = data;
            a.download = `snapshot_${Date.now()}.jpg`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            log('Snapshot saved');
        } catch (e) { log('Snapshot failed', 'error'); }
    }

    // thumbnails removed (kept intentionally empty)

    function ensureOverlayCanvas(){
        if (!overlayEl) return;
        const dpr = window.devicePixelRatio || 1;
        const cssW = overlayEl.clientWidth;
        const cssH = overlayEl.clientHeight;
        if (!overlayCanvas){
            overlayCanvas = document.createElement('canvas');
            overlayCanvas.style.position = 'absolute';
            overlayCanvas.style.left = '0';
            overlayCanvas.style.top = '0';
            overlayCanvas.style.width = cssW + 'px';
            overlayCanvas.style.height = cssH + 'px';
            overlayCanvas.width = Math.max(1, Math.round(cssW * dpr));
            overlayCanvas.height = Math.max(1, Math.round(cssH * dpr));
            overlayEl.appendChild(overlayCanvas);
            overlayCtx = overlayCanvas.getContext('2d');
            // scale to device pixels so drawing uses CSS pixels coordinates
            overlayCtx.setTransform(1,0,0,1,0,0);
            overlayCtx.scale(dpr, dpr);
            // keep canvas sized to container
            try {
                const ro = new ResizeObserver(() => {
                    const w = overlayEl.clientWidth;
                    const h = overlayEl.clientHeight;
                    overlayCanvas.style.width = w + 'px';
                    overlayCanvas.style.height = h + 'px';
                    overlayCanvas.width = Math.max(1, Math.round(w * dpr));
                    overlayCanvas.height = Math.max(1, Math.round(h * dpr));
                    overlayCtx = overlayCanvas.getContext('2d');
                    overlayCtx.setTransform(1,0,0,1,0,0);
                    overlayCtx.scale(dpr, dpr);
                });
                ro.observe(overlayEl);
            } catch (e) { /* ResizeObserver not available */ }
        } else {
            overlayCanvas.style.width = cssW + 'px';
            overlayCanvas.style.height = cssH + 'px';
            overlayCanvas.width = Math.max(1, Math.round(cssW * dpr));
            overlayCanvas.height = Math.max(1, Math.round(cssH * dpr));
            overlayCtx = overlayCanvas.getContext('2d');
            overlayCtx.setTransform(1,0,0,1,0,0);
            overlayCtx.scale(dpr, dpr);
        }
    }

    function drawDetections(meta){
        if (!overlayEl) return;
        ensureOverlayCanvas();
        if (!overlayCtx) return;
        const rect = videoImg.getBoundingClientRect();
        const displayW = rect.width;
        const displayH = rect.height;
        const [frameW, frameH] = meta.frame_size || [displayW, displayH];
        const sx = displayW / frameW;
        const sy = displayH / frameH;
        // clear using CSS-pixel coordinates (context is scaled)
        overlayCtx.clearRect(0,0,overlayEl.clientWidth, overlayEl.clientHeight);
        overlayCtx.lineWidth = 3;
        overlayCtx.font = '16px Arial';
        overlayCtx.textBaseline = 'top';
        for (const d of meta.detections || []){
            const [x,y,w,h] = d.box;
            const lx = Math.round(x * sx);
            const ly = Math.round(y * sy);
            const lw = Math.round(w * sx);
            const lh = Math.round(h * sy);
            if (d.label === 'ates'){
                overlayCtx.strokeStyle = 'rgba(255,50,50,0.95)';
                overlayCtx.fillStyle = 'rgba(255,50,50,0.16)';
                overlayCtx.fillRect(lx, ly, lw, lh);
                overlayCtx.strokeRect(lx, ly, lw, lh);
                } else if (d.label === 'duman'){
                    // skip drawing smoke overlays entirely to avoid large yellow scale boxes
                    continue;
                } else {
                overlayCtx.strokeStyle = 'rgba(50,200,255,0.9)';
                overlayCtx.fillStyle = 'rgba(50,200,255,0.08)';
                overlayCtx.fillRect(lx, ly, lw, lh);
                overlayCtx.strokeRect(lx, ly, lw, lh);
            }
            const label = `${d.label}${d.score ? ' '+d.score : ''}`;
            overlayCtx.fillStyle = 'rgba(0,0,0,0.6)';
            const textW = overlayCtx.measureText(label).width + 8;
            overlayCtx.fillRect(lx, ly - 20, textW, 20);
            overlayCtx.fillStyle = '#fff';
            overlayCtx.fillText(label, lx + 4, ly - 18);
        }
    }

    // fullscreen toggle
    fullscreenBtn && fullscreenBtn.addEventListener('click', ()=>{
        const el = document.querySelector('.video-wrap');
        if (!document.fullscreenElement){
            el.requestFullscreen().catch(()=>{});
        } else {
            document.exitFullscreen().catch(()=>{});
        }
    });

    // keyboard shortcuts: Space=start/stop, s=snapshot
    document.addEventListener('keydown', (e) => {
        if (e.code === 'Space') {
            e.preventDefault();
            if (ws) stopStream(); else startStream();
        }
        if (e.key === 's' || e.key === 'S') {
            snapshot();
        }
    });

    // Mobile nav toggle and hash-based client router
    try {
        const navToggle = document.getElementById('nav-toggle');
        const navContainer = document.getElementById('nav-container');
        if (navToggle && navContainer) {
            navToggle.addEventListener('click', (e)=>{
                e.stopPropagation();
                navContainer.classList.toggle('open');
            });
            document.addEventListener('click', (e)=>{
                if (!navContainer.contains(e.target) && !navToggle.contains(e.target)) navContainer.classList.remove('open');
            });
        }

        const routeMap = {
            '#live': () => showSection('live'),
            '#recordings': () => showSection('recordings'),
            '#settings': () => showSection('settings'),
            '#advanced': () => showSection('advanced'),
            '#about': () => showSection('about'),
            '#home': () => showSection('home')
        };

        function showSection(name){
            // hide all page-section nodes
            document.querySelectorAll('.page-section').forEach(s=>{
                s.classList.remove('active');
                s.setAttribute('aria-hidden','true');
            });
            // show main container (home/live)
            const main = document.querySelector('main.container');
            if (!main) return;
            if (name === 'home' || name === 'live'){
                // show main, hide page-sections
                main.style.display = '';
                // scroll to video for live
                if (name === 'live') document.querySelector('.video-wrap')?.scrollIntoView({behavior:'smooth', block:'center'});
            } else {
                // hide main and show chosen section
                main.style.display = 'none';
                const section = document.getElementById(name);
                if (section) { section.classList.add('active'); section.setAttribute('aria-hidden','false'); section.scrollIntoView({behavior:'smooth', block:'center'}); }
            }
            // update active link visuals
            document.querySelectorAll('.nav-links a').forEach(a=>a.classList.remove('active'));
            const active = document.querySelector(`.nav-links a[href="#${name}"]`);
            if (active) active.classList.add('active');
            // close mobile menu when navigating
            navContainer && navContainer.classList.remove('open');
        }

        document.querySelectorAll('.nav-links a').forEach(a=>{
            a.addEventListener('click', (e)=>{
                // allow default hash change, then handle
                setTimeout(()=>{ setActiveHashHandler(); }, 10);
            });
        });

        function setActiveHashHandler(){
            const h = location.hash || '#home';
            const name = h.replace('#','');
            if (routeMap[h]) routeMap[h](); else showSection('home');
        }

        window.addEventListener('hashchange', setActiveHashHandler);
        // initial activation
        setActiveHashHandler();
    } catch (e) { /* ignore if elements missing */ }

    // event bindings
    document.getElementById('start').addEventListener('click', startStream);
    document.getElementById('stop').addEventListener('click', stopStream);
    snapBtn.addEventListener('click', snapshot);
    zoomInput.addEventListener('input', (e) => { videoImg.style.transform = `scale(${e.target.value})`; });

})();
