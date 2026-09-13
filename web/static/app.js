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
  date: null,          // ISO-подобная dd.mm.yyyy или null = сегодня
  mode: 'day',         // 'day' | 'week'
  schools: [], entities: [],
};

async function api(path) {
  const r = await fetch(path, { headers: { 'X-Telegram-Init-Data': tg.initData || '' } });
  if (!r.ok) {
    const body = await r.json().catch(() => ({ detail: 'Ошибка сети' }));
    throw new Error(body.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

function fmtDate(d) {
  const x = d instanceof Date ? d : new Date();
  return `${String(x.getDate()).padStart(2, '0')}.${String(x.getMonth() + 1).padStart(2, '0')}.${x.getFullYear()}`;
}

function shiftDate(days) {
  const base = state.date ? parseDate(state.date) : new Date();
  base.setDate(base.getDate() + days);
  state.date = fmtDate(base);
  render();
}

function parseDate(s) {
  const [d, m, y] = s.split('.').map(Number);
  return new Date(y, m - 1, d);
}

async function init() {
  try {
    const [schools, me] = await Promise.all([api('/api/schools'), api('/api/me')]);
    state.schools = schools.schools;
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
  $('date-label').textContent = state.date || fmtDate(new Date());
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
      const off = 0; // неделя — всегда текущая (лимит ±2)
      const body = await api(`/api/${state.schoolId}/schedule/${state.kind}/${encodeURIComponent(state.entity)}/week?offset=${off}`);
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
  const lesson = promptLesson();
  if (!lesson) { el.hidden = true; container.hidden = false; return; }
  try {
    const q = `lesson=${lesson}${state.date ? `&date=${state.date}` : ''}`;
    const body = await api(`/api/${state.schoolId}/free-rooms?${q}`);
    el.innerHTML = `<div class="day-title">Свободные кабинеты, урок ${escapeHtml(lesson)}</div>` +
      (body.free_rooms.length ? body.free_rooms.map(escapeHtml).join(' · ') : 'Все заняты');
  } catch (e) { el.innerHTML = `<div class="hint">⚠️ ${escapeHtml(e.message)}</div>`; }
}

function promptLesson() {
  const n = window.prompt('Номер урока (1-12)', '1');
  return n && Number(n) >= 1 && Number(n) <= 12 ? Number(n) : null;
}

function showError(msg) { $('schedule-container').innerHTML = `<div class="hint">⚠️ ${escapeHtml(msg)}</div>`; }

$('tab-class').onclick = () => setKind('class');
$('tab-teacher').onclick = () => setKind('teacher');
$('tab-room').onclick = () => setKind('room');
$('free-rooms-btn').onclick = () => showFreeRooms();
$('date-prev').onclick = () => shiftDate(-1);
$('date-next').onclick = () => shiftDate(1);
$('mode-day').onclick = () => { state.mode = 'day'; $('mode-day').classList.add('active'); $('mode-week').classList.remove('active'); render(); };
$('mode-week').onclick = () => { state.mode = 'week'; $('mode-week').classList.add('active'); $('mode-day').classList.remove('active'); render(); };
$('search-input').oninput = (e) => { state.entity = e.target.value || null; clearTimeout(state._t); state._t = setTimeout(render, 400); };

init();
