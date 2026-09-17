/* Mini App «Расписание»: vanilla JS, Telegram WebApp SDK. */
const tg = window.Telegram.WebApp;
tg.ready(); tg.expand();

const $ = (id) => document.getElementById(id);

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const state = {
  schoolId: null, kind: 'class', entity: null,
  date: null,          // dd.mm.yyyy или null = серверная «сегодня»
  today: null,         // серверная «сегодня» dd.mm.yyyy
  weekOffset: 0,       // смещение недели, клампится -2..2
  mode: 'day',         // 'day' | 'week'
  schools: [], entities: [],
  offline: false,      // true, если данные показаны из TTL-кэша
};

// Должно совпадать с API_TTL_MS в service-worker.js
const API_TTL_MS = 12 * 60 * 60 * 1000;

function setOffline(offline) {
  state.offline = offline;
  const el = $('offline-indicator');
  if (el) el.hidden = !offline;
}

// Прямой fallback на кэш, если SW ещё не контролирует страницу
async function cachedApi(path) {
  if (!('caches' in window)) return null;
  try {
    const cached = await caches.match(path);
    if (!cached) return null;
    const cachedAt = Number(cached.headers.get('X-SW-Cached-At') || 0);
    if (!cachedAt || Date.now() - cachedAt > API_TTL_MS) return null;
    return cached;
  } catch (_) { return null; }
}

async function api(path) {
  let r;
  try {
    r = await fetch(path, { headers: { 'X-Telegram-Init-Data': tg.initData || '' } });
  } catch (e) {
    const cached = await cachedApi(path);
    if (cached) { setOffline(true); return cached.json(); }
    throw e;
  }
  if (!r.ok) {
    const body = await r.json().catch(() => ({ detail: 'Ошибка сети' }));
    throw new Error(body.detail || `HTTP ${r.status}`);
  }
  setOffline(r.headers.get('X-SW-From-Cache') === '1');
  return r.json();
}

function fmtDate(d) {
  const x = d instanceof Date ? d : new Date();
  return `${String(x.getDate()).padStart(2, '0')}.${String(x.getMonth() + 1).padStart(2, '0')}.${x.getFullYear()}`;
}

function shiftDate(days) {
  const base = state.date ? parseDate(state.date)
    : state.today ? parseDate(state.today) : new Date();
  base.setDate(base.getDate() + days);
  state.date = fmtDate(base);
  render();
}

function shiftWeek(delta) {
  state.weekOffset = Math.max(-2, Math.min(2, state.weekOffset + delta));
  render();
}

function parseDate(s) {
  const [d, m, y] = s.split('.').map(Number);
  return new Date(y, m - 1, d);
}

async function init() {
  try {
    // /api/me не кэшируется, поэтому офлайн-инициализация не должна падать из-за него
    const [schools, me] = await Promise.all([api('/api/schools'), api('/api/me').catch(() => ({}))]);
    state.schools = schools.schools;
    state.today = schools.today || null;
    state.date = state.today;
    const sel = $('school-select');
    sel.innerHTML = schools.schools.map(s => `<option value="${escapeHtml(s.id)}">${escapeHtml(s.name)}</option>`).join('');
    if (me.school_id && schools.schools.some(s => s.id === me.school_id)) sel.value = me.school_id;
    state.schoolId = sel.value;
    if (me.class_name) { state.entity = me.class_name; $('search-input').value = me.class_name; }
    sel.onchange = () => { state.schoolId = sel.value; state.entity = null; loadEntities(); render(); };
    await loadEntities();
    render();
  } catch (e) { showError(e.message); }
}

async function loadEntities() {
  const kindPath = { class: 'classes', teacher: 'teachers', room: 'rooms' }[state.kind];
  const body = await api(`/api/${state.schoolId}/${kindPath}`);
  state.entities = body[{ class: 'classes', teacher: 'teachers', room: 'rooms' }[state.kind]];
  $('entity-list').innerHTML = state.entities.map(e => `<option value="${escapeHtml(e)}">`).join('');
}

function setKind(kind) {
  state.kind = kind; state.entity = null; $('search-input').value = '';
  ['tab-class', 'tab-teacher', 'tab-room'].forEach(id => $(id).classList.remove('active'));
  $(`tab-${kind}`).classList.add('active');
  loadEntities().then(render).catch(e => showError(e.message));
}

