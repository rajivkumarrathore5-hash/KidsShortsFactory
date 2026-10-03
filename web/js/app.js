// Kids Shorts Factory - Modern Web App Logic

let activeConfig = {};
let activeVideoPath = null;
let activeScript = null;
let activeTheme = null;
let activeCharacter = null;
let ws = null;
let deferredPrompt = null;

// PWA Service Worker Registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js').catch((err) => {
      console.log('SW registration failed: ', err);
    });
  });
}

// PWA Install Prompt Listener
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const btnInstall = document.getElementById('btn-pwa-install');
  if (btnInstall) {
    btnInstall.style.display = 'block';
    btnInstall.addEventListener('click', () => {
      btnInstall.style.display = 'none';
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(() => {
        deferredPrompt = null;
      });
    });
  }
});

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  connectWebSocket();
  await loadInitialData();
  await loadRecentGallery();
});

// Setup UI Event Listeners
function setupEventListeners() {
  // Mode Chips
  document.querySelectorAll('[data-mode]').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-mode]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });

  // Ratio Chips
  document.querySelectorAll('[data-ratio]').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-ratio]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });

  // Voice Speed Slider
  const speedSlider = document.getElementById('voice-speed-slider');
  const speedVal = document.getElementById('voice-speed-val');
  speedSlider.addEventListener('input', (e) => {
    speedVal.textContent = `${e.target.value}x`;
  });

  // Overlay Opacity Slider
  const opacitySlider = document.getElementById('overlay-opacity-slider');
  const opacityVal = document.getElementById('overlay-opacity-val');
  opacitySlider.addEventListener('input', (e) => {
    opacityVal.textContent = `${e.target.value}%`;
  });

  // Generate Video Button
  document.getElementById('btn-generate-video').addEventListener('click', () => {
    startGeneration({ autoUpload: false });
  });

  // Auto-Run & Upload Button
  document.getElementById('btn-auto-run-upload').addEventListener('click', () => {
    startGeneration({ autoUpload: true });
  });

  // Upload Buttons
  document.getElementById('btn-upload-youtube').addEventListener('click', () => {
    triggerUpload('youtube');
  });

  document.getElementById('btn-upload-facebook').addEventListener('click', () => {
    triggerUpload('facebook');
  });

  // Refresh Gallery Button
  document.getElementById('btn-refresh-gallery').addEventListener('click', loadRecentGallery);
}

