/* ═══════════════════════════════════════════════════════════════
   MASTER GLORY — Frontend Logic (PAID📩)
   ═══════════════════════════════════════════════════════════════ */

(function () {
'use strict';

var STATE = {
  stats: {
    uptime: 0, total_accounts: 0, total_teams: 0,
    online: 0, in_game: 0, paused: 0,
    match_started: 0, match_completed: 0, match_failed: 0,
    teams: [],
  },
  logs: [],
  logFilter: 'all',
  logSearch: '',
  autoScroll: true,
  teamsFilter: '',
  settings: {},
  lastSyncAt: 0,
  currentView: 'dash',
  polling: null,
  _confirmCallback: null,
};

function $(id) { return document.getElementById(id); }
function $$(sel) { return document.querySelectorAll(sel); }

function esc(s) {
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function num(n) { return Number(n || 0).toLocaleString(); }

function fmtDuration(sec) {
  sec = Math.max(0, Math.floor(Number(sec) || 0));
  var h = Math.floor(sec / 3600);
  var m = Math.floor((sec % 3600) / 60);
  var s = sec % 60;
  var pad = function (n) { return String(n).padStart(2, '0'); };
  return pad(h) + ':' + pad(m) + ':' + pad(s);
}

function timeAgo(ts) {
  if (!ts) return 'never';
  var d = Math.floor((Date.now() - ts) / 1000);
  if (d < 5) return 'just now';
  if (d < 60) return d + 's ago';
  if (d < 3600) return Math.floor(d / 60) + 'm ago';
  if (d < 86400) return Math.floor(d / 3600) + 'h ago';
  return Math.floor(d / 86400) + 'd ago';
}

function setText(id, val) {
  var el = $(id);
  if (el) el.textContent = val;
}

/* ═══════ TOAST ═══════ */
function toast(msg, type) {
  type = type || '';
  var box = $('toasts');
  if (!box) return;
  var el = document.createElement('div');
  el.className = 'toast ' + type;
  var icon = '';
  if (type === 'ok') icon = '<i class="fa-solid fa-check" style="color:var(--ok)"></i>';
  else if (type === 'err') icon = '<i class="fa-solid fa-xmark" style="color:var(--err)"></i>';
  else if (type === 'warn') icon = '<i class="fa-solid fa-triangle-exclamation" style="color:var(--warn)"></i>';
  else icon = '<i class="fa-solid fa-circle-info" style="color:var(--a1)"></i>';
  el.innerHTML = icon + '<span>' + esc(msg) + '</span>';
  box.appendChild(el);
  setTimeout(function () {
    el.classList.add('hide');
    setTimeout(function () { el.remove(); }, 300);
  }, 4000);
}

/* ═══════ CONFIRM ═══════ */
function confirmDialog(title, message, onConfirm) {
  var modal = $('confirmModal');
  if (!modal) return;
  setText('confirmTitle', title || 'Are you sure?');
  setText('confirmMessage', message || 'This action cannot be undone.');
  STATE._confirmCallback = onConfirm;
  modal.classList.add('on');
}

function closeConfirm() {
  var modal = $('confirmModal');
  if (modal) modal.classList.remove('on');
  STATE._confirmCallback = null;
}

/* ═══════ HTTP ═══════ */
async function apiGet(url) {
  try {
    var r = await fetch(url);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch (e) { return { error: e.message }; }
}

async function apiPostForm(url, formData) {
  try {
    var r = await fetch(url, {
      method: 'POST',
      body: formData instanceof FormData ? formData : new URLSearchParams(formData),
    });
    var j = await r.json().catch(function () { return {}; });
    if (!r.ok) throw new Error(j.detail || 'HTTP ' + r.status);
    return j;
  } catch (e) { return { error: e.message }; }
}

async function apiPostJson(url, obj) {
  try {
    var r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(obj || {}),
    });
    var j = await r.json().catch(function () { return {}; });
    if (!r.ok) throw new Error(j.detail || 'HTTP ' + r.status);
    return j;
  } catch (e) { return { error: e.message }; }
}

/* ═══════ STATS ═══════ */
async function fetchStats() {
  var d = await apiGet('/api/stats');
  if (d.error) { setStatus('OFFLINE', true); return; }
  STATE.stats = d;
  STATE.lastSyncAt = Date.now();
  setStatus('ONLINE', false);
  applyStats(d);
  setText('syncTime', 'Synced ' + timeAgo(STATE.lastSyncAt));
}

function setStatus(text, isOff) {
  setText('statusText', text);
  var pill = $('statusPill');
  if (pill) pill.classList.toggle('off', isOff);
  var dot = $('syncDot');
  if (dot) dot.classList.toggle('off', isOff);
}

function applyStats(d) {
  setText('s-uptime', fmtDuration(d.uptime));
  setText('s-teams', num(d.total_teams));
  setText('s-teams-foot', (d.teams_running || []).length + ' running');
  setText('s-online', num(d.online));
  var onlinePct = d.total_accounts > 0 ? Math.round((d.online / d.total_accounts) * 100) : 0;
  setText('s-online-foot', onlinePct + '%');
  setText('s-ingame', num(d.in_game));
  setText('s-started', num(d.match_started));
  setText('s-completed', num(d.match_completed));
  setText('s-completed-foot', num(d.match_failed) + ' failed');

  setText('w-online', num(d.online));
  setText('w-ingame', num(d.in_game));
  setText('w-teams', num(d.total_teams));

  setText('nav-team-count', num(d.total_teams));
  setText('infoAccounts', d.total_accounts || 0);
  setText('infoTeams', d.total_teams || 0);

  renderTeams(d.teams || []);
}

/* ═══════ TEAMS ═══════ */
function renderTeams(teams) {
  var container = $('teamsContainer');
  if (!container) return;

  var q = (STATE.teamsFilter || '').toLowerCase().trim();
  var filtered = teams;
  if (q) {
    filtered = teams.filter(function (t) {
      if (t.id.toLowerCase().indexOf(q) !== -1) return true;
      return t.members.some(function (m) {
        return (m.name || '').toLowerCase().indexOf(q) !== -1 ||
               (m.uid || '').toLowerCase().indexOf(q) !== -1;
      });
    });
  }

  if (filtered.length === 0) {
    container.innerHTML = '<div class="empty"><i class="fa-solid fa-ghost"></i><p>No teams found</p></div>';
    return;
  }

  var scrollTop = container.scrollTop;
  container.innerHTML = filtered.map(teamCardHTML).join('');
  container.scrollTop = scrollTop;

  // Restore saved values
  filtered.forEach(function (t) {
    var saved = STATE['_teamInput_' + t.id];
    if (saved) {
      var sid = safeId(t.id);
      var gEl = $('guild_' + sid);
      var dEl = $('delay_' + sid);
      var lEl = $('loop_' + sid);
      if (gEl && saved.guild) gEl.value = saved.guild;
      if (dEl && saved.delay) dEl.value = saved.delay;
      if (lEl) lEl.checked = !!saved.loop;
    }
  });
}

function safeId(id) {
  return String(id).replace(/[^a-zA-Z0-9_-]/g, '');
}

function teamCardHTML(team) {
  var running = team.running;
  var membersHTML = team.members.map(memberHTML).join('');
  var sid = safeId(team.id);

  return '<div class="team-card' + (running ? ' running' : '') + '" data-team="' + esc(team.id) + '">' +
      '<div class="team-head">' +
        '<div class="team-title"><i class="fa-solid fa-crown"></i>' + esc(team.id) + '</div>' +
        '<div class="team-status ' + (running ? 'running' : 'idle') + '">' +
          (running ? 'RUNNING' : 'IDLE') +
        '</div>' +
      '</div>' +
      '<div class="members-grid">' + membersHTML + '</div>' +
      '<div class="team-actions">' +
        '<div class="team-action-row">' +
          '<input type="number" id="guild_' + sid + '" placeholder="Guild ID" min="1" oninput="MG.saveInput(\'' + esc(team.id) + '\',\'guild\',this.value)">' +
          '<button class="join" onclick="MG.joinGuild(\'' + esc(team.id) + '\',this)">' +
            '<i class="fa-solid fa-user-plus"></i>Join' +
          '</button>' +
        '</div>' +
        '<div class="team-action-row">' +
          '<input type="number" id="delay_' + sid + '" placeholder="Wait Mins" value="2" min="1" max="60" oninput="MG.saveInput(\'' + esc(team.id) + '\',\'delay\',this.value)">' +
          '<label class="loop-check">' +
            '<input type="checkbox" id="loop_' + sid + '" onchange="MG.saveInput(\'' + esc(team.id) + '\',\'loop\',this.checked)">' +
            '<span>Auto-Loop</span>' +
          '</label>' +
        '</div>' +
        '<div class="team-action-row">' +
          (running
            ? '<button class="stop" onclick="MG.stopTeam(\'' + esc(team.id) + '\',this)"><i class="fa-solid fa-stop"></i>STOP TEAM</button>'
            : '<button class="start" onclick="MG.startMatch(\'' + esc(team.id) + '\',this)"><i class="fa-solid fa-play"></i>START MATCH</button>'
          ) +
        '</div>' +
      '</div>' +
    '</div>';
}

function memberHTML(m) {
  var initial = (m.name || m.uid || '?').charAt(0).toUpperCase();
  var status = m.status || 'OFFLINE';
  var isPaused = m.is_paused || status === 'PAUSED';
  var stText = isPaused ? 'PAUSED' : status;
  var stColor = 'var(--text3)';
  if (status === 'IN_MATCH' || status === 'IN_GAME') stColor = 'var(--match)';
  else if (status === 'ONLINE' || status === 'CONNECTING' || status === 'SEARCHING') stColor = 'var(--ok)';
  else if (isPaused) stColor = 'var(--warn)';

  return '<div class="member">' +
      '<div class="member-avatar">' + esc(initial) + '</div>' +
      '<div class="member-info">' +
        '<div class="member-name" title="' + esc(m.name) + '">' + esc(m.name || 'Unknown') + '</div>' +
        '<div class="member-uid" title="' + esc(m.uid) + '">' + esc(m.uid) + '</div>' +
        '<div class="member-uptime">⏱ ' + fmtDuration(m.uptime) + ' · <span style="color:' + stColor + '">' + esc(stText) + '</span></div>' +
      '</div>' +
    '</div>';
}

/* ═══════ TEAM ACTIONS ═══════ */
window.MG = window.MG || {};

MG.saveInput = function (teamId, field, value) {
  var key = '_teamInput_' + teamId;
  if (!STATE[key]) STATE[key] = {};
  STATE[key][field] = value;
};

MG.joinGuild = async function (teamId, btn) {
  var sid = safeId(teamId);
  var guildEl = $('guild_' + sid);
  if (!guildEl) return;
  var gid = (guildEl.value || '').trim();
  if (!gid || !/^\d+$/.test(gid)) {
    toast('Enter a valid numeric Guild ID', 'err');
    return;
  }
  var team = findTeam(teamId);
  if (!team) { toast('Team not found', 'err'); return; }
  var uids = team.members.map(function (m) { return m.uid; }).join(',');

  var old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>Joining...';

  var fd = new FormData();
  fd.append('guild_id', gid);
  fd.append('uids', uids);

  var r = await apiPostForm('/api/clan_join', fd);
  btn.disabled = false;
  btn.innerHTML = old;

  if (r.error) toast('Join failed: ' + r.error, 'err');
  else {
    toast('Joining ' + team.members.length + ' accounts to guild ' + gid, 'ok');
    setTimeout(fetchStats, 1500);
  }
};

MG.startMatch = async function (teamId, btn) {
  var sid = safeId(teamId);
  var delayEl = $('delay_' + sid);
  var loopEl = $('loop_' + sid);
  var delay = delayEl ? parseInt(delayEl.value, 10) || 2 : 2;
  var loop = loopEl ? loopEl.checked : false;

  var old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>Starting...';

  var fd = new FormData();
  fd.append('team_id', teamId);
  fd.append('delay_mins', delay);
  fd.append('loop_match', loop ? 'true' : 'false');

  var r = await apiPostForm('/api/start_team', fd);
  btn.disabled = false;
  btn.innerHTML = old;

  if (r.error) toast('Start failed: ' + r.error, 'err');
  else {
    toast(teamId + ' match started!', 'ok');
    setTimeout(fetchStats, 800);
  }
};

MG.stopTeam = async function (teamId, btn) {
  confirmDialog('Stop Team?', 'Stop ' + teamId + '? Running match will be halted.', async function () {
    var old = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>Stopping...';
    var fd = new FormData();
    fd.append('team_id', teamId);
    var r = await apiPostForm('/api/stop_team', fd);
    btn.disabled = false;
    btn.innerHTML = old;
    if (r.error) toast('Stop failed: ' + r.error, 'err');
    else { toast(teamId + ' stopped', 'warn'); setTimeout(fetchStats, 500); }
  });
};

MG.stopAll = async function () {
  confirmDialog('Stop Everything?', 'All running matches will be stopped.', async function () {
    var r = await apiPostJson('/api/stop_all', {});
    if (r.error) toast('Stop failed: ' + r.error, 'err');
    else { toast('All stopped', 'warn'); setTimeout(fetchStats, 500); }
  });
};

function findTeam(teamId) {
  var teams = STATE.stats.teams || [];
  for (var i = 0; i < teams.length; i++) {
    if (teams[i].id === teamId) return teams[i];
  }
  return null;
}

/* ═══════ LOGS ═══════ */
async function fetchLogs() {
  var d = await apiGet('/api/logs?limit=200');
  if (d.error) return;
  STATE.logs = d.logs || [];
  renderLogs();
}

function classifyLog(msg) {
  var m = String(msg || '').toLowerCase();
  if (m.indexOf('match') !== -1 || m.indexOf('udp') !== -1) return 'match';
  if (m.indexOf('clan') !== -1 || m.indexOf('guild') !== -1) return 'clan';
  if (m.indexOf('gen') !== -1 || m.indexOf('create') !== -1) return 'gen';
  if (m.indexOf('error') !== -1 || m.indexOf('fail') !== -1) return 'error';
  return 'system';
}

function logIcon(cat) {
  if (cat === 'error') return '❌';
  if (cat === 'match') return '⚔️';
  if (cat === 'clan') return '👥';
  if (cat === 'gen') return '✨';
  return '›';
}

function renderLogs() {
  var body = $('termBody');
  if (!body) return;

  var list = STATE.logs.slice();
  if (STATE.logFilter !== 'all') {
    list = list.filter(function (l) { return classifyLog(l) === STATE.logFilter; });
  }
  if (STATE.logSearch) {
    var q = STATE.logSearch.toLowerCase();
    list = list.filter(function (l) { return String(l).toLowerCase().indexOf(q) !== -1; });
  }

  if (list.length === 0) {
    body.innerHTML = '<div class="empty-mini">No logs yet...</div>';
    return;
  }

  var html = list.map(function (line) {
    var m = String(line).match(/^\[([^\]]+)\]\s*(.*)$/);
    var ts = m ? m[1] : '';
    var msg = m ? m[2] : line;
    var cat = classifyLog(msg);
    var ic = logIcon(cat);
    var msgHTML = esc(msg);
    if (STATE.logSearch) {
      try {
        var re = new RegExp('(' + STATE.logSearch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
        msgHTML = msgHTML.replace(re, '<mark>$1</mark>');
      } catch (e) {}
    }
    return '<div class="line"><span class="ts">[' + esc(ts) + ']</span><span class="ic">' + ic + '</span><span class="msg ' + cat + '">' + msgHTML + '</span></div>';
  }).join('');

  body.innerHTML = html;
  if (STATE.autoScroll) body.scrollTop = body.scrollHeight;
}

/* ═══════ SETTINGS ═══════ */
async function loadSettings() {
  var d = await apiGet('/api/settings');
  if (d.error) return;
  STATE.settings = d.settings || {};
  applySettingsToForm();
}

function applySettingsToForm() {
  var s = STATE.settings;
  if ($('setRegion')) $('setRegion').value = s.default_region || 'IND';
  if ($('setDelay')) $('setDelay').value = s.match_delay_mins || 2;
  if ($('setAutoLoop')) $('setAutoLoop').value = String(!!s.auto_loop);
  if ($('setTeamSize')) $('setTeamSize').value = s.team_size || 4;
}

async function saveSettings() {
  var payload = {
    default_region: $('setRegion').value,
    match_delay_mins: parseInt($('setDelay').value, 10) || 2,
    auto_loop: $('setAutoLoop').value === 'true',
    team_size: parseInt($('setTeamSize').value, 10) || 4,
  };
  var r = await apiPostJson('/api/settings', payload);
  if (r.error) toast('Save failed: ' + r.error, 'err');
  else {
    STATE.settings = r.settings || payload;
    toast('Settings saved!', 'ok');
    setTimeout(fetchStats, 500);
  }
}

async function resetSettings() {
  var r = await apiPostJson('/api/settings', {
    default_region: 'IND', match_delay_mins: 2, auto_loop: false, team_size: 4,
  });
  if (r.error) toast('Reset failed: ' + r.error, 'err');
  else {
    STATE.settings = r.settings;
    applySettingsToForm();
    toast('Reset to defaults', 'ok');
  }
}

/* ═══════ VIEW ═══════ */
function switchView(view) {
  STATE.currentView = view;
  $$('.nav-btn').forEach(function (b) { b.classList.toggle('on', b.dataset.view === view); });
  $$('.view').forEach(function (v) { v.classList.remove('on'); });
  var el = $('v-' + view);
  if (el) el.classList.add('on');
  var btn = document.querySelector('.nav-btn[data-view="' + view + '"]');
  if (btn) {
    setText('pageTitle', btn.dataset.title);
    setText('pageSub', btn.dataset.sub);
  }
  document.body.classList.remove('nav-open');
  if (view === 'settings') loadSettings();
  if (view === 'term') fetchLogs();
}

/* ═══════ THEME ═══════ */
function setTheme(theme) {
  if (theme === 'titanium') {
    document.documentElement.removeAttribute('data-theme');
  } else {
    document.documentElement.setAttribute('data-theme', theme);
  }

  // Auto-switch light mode for crystal (white theme)
  var lightThemes = ['crystal'];
  if (lightThemes.indexOf(theme) >= 0) {
    setMode('light');
  } else {
    setMode('dark');
  }

  try { localStorage.setItem('mg_theme', theme); } catch (e) {}
}

function setMode(mode) {
  document.documentElement.setAttribute('data-mode', mode);
  var btn = $('themeBtn');
  if (btn) {
    var i = btn.querySelector('i');
    if (i) i.className = mode === 'light' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
  }
  try { localStorage.setItem('mg_mode', mode); } catch (e) {}
}

function toggleMode() {
  var cur = document.documentElement.getAttribute('data-mode') || 'dark';
  setMode(cur === 'dark' ? 'light' : 'dark');
}

/* ═══════ ADD ACCOUNT ═══════ */
function openAdd() {
  var m = $('addModal');
  if (!m) return;
  if ($('inUid')) $('inUid').value = '';
  if ($('inPass')) $('inPass').value = '';
  m.classList.add('on');
}

function closeAdd() {
  var m = $('addModal');
  if (m) m.classList.remove('on');
}

async function submitAdd(e) {
  if (e) e.preventDefault();
  var uid = ($('inUid').value || '').trim();
  var pass = ($('inPass').value || '').trim();
  if (!uid || !pass) {
    toast('UID and password required', 'err');
    return;
  }
  var btn = $('addSubmitBtn');
  var old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>Adding...';

  var r = await apiPostJson('/api/account/add', { uid: uid, password: pass });
  btn.disabled = false;
  btn.innerHTML = old;

  if (r.error) toast('Add failed: ' + r.error, 'err');
  else {
    toast('Account added: ' + uid, 'ok');
    closeAdd();
    setTimeout(fetchStats, 800);
  }
}

/* ═══════ BINDINGS ═══════ */
function initBindings() {
  $$('.nav-btn').forEach(function (b) {
    b.addEventListener('click', function () { switchView(b.dataset.view); });
  });

  var burger = $('burger');
  if (burger) burger.addEventListener('click', function () {
    document.body.classList.toggle('nav-open');
  });
  var overlay = $('navOverlay');
  if (overlay) overlay.addEventListener('click', function () {
    document.body.classList.remove('nav-open');
  });

  var themeBtn = $('themeBtn');
  if (themeBtn) themeBtn.addEventListener('click', toggleMode);

  var refreshBtn = $('refreshBtn');
  if (refreshBtn) refreshBtn.addEventListener('click', function () {
    toast('Refreshing...');
    fetchStats();
    fetchLogs();
  });

  var addBtn = $('addBtn');
  if (addBtn) addBtn.addEventListener('click', openAdd);

  var stopBtn = $('stopBtn');
  if (stopBtn) stopBtn.addEventListener('click', MG.stopAll);

  var addForm = $('addForm');
  if (addForm) addForm.addEventListener('submit', submitAdd);
  var cancelAdd = $('cancelAdd');
  if (cancelAdd) cancelAdd.addEventListener('click', closeAdd);
  var addModal = $('addModal');
  if (addModal) addModal.addEventListener('click', function (e) {
    if (e.target.id === 'addModal') closeAdd();
  });

  var confirmOk = $('confirmOk');
  if (confirmOk) confirmOk.addEventListener('click', function () {
    var cb = STATE._confirmCallback;
    closeConfirm();
    if (cb) cb();
  });
  var confirmCancel = $('confirmCancel');
  if (confirmCancel) confirmCancel.addEventListener('click', closeConfirm);
  var confirmModal = $('confirmModal');
  if (confirmModal) confirmModal.addEventListener('click', function (e) {
    if (e.target.id === 'confirmModal') closeConfirm();
  });

  var refreshTeams = $('refreshTeamsBtn');
  if (refreshTeams) refreshTeams.addEventListener('click', function () {
    fetchStats();
    toast('Teams refreshed', 'ok');
  });

  var qEl = $('q');
  if (qEl) qEl.addEventListener('input', function () {
    STATE.teamsFilter = qEl.value;
    renderTeams(STATE.stats.teams || []);
  });

  $$('#logfilters button').forEach(function (b) {
    b.addEventListener('click', function () {
      STATE.logFilter = b.dataset.lf;
      $$('#logfilters button').forEach(function (x) { x.classList.toggle('on', x === b); });
      renderLogs();
    });
  });

  var logSearch = $('logSearch');
  if (logSearch) logSearch.addEventListener('input', function () {
    STATE.logSearch = logSearch.value;
    renderLogs();
  });

  var autoBtn = $('autoBtn');
  if (autoBtn) autoBtn.addEventListener('click', function () {
    STATE.autoScroll = !STATE.autoScroll;
    autoBtn.style.background = STATE.autoScroll ? 'var(--grad-soft)' : '';
    if (STATE.autoScroll) {
      var b = $('termBody');
      if (b) b.scrollTop = b.scrollHeight;
    }
  });

  var clearLogsBtn = $('clearLogsBtn');
  if (clearLogsBtn) clearLogsBtn.addEventListener('click', async function () {
    var r = await apiPostJson('/api/logs/clear', {});
    if (r.error) toast('Clear failed', 'err');
    else {
      STATE.logs = [];
      renderLogs();
      toast('Logs cleared', 'ok');
    }
  });

  var saveBtn = $('saveSettingsBtn');
  if (saveBtn) saveBtn.addEventListener('click', saveSettings);
  var resetBtn = $('resetSettingsBtn');
  if (resetBtn) resetBtn.addEventListener('click', resetSettings);

  var clearHistBtn = $('clearHistoryBtn');
  if (clearHistBtn) clearHistBtn.addEventListener('click', function () {
    confirmDialog('Clear History?', 'Match history will be permanently deleted.', async function () {
      var r = await apiPostJson('/api/history/clear', {});
      if (r.error) toast('Clear failed: ' + r.error, 'err');
      else toast('History cleared', 'ok');
    });
  });

  // Theme dots
  $$('.tdot').forEach(function (d) {
    d.addEventListener('click', function () {
      setTheme(d.dataset.theme);
      $$('.tdot').forEach(function (x) { x.classList.toggle('on', x === d); });
    });
  });
}

/* ═══════ UPTIME TICKER ═══════ */
function startUptimeTicker() {
  var lastUptime = STATE.stats.uptime || 0;
  var lastAt = Date.now();

  setInterval(function () {
    if (document.hidden) return;
    var now = Date.now();
    var elapsed = Math.floor((now - lastAt) / 1000);
    if (elapsed >= 1) {
      STATE.stats.uptime = lastUptime + elapsed;
      setText('s-uptime', fmtDuration(STATE.stats.uptime));
    }
  }, 1000);

  var origFetch = fetchStats;
  fetchStats = async function () {
    await origFetch();
    lastUptime = STATE.stats.uptime || 0;
    lastAt = Date.now();
  };
}

/* ═══════ BOOT ═══════ */
async function boot() {
  var savedTheme = 'titanium';
  try { savedTheme = localStorage.getItem('mg_theme') || 'titanium'; } catch (e) {}
  setTheme(savedTheme);
  $$('.tdot').forEach(function (d) { d.classList.toggle('on', d.dataset.theme === savedTheme); });

  var savedMode = 'dark';
  try { savedMode = localStorage.getItem('mg_mode') || 'dark'; } catch (e) {}
  setMode(savedMode);

  initBindings();

  await fetchStats();
  await fetchLogs();
  await loadSettings();

  STATE.polling = setInterval(function () {
    if (document.hidden) return;
    fetchStats();
  }, 3000);

  setInterval(function () {
    if (document.hidden) return;
    if (STATE.currentView === 'term') fetchLogs();
  }, 2000);

  startUptimeTicker();

  setTimeout(function () {
    var loader = $('loader');
    if (loader) {
      loader.classList.add('hidden');
      setTimeout(function () { loader.remove(); }, 700);
    }
  }, 800);

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) {
      fetchStats();
      if (STATE.currentView === 'term') fetchLogs();
    }
  });
}

window.MG = window.MG || {};
window.MG.startMatch = MG.startMatch;
window.MG.stopTeam = MG.stopTeam;
window.MG.joinGuild = MG.joinGuild;
window.MG.stopAll = MG.stopAll;
window.MG.saveInput = MG.saveInput;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}

})();