function lessonHtml(l) {
  const items = l.items.map(i =>
    `${escapeHtml(i.subject)}${i.class_name ? ` (${escapeHtml(i.class_name)})` : ''} — ${escapeHtml(i.teacher || '')} · ${escapeHtml(i.room || '')}`).join('; ');
  const badge = l.is_cancelled ? '<span class="badge">❌ отменено</span>'
    : l.has_exchange ? '<span class="badge">🔄 замена</span>' : '';
  return `<div class="lesson${l.is_cancelled ? ' cancelled' : ''}">
    <span class="time">${escapeHtml(l.num)}. ${escapeHtml(l.start)}–${escapeHtml(l.end)}</span>${badge}<br>${items || '—'}</div>`;
}

function dayHtml(day) {
  if (day.vacation) return `<div class="hint">🏖️ Каникулы/праздник</div>`;
  if (day.weekend) return `<div class="hint">Выходной</div>`;
  if (!day.lessons.length) return `<div class="hint">📭 Занятий нет</div>`;
  return day.lessons.map(lessonHtml).join('');
}

async function render() {
  const container = $('schedule-container');
  const free = $('free-rooms-result');
  free.hidden = true; container.hidden = false;
  $('date-label').textContent = state.date || state.today || '';
  if (!state.entity) {
    container.innerHTML = `<div class="hint">Выберите ${state.kind === 'class' ? 'класс' : state.kind === 'teacher' ? 'преподавателя' : 'кабинет'} выше</div>`;
    return;
  }
  $('loading').hidden = false;
  try {
    if (state.mode === 'day') {
      const q = state.date ? `?date=${state.date}` : '';
      const day = await api(`/api/${state.schoolId}/schedule/${state.kind}/${encodeURIComponent(state.entity)}${q}`);
      container.innerHTML = `<div class="day-title">${escapeHtml(day.day_name)}, ${escapeHtml(day.date)}</div>` + dayHtml(day);
    } else {
      const body = await api(`/api/${state.schoolId}/schedule/${state.kind}/${encodeURIComponent(state.entity)}/week?offset=${state.weekOffset}`);
      const first = body.days.length ? body.days[0].date : '';
      $('date-label').textContent = first ? `нед. ${first}` : '';
      container.innerHTML = body.days.map(d =>
        `<div class="day-title">${escapeHtml(d.day_name)}, ${escapeHtml(d.date)}</div>` + dayHtml(d)).join('<hr>');
    }
  } catch (e) { container.innerHTML = `<div class="hint">⚠️ ${escapeHtml(e.message)}</div>`; }
  finally { $('loading').hidden = true; }
}

async function showFreeRooms() {
  const container = $('schedule-container');
  $('free-rooms-result').hidden = false;
  container.hidden = true;
  const el = $('free-rooms-result');
  const lesson = Number($('free-room-lesson').value) || 1;
  try {
    const q = `lesson=${lesson}${state.date ? `&date=${state.date}` : ''}`;
    const body = await api(`/api/${state.schoolId}/free-rooms?${q}`);
    el.innerHTML = `<div class="day-title">Свободные кабинеты, урок ${escapeHtml(lesson)}</div>` +
      (body.free_rooms.length ? body.free_rooms.map(escapeHtml).join(' · ') : 'Все заняты');
  } catch (e) { el.innerHTML = `<div class="hint">⚠️ ${escapeHtml(e.message)}</div>`; }
}

function showError(msg) { $('schedule-container').innerHTML = `<div class="hint">⚠️ ${escapeHtml(msg)}</div>`; }

$('tab-class').onclick = () => setKind('class');
$('tab-teacher').onclick = () => setKind('teacher');
$('tab-room').onclick = () => setKind('room');
$('free-rooms-btn').onclick = () => showFreeRooms();
$('date-prev').onclick = () => state.mode === 'week' ? shiftWeek(-1) : shiftDate(-1);
$('date-next').onclick = () => state.mode === 'week' ? shiftWeek(1) : shiftDate(1);
$('mode-day').onclick = () => { state.mode = 'day'; $('mode-day').classList.add('active'); $('mode-week').classList.remove('active'); render(); };
$('mode-week').onclick = () => { state.mode = 'week'; $('mode-week').classList.add('active'); $('mode-day').classList.remove('active'); render(); };
$('search-input').oninput = (e) => { state.entity = e.target.value || null; clearTimeout(state._t); state._t = setTimeout(render, 400); };

// Индикатор офлайна: показываем при потере сети, скрываем при восстановлении
window.addEventListener('offline', () => setOffline(true));
window.addEventListener('online', () => setOffline(false));
if (navigator.onLine === false) setOffline(true);

init();