// Connect WebSocket for Live Terminal Logs
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/logs`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    document.getElementById('log-status-tag').textContent = 'Live Connected';
    document.getElementById('log-status-tag').style.color = '#10b981';
  };

  ws.onmessage = (event) => {
    const logBox = document.getElementById('terminal-box');
    const msg = event.data;
    logBox.textContent += '\n' + msg;
    logBox.scrollTop = logBox.scrollHeight;

    // Detect steps from logs to update progress circles
    updateStepTrackerFromLog(msg);
  };

  ws.onclose = () => {
    document.getElementById('log-status-tag').textContent = 'Disconnected';
    document.getElementById('log-status-tag').style.color = '#ef4444';
    // Reconnect after 3 seconds
    setTimeout(connectWebSocket, 3000);
  };
}

// Update Animated Step Tracker based on console keywords
function updateStepTrackerFromLog(msg) {
  const lower = msg.toLowerCase();
  const stepScript = document.getElementById('step-script');
  const stepVoice = document.getElementById('step-voice');
  const stepVisuals = document.getElementById('step-visuals');
  const stepRender = document.getElementById('step-render');
  const stepUpload = document.getElementById('step-upload');

  if (lower.includes('generating script') || lower.includes('[script]')) {
    setStepActive(stepScript);
  } else if (lower.includes('[tts]') || lower.includes('indicf5') || lower.includes('audio generation')) {
    setStepDone(stepScript);
    setStepActive(stepVoice);
  } else if (lower.includes('[image]') || lower.includes('visual') || lower.includes('pexels') || lower.includes('flux')) {
    setStepDone(stepVoice);
    setStepActive(stepVisuals);
  } else if (lower.includes('[render]') || lower.includes('ffmpeg') || lower.includes('rendering base video')) {
    setStepDone(stepVisuals);
    setStepActive(stepRender);
  } else if (lower.includes('[upload]') || lower.includes('uploading video') || lower.includes('[fb] uploading')) {
    setStepDone(stepRender);
    setStepActive(stepUpload);
  } else if (lower.includes('[success]') || lower.includes('video saved:')) {
    setStepDone(stepRender);
  }
}

function setStepActive(elem) {
  elem.classList.add('active');
  elem.classList.remove('done');
}

function setStepDone(elem) {
  elem.classList.remove('active');
  elem.classList.add('done');
}

function resetStepTracker() {
  document.querySelectorAll('.step-item').forEach((item) => {
    item.classList.remove('active', 'done');
  });
}

// Fetch Initial Themes & Configuration from Server
async function loadInitialData() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;
    const data = await res.json();
    activeConfig = data.config || {};

    // Populate Themes Dropdown
    const themeSelect = document.getElementById('theme-select');
    themeSelect.innerHTML = '<option value="auto">🎲 [Auto Random] Rotate across 83+ Themes</option>';

    if (data.themes && Array.isArray(data.themes)) {
      // Group by God / Entity
      const grouped = {};
      data.themes.forEach((t) => {
        const god = t.character || 'Devotional Stories';
        if (!grouped[god]) grouped[god] = [];
        grouped[god].push(t);
      });

      for (const [godName, themeList] of Object.entries(grouped)) {
        const optGroup = document.createElement('optgroup');
        optGroup.label = `🕉️ ${godName}`;
        themeList.forEach((themeItem) => {
          const opt = document.createElement('option');
          opt.value = themeItem.id || themeItem.theme;
          opt.textContent = `${themeItem.character} – ${themeItem.theme}`;
          optGroup.appendChild(opt);
        });
        themeSelect.appendChild(optGroup);
      }
    }

    // Apply saved defaults
    if (activeConfig.video_mode) {
      document.querySelectorAll('[data-mode]').forEach((btn) => {
        if (btn.dataset.mode === activeConfig.video_mode) {
          btn.click();
        }
      });
    }

    if (activeConfig.aspect_ratio) {
      document.querySelectorAll('[data-ratio]').forEach((btn) => {
        if (btn.dataset.ratio === activeConfig.aspect_ratio) {
          btn.click();
        }
      });
    }

    if (activeConfig.duration_target) {
      document.getElementById('duration-select').value = String(activeConfig.duration_target);
    }

    if (activeConfig.indicf5_speed) {
      document.getElementById('voice-speed-slider').value = activeConfig.indicf5_speed;
      document.getElementById('voice-speed-val').textContent = `${activeConfig.indicf5_speed}x`;
    }

    if (activeConfig.overlay_transparency) {
      document.getElementById('overlay-opacity-slider').value = activeConfig.overlay_transparency;
      document.getElementById('overlay-opacity-val').textContent = `${activeConfig.overlay_transparency}%`;
    }

    if (typeof activeConfig.overlay_enabled === 'boolean') {
      document.getElementById('overlay-toggle').checked = activeConfig.overlay_enabled;
    }
  } catch (err) {
    console.error('Failed to load initial data:', err);
  }
}

// Start Video Generation
async function startGeneration({ autoUpload = false }) {
  const btnGen = document.getElementById('btn-generate-video');
  const btnAuto = document.getElementById('btn-auto-run-upload');
  const jobStatus = document.getElementById('job-status-badge');

  btnGen.disabled = true;
  btnAuto.disabled = true;
  jobStatus.textContent = 'Generating...';
  jobStatus.style.color = '#f59e0b';

  resetStepTracker();
  setStepActive(document.getElementById('step-script'));

  // Collect Payload
  const activeModeBtn = document.querySelector('[data-mode].active');
  const activeRatioBtn = document.querySelector('[data-ratio].active');

  const payload = {
    theme: document.getElementById('theme-select').value,
    video_mode: activeModeBtn ? activeModeBtn.dataset.mode : 'auto',
    aspect_ratio: activeRatioBtn ? activeRatioBtn.dataset.ratio : '9:16',
    duration: document.getElementById('duration-select').value,
    indicf5_speed: parseFloat(document.getElementById('voice-speed-slider').value),
    overlay_enabled: document.getElementById('overlay-toggle').checked,
    overlay_transparency: parseInt(document.getElementById('overlay-opacity-slider').value, 10),
    caption_style: document.getElementById('caption-style-select').value,
    auto_upload: autoUpload,
  };

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (data.success && data.video_path) {
      activeVideoPath = data.video_path;
      activeScript = data.script;
      activeTheme = data.theme;
      activeCharacter = data.character;

      // Show video player
      const videoPlayer = document.getElementById('main-video-player');
      const placeholder = document.getElementById('preview-placeholder');
      const uploadBox = document.getElementById('upload-box');

      videoPlayer.src = `/outputs/${data.video_filename}`;
      videoPlayer.style.display = 'block';
      placeholder.style.display = 'none';
      uploadBox.style.display = 'grid';

      jobStatus.textContent = 'Ready & Completed';
      jobStatus.style.color = '#10b981';

      videoPlayer.play().catch(() => {});
      await loadRecentGallery();
    } else {
      jobStatus.textContent = 'Failed';
      jobStatus.style.color = '#ef4444';
      alert(`Generation failed: ${data.error || 'Unknown error'}`);
    }
  } catch (err) {
    jobStatus.textContent = 'Error';
    jobStatus.style.color = '#ef4444';
    alert(`Connection error: ${err.message}`);
  } finally {
    btnGen.disabled = false;
    btnAuto.disabled = false;
  }
}

// Trigger Manual Platform Upload
async function triggerUpload(platform) {
  if (!activeVideoPath) {
    alert('Please generate a video first!');
    return;
  }

  const btnYt = document.getElementById('btn-upload-youtube');
  const btnFb = document.getElementById('btn-upload-facebook');
  const targetBtn = platform === 'youtube' ? btnYt : btnFb;

  const origText = targetBtn.innerHTML;
  targetBtn.innerHTML = '<span>Uploading...</span>';
  targetBtn.disabled = true;

  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform: platform,
        video_path: activeVideoPath,
        script: activeScript,
        theme: activeTheme,
        character: activeCharacter,
      }),
    });

    const data = await res.json();
    if (data.success && data.url) {
      alert(`✅ Upload Successful on ${platform.toUpperCase()}!\nLink: ${data.url}`);
    } else {
      alert(`⚠️ Upload failed on ${platform.toUpperCase()}: ${data.error || 'Check console logs'}`);
    }
  } catch (err) {
    alert(`Network error during upload: ${err.message}`);
  } finally {
    targetBtn.innerHTML = origText;
    targetBtn.disabled = false;
  }
}

// Load Recent Gallery Cards
async function loadRecentGallery() {
  const grid = document.getElementById('gallery-grid');
  try {
    const res = await fetch('/api/videos');
    if (!res.ok) return;
    const data = await res.json();
    const videos = data.videos || [];

    if (videos.length === 0) {
      grid.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem;">No recent videos found.</div>';
      return;
    }

    grid.innerHTML = '';
    videos.forEach((vid) => {
      const card = document.createElement('div');
      card.className = 'gallery-card';
      card.innerHTML = `
        <h4>🎬 ${vid.name}</h4>
        <div class="gallery-meta">
          <span>⏱️ ${vid.size_mb} MB</span>
          <span>📅 ${vid.modified}</span>
        </div>
        <button class="chip-btn" style="margin-top:6px; background:rgba(245,158,11,0.1); color:#fbbf24; border-color:rgba(245,158,11,0.3);" onclick="playGalleryVideo('${vid.name}', '${vid.path}')">
          ▶️ Play in Studio
        </button>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    console.error('Failed to load gallery:', err);
  }
}

// Play Selected Video from Gallery
window.playGalleryVideo = function (filename, fullPath) {
  const videoPlayer = document.getElementById('main-video-player');
  const placeholder = document.getElementById('preview-placeholder');
  const uploadBox = document.getElementById('upload-box');

  activeVideoPath = fullPath;
  videoPlayer.src = `/outputs/${filename}`;
  videoPlayer.style.display = 'block';
  placeholder.style.display = 'none';
  uploadBox.style.display = 'grid';

  videoPlayer.scrollIntoView({ behavior: 'smooth' });
  videoPlayer.play().catch(() => {});
};
