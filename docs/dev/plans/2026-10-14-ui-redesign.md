# Переработка интерфейса — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Упростить навигацию и экраны расписания: явные кнопки «К списку»/«На главную», сводка по каждому избранному на главной, авто-избранное открытого элемента, двухшаговый выбор класса и удаление вида «Компактный».

**Architecture:** Точечные изменения существующих Svelte 5 компонентов и сторов без новых зависимостей. Одна новая чистая утилита (`lib/class-list.ts`) и один новый презентационный компонент (`FavoriteSummary.svelte`), который переиспользует `NowWidget`. Изменение типа `ScheduleView` (удаление `compact`) затрагивает нескольких потребителей сразу, поэтому выполняется одной атомарной задачей.

**Tech Stack:** Svelte 5 (runes), Vite, TypeScript, Vitest, @testing-library/svelte, jsdom.

**Spec:** `docs/dev/specs/2026-10-14-ui-redesign-design.md`

## Global Constraints

- Mobile-first: контейнер `max-width: 40rem`; интерактив ≥44px по высоте.
- Весь пользовательский текст — на русском, как в текущих компонентах.
- Никаких новых runtime-зависимостей.
- Сохранять существующие скины (`classic`/`minimal`/`dark`/`contrast`/`youth`) и классы кнопок `nika-btn*`.
- Переиспользовать хелперы из `frontend/src/test-helpers.ts` в тестах.
- Следовать паттернам Svelte 5 (`$state`/`$derived`/`$effect`), уже принятым в проекте.
- Все команды запускаются из каталога `frontend/`. Целевые прогоны: `npx vitest run <путь>`; финальный гейт — `npm run verify`.

## Review Focus

- Имя класса без буквы (`«5»`) или нецифровое/пустое имя не должно ломать выбор параллели: парсится в параллель с пустой буквой и всё равно открывается.
- Сводки на главной для избранных кабинетов и учителей должны запрашивать `/now` с правильным `kind`, а не хардкодить `class`; при пустом tomorrow — показывать «Уроков нет».
- Ошибка `/now` (или отсутствие данных) для карточки избранного должна давать состояние ошибки/пустоты, а не вечную загрузку.
- Авто-избранное по deep-link не должно зацикливаться или дублировать записи.
- Недельный вид сохраняет заголовки дней (`DayView` `showHeading` по умолчанию `true`); дублирующий заголовок подавляется только в дневном режиме.

---

### Task 1: Хелпер разбора имён классов

**Files:**
- Create: `frontend/src/lib/class-list.ts`
- Test: `frontend/src/lib/class-list.test.ts`
- Modify: `frontend/src/lib/index.ts`

**Interfaces:**
- Consumes: ничего.
- Produces:
  - `parseClassName(name: string): { grade: string; letter: string } | null`
  - `groupClassesByGrade(names: string[]): Array<{ grade: string; classes: string[] }>`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/lib/class-list.test.ts
import { describe, expect, it } from 'vitest';
import { groupClassesByGrade, parseClassName } from './class-list';

describe('parseClassName', () => {
  it('splits a grade and a Cyrillic letter', () => {
    expect(parseClassName('5А')).toEqual({ grade: '5', letter: 'А' });
    expect(parseClassName('5 А')).toEqual({ grade: '5', letter: 'А' });
    expect(parseClassName('10Б')).toEqual({ grade: '10', letter: 'Б' });
  });
  it('keeps a grade without a letter', () => {
    expect(parseClassName('5')).toEqual({ grade: '5', letter: '' });
  });
  it('returns null for non-class names', () => {
    expect(parseClassName('Спортзал')).toBeNull();
    expect(parseClassName('')).toBeNull();
  });
});

describe('groupClassesByGrade', () => {
  it('groups by grade in numeric order and drops non-class names', () => {
    expect(
      groupClassesByGrade(['10Б', '5А', '5Б', 'Спортзал', '2В']),
    ).toEqual([
      { grade: '2', classes: ['2В'] },
      { grade: '5', classes: ['5А', '5Б'] },
      { grade: '10', classes: ['10Б'] },
    ]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/class-list.test.ts`
Expected: FAIL — cannot resolve `./class-list`.

- [ ] **Step 3: Implement `frontend/src/lib/class-list.ts`**

Match `/^(\d+)\s*(.*)$/`: `grade` = цифры, `letter` = остаток `trim()` (может быть `''`); иначе `null`. `groupClassesByGrade` пропускает `null`, собирает в `Map`, сортирует параллели численно по возрастанию.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/class-list.test.ts`
Expected: PASS.

- [ ] **Step 5: Export from the barrel**

Добавить в `frontend/src/lib/index.ts` строку `export * from './class-list';` рядом с другими `export *`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/class-list.ts frontend/src/lib/class-list.test.ts frontend/src/lib/index.ts
git commit -m "feat(frontend): helper to group class names by grade"
```

---

### Task 2: Удалить вид «Компактный» (атомарно)

Один связный деливерабл: тип `ScheduleView` теряет `compact`, поэтому стор и все его потребители меняются вместе.

**Files:**
- Modify: `frontend/src/lib/stores/settings.svelte.ts`
- Modify: `frontend/src/routes/Settings.svelte`
- Modify: `frontend/src/routes/Variants.svelte`
- Modify: `frontend/src/routes/Schedule.svelte` (только default пропа)
- Modify: `frontend/src/components/DayView.svelte`
- Modify: `frontend/src/components/WeekView.svelte`
- Modify: `frontend/src/components/schedule/ScheduleBody.svelte`
- Delete: `frontend/src/components/schedule/ScheduleCompact.svelte`
- Modify: `frontend/src/lib/stores/settings.test.ts`
- Modify: `frontend/src/routes/Settings.test.ts`
- Modify: `frontend/src/routes/Variants.test.ts`
- Modify: `frontend/src/App.test.ts`
- Modify: `frontend/src/components/DayView.test.ts`
- Modify: `frontend/src/components/WeekView.test.ts`
- Modify: `frontend/src/routes/Schedule.test.ts`

**Interfaces:**
- Produces: `ScheduleView` = `'cards' | 'table' | 'timeline' | 'nownext'`; `DEFAULT_SETTINGS.scheduleView = 'cards'`; свойство `DayView`/`ScheduleBody` `showHeading?: boolean` (default `true`) — используется в Task 3.
- Consumers: `SCHEDULE_VIEW_LABELS` больше не содержит `compact`.

- [ ] **Step 1: Update the settings store**

В `settings.svelte.ts`: удалить `'compact'` из типа `ScheduleView`, из `SCHEDULE_VIEW_LABELS`, из массива `SCHEDULE_VIEWS`; в `DEFAULT_SETTINGS` поставить `scheduleView: 'cards'`.

- [ ] **Step 2: Update the settings store test**

В `settings.test.ts`: заменить ожидания `toBe('compact')` → `toBe('cards')` (строки 33 и 128); тест про «неизвестное значение» (`'kanban'`) продолжает откатываться к `DEFAULT_SETTINGS` (теперь `'cards'`) без правок логики.

- [ ] **Step 3: Run the store test**

Run: `npx vitest run src/lib/stores/settings.test.ts`
Expected: PASS.

- [ ] **Step 4: Update the Settings screen**

В `Settings.svelte`: убрать `'compact'` из локального массива `SCHEDULE_VIEWS`; обновить текст `p.hint` (убрать упоминание «Компактного», например: «Так выглядит расписание дня. Другой формат — из сравнения вариантов ниже.»). В `Settings.test.ts`: удалить проверку радио «Компактный»; ожидание `settings.scheduleView` → `'cards'`; остальные проверки оформить как «четыре вида расписания».

- [ ] **Step 5: Update the Variants screen**

В `Variants.svelte`: удалить секцию `data-variant="compact"`; перенумеровать секции в «1. Карточки», «2. Таблица», «3. Таймлайн», «4. Сейчас / далее»; текст «в пяти оформлениях» → «в четырёх». В `Variants.test.ts`: ожидать 4 элемента `[data-variant]` и новые подписи; в `App.test.ts` заменить ожидание `'1. Компактный (текущий)'` (≈строка 117) на `'1. Карточки'`.

- [ ] **Step 6: Update the rendering defaults and body**

- `DayView.svelte`: `view` default → `'cards'`; добавить проп `showHeading` (default `true`) и пробросить в `ScheduleBody`; `now` без изменений.
- `WeekView.svelte`: `view` default → `'cards'`; `perDayView` запасной вариант для `'nownext'` → `'cards'`.
- `Schedule.svelte`: default пропа `scheduleView` → `'cards'`.
- `ScheduleBody.svelte`: добавить проп `showHeading` (default `true`); выводить `<h3>{dayTitle(day)}</h3>` только при `chrome && showHeading`; удалить `<p class="period">` и `<p class="shift">`; удалить ветку `{:else}ScheduleCompact`; убрать из импортов `periodLabel`, `shiftLabel`, `ScheduleCompact` (значение `shift` в теле больше не считается).
- Удалить файл `frontend/src/components/schedule/ScheduleCompact.svelte`.

- [ ] **Step 7: Update the affected rendering tests**

- `DayView.test.ts`: рендер без пропа `view` теперь даёт «Карточки» — заменить compact-специфичные ожидания: `'.lesson'` → `'.card'`, `'каб. 101'` → чип `'101'`; удалить блоки про период (`'На период: …'`, `'.period'`) и про смену в теле (`'Смена 6'`, `'.shift'`); состояния каникул/выходного/нет периода/«Занятий нет» сохранить; free-lesson проверки перевести на `'.card'`.
- `WeekView.test.ts`: `'.lesson'` → `'.card'`; ожидания заголовков дней (`'Понедельник, 05.10.2026'`, `'Выходной'`, `'Нет учебного периода'`) оставить — `showHeading` по умолчанию `true`.
- `Schedule.test.ts`: тест про «Таблица вместо компактного списка» (≈786) оставить с проверкой `.cards === null`; тест фолбэка недельного вида (≈857) переименовать в «переходит к «Карточкам»…» и ожидать наличие `.cards`.

- [ ] **Step 8: Run the full suite**

Run: `npm run verify`
Expected: PASS (check + lint + test + build). Здесь и далее `npm run verify` — финальный гейт; промежуточные задачи гоняют только свои файлы.

- [ ] **Step 9: Commit**

```bash
git add -A frontend/src
git commit -m "feat(frontend): remove the compact schedule view"
```

---

### Task 3: Навигация на экране расписания

**Files:**
- Modify: `frontend/src/routes/Schedule.svelte`
- Modify: `frontend/src/routes/Schedule.test.ts`

**Interfaces:**
- Consumes: `showHeading` из Task 2; `shiftLabel`, `isSecondShift` из `lib/schedule-view.ts`.
- Produces: проп `onHome?: () => void` у `Schedule` (используется в Task 4).

- [ ] **Step 1: Write the failing test**

```ts
// в Schedule.test.ts
it('renders both «К списку» and «На главную» controls wired to handlers', async () => {
  const onBack = vi.fn();
  const onHome = vi.fn();
  render(Schedule, { props: { ...baseProps(), onBack, onHome } });
  await fireEvent.click(await screen.findByRole('button', { name: 'К списку' }));
  await fireEvent.click(screen.getByRole('button', { name: 'На главную' }));
  expect(onBack).toHaveBeenCalledTimes(1);
  expect(onHome).toHaveBeenCalledTimes(1);
});
```

И тест бейджа смены:

```ts
it('shows a shift badge only for the second shift', async () => {
  // day с shift: 2 → в заголовке есть 'Смена 2'; day с shift: 1 → нет
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/routes/Schedule.test.ts`
Expected: FAIL — нет кнопки «На главную».

- [ ] **Step 3: Implement in `Schedule.svelte`**

Добавить проп `onHome?: () => void`. Рядом с back-кнопкой «К списку» добавить `<button class="back" aria-label="На главную" onclick={() => onHome?.()}>← на главную</button>`. В `<h2>` добавить бейдж: `{#if dayResource.data && isSecondShift(dayResource.data.shift)}<span class="shift-badge">{shiftLabel(dayResource.data.shift)}</span>{/if}`. В дневной ветке передать `<DayView … showHeading={false} />`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/routes/Schedule.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/Schedule.svelte frontend/src/routes/Schedule.test.ts
git commit -m "feat(frontend): add «На главную» control and shift badge to schedule"
```

---

### Task 4: Шапка — кнопка «Школьный сайт» и выравнивание шестерёнки

**Files:**
- Modify: `frontend/src/App.svelte`
- Modify: `frontend/src/App.test.ts`

**Interfaces:**
- Consumes: `selectedSchool` (уже есть в `App`), `goHome`; `onHome` из Task 3.
- Produces: проброс `onHome={goHome}` в `<Schedule>`.

- [ ] **Step 1: Write the failing test**

```ts
it('shows a school-site link in the header when the school has a homepage', async () => {
  // school с homepage_url и features.homepage !== false
  const { findByRole } = render(App, { props: baseProps() });
  const link = await findByRole('link', { name: 'Школьный сайт' });
  expect(link.getAttribute('href')).toContain('http');
});
it('hides the school-site link when there is no homepage', async () => { /* школы без homepage_url */ });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/App.test.ts`
Expected: FAIL — в шапке нет ссылки.

- [ ] **Step 3: Implement in `App.svelte`**

Добавить `showHomepageLink = $derived(!!selectedSchool?.homepage_url && (selectedSchool?.features?.homepage ?? true))`. В `div.header-row` перед кнопкой настроек вставить `{#if showHomepageLink}<a class="site-link" href={selectedSchool.homepage_url}>Школьный сайт</a>{/if}`. В стилях: `.header-row` уже `align-items: center`; задать `.site-link` и `.gear` одинаковую высоту (min-height 44px, `flex: none`, `display: inline-flex; align-items: center`). Передать в `<Schedule>` проп `onHome={goHome}`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/App.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.svelte frontend/src/App.test.ts
git commit -m "feat(frontend): school-site link in header and aligned gear"
```

---

### Task 5: Авто-избранное открытого элемента

**Files:**
- Modify: `frontend/src/App.svelte`
- Modify: `frontend/src/App.test.ts`

**Interfaces:**
- Consumes: `router.route` / существующий `currentRoute`; `favorites.add` (идемпотентно); `goHome` не нужен.
- Produces: ничего для других задач.

- [ ] **Step 1: Write the failing test**

```ts
it('adds an opened entity to favorites automatically', async () => {
  const favorites = makeFavorites();
  const { router, env } = makeRouter(makeFakeEnv('/s/gym1/class/5%D0%90'));
  render(App, { props: { ...baseProps(), favorites, router } });
  await waitFor(() => expect(favorites.has('gym1', 'class', '5А')).toBe(true));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/App.test.ts`
Expected: FAIL — элемент не добавлен.

- [ ] **Step 3: Implement in `App.svelte`**

Добавить один `$effect`, который читает текущий маршрут и, если `view === 'schedule' && route.school && route.name`, вызывает `favorites.add(route.school, route.kind, route.name)` (идемпотентно; `untrack` не нужен — лишний прогон после записи стабилен).

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/App.test.ts`
Expected: PASS (в т.ч. не появляется бесконечный цикл).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.svelte frontend/src/App.test.ts
git commit -m "feat(frontend): auto-add opened entity to favorites"
```

---

### Task 6: Компонент сводки избранного

**Files:**
- Create: `frontend/src/components/FavoriteSummary.svelte`
- Test: `frontend/src/components/FavoriteSummary.test.ts`
- Modify: `frontend/src/components/NowWidget.svelte`
- Modify: `frontend/src/components/NowWidget.test.ts`

**Interfaces:**
- Consumes: `client.getNow(schoolId, kind, name, date)`, `addDays` из `lib/dates.ts`, паттерн `createAsync`/`NowResponse` из `Home.svelte` и `NowWidget.svelte`.
- Produces:
  - `NowWidget` получает проп `note?: string | null` (показывается бейджем рядом с заголовком; используется для «Завтра»).
  - `FavoriteSummary` props: `{ client, schoolId, kind, name, today }`.

- [ ] **Step 1: Write the failing test**

```ts
// FavoriteSummary.test.ts
it('renders today\'s lesson when /now has one', async () => {
  const client = makeClient({ getNow: vi.fn().mockResolvedValue({
    server_time: '2026-10-05T10:00:00+03:00',
    current: { num: 3, time: '10:00–10:45', subject: 'Физика', room: '101', in_minutes: 20 },
    next: null,
  }) });
  render(FavoriteSummary, { props: { client, schoolId: 'gym1', kind: 'room', name: '101', today: '05.10.2026' } });
  expect(await screen.findByText('Идёт урок')).toBeTruthy();
  expect(client.getNow).toHaveBeenCalledWith('gym1', 'room', '101', '05.10.2026');
});
it('falls back to tomorrow with a «Завтра» note when today is empty', async () => {
  const client = makeClient({ getNow: vi.fn()
    .mockResolvedValueOnce({ server_time: '2026-10-05T18:00:00+03:00', current: null, next: null })
    .mockResolvedValueOnce({ server_time: '2026-10-05T18:00:00+03:00', current: { num: 1, time: '08:00–08:45', subject: 'Математика', room: '12', in_minutes: 0 }, next: null }) });
  render(FavoriteSummary, { props: { client, schoolId: 'gym1', kind: 'class', name: '5А', today: '05.10.2026' } });
  expect(await screen.findByText('Завтра')).toBeTruthy();
  expect(client.getNow).toHaveBeenLastCalledWith('gym1', 'class', '5А', '06.10.2026');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/FavoriteSummary.test.ts`
Expected: FAIL — компонент не найден.

- [ ] **Step 3: Add the `note` prop to `NowWidget`**

`NowWidget.svelte`: добавить `note?: string | null` (default `null`); при наличии вывести бейдж (`<span class="note">{note}</span>`) рядом с заголовком «Сейчас». В `NowWidget.test.ts` добавить проверку, что `note` рендерится и по умолчанию отсутствует.

- [ ] **Step 4: Implement `FavoriteSummary.svelte`**

Пропсы `{ client, schoolId, kind, name, today }`. `createAsync<NowResponse>`, ключ `schoolId|kind|name|today`. Загрузка: сначала `getNow(schoolId, kind, name, today)`; если `current` и `next` оба `null` — повторный запрос `getNow(schoolId, kind, name, addDays(today, 1))` и рендер `NowWidget` с `note="Завтра"`. Иначе — `NowWidget` без note. Данные/статус/ошибку передавать в `NowWidget` (error → его штатное состояние ошибки).

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/components/FavoriteSummary.test.ts src/components/NowWidget.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/FavoriteSummary.svelte frontend/src/components/FavoriteSummary.test.ts frontend/src/components/NowWidget.svelte frontend/src/components/NowWidget.test.ts
git commit -m "feat(frontend): per-favorite now summary with tomorrow fallback"
```

---

### Task 7: Главная — разделы и карточки избранного

**Files:**
- Modify: `frontend/src/routes/Home.svelte`
- Modify: `frontend/src/routes/Home.test.ts`

**Interfaces:**
- Consumes: `FavoriteSummary` из Task 6; `KIND_PLURAL_LABELS`/`KIND_LABELS` из `lib/schedule-view.ts`.
- Produces: ничего для других задач.

- [ ] **Step 1: Write the failing tests**

```ts
it('offers Классы, Учителя and Кабинеты sections', async () => {
  render(Home, { props: baseProps() });
  expect(await screen.findByRole('button', { name: 'Классы' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Учителя' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Кабинеты' })).toBeTruthy();
});
it('no longer renders the school-site link (moved to the header)', async () => {
  render(Home, { props: baseProps() });
  await screen.findByRole('button', { name: 'Классы' });
  expect(screen.queryByRole('link', { name: 'Школьный сайт' })).toBeNull();
});
it('renders a now summary card for each favorite', async () => {
  // два избранных (class + room), getNow мокается → две сводки
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/routes/Home.test.ts`
Expected: FAIL — нет «Кабинеты», есть ссылка «Школьный сайт».

- [ ] **Step 3: Implement in `Home.svelte`**

- В `nav.sections` добавить кнопку `Кабинеты` (`data-section="room"`, `onclick={() => onOpenList('room')}`, класс `nika-btn-blue`).
- Удалить `<a … «Школьный сайт»>` и производную `showHomepageLink`.
- Удалить `savedClass`, `nowResource` и `<NowWidget>`; в секции «Избранное» каждый элемент сделать карточкой: заголовок (`★ {name}` + `KIND_LABELS[kind]` + кнопка удаления `aria-label="Удалить из избранного: {name}"`), ниже `<FavoriteSummary {client} {schoolId} kind={item.kind} name={item.name} {today} />`, тап по заголовку → `onOpenEntity(item.kind, item.name)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/routes/Home.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/Home.svelte frontend/src/routes/Home.test.ts
git commit -m "feat(frontend): home sections and per-favorite summary cards"
```

---

### Task 8: Список — двухшаговый выбор класса и подсветка выбранного

**Files:**
- Modify: `frontend/src/routes/List.svelte`
- Modify: `frontend/src/routes/List.test.ts`

**Interfaces:**
- Consumes: `groupClassesByGrade`/`parseClassName` из Task 1.
- Produces: ничего для других задач.

- [ ] **Step 1: Write the failing tests**

```ts
it('picks a class in two steps: grade, then letter', async () => {
  const onOpenEntity = vi.fn();
  render(List, { props: { ...baseProps(), onOpenEntity } });
  await fireEvent.click(await screen.findByRole('button', { name: '6' }));
  await fireEvent.click(screen.getByRole('button', { name: 'Б' }));
  expect(onOpenEntity).toHaveBeenCalledWith('class', '6Б');
});
it('still lets search filter all classes', async () => {
  render(List, { props: baseProps() });
  await fireEvent.input(await screen.findByRole('searchbox', { name: 'Поиск' }), { target: { value: '6' } });
  expect(screen.getByRole('button', { name: '6Б' })).toBeTruthy();
});
it('highlights the selected entity', async () => {
  const selection = makeSelection();
  selection.selectEntity('class', '5А');
  render(List, { props: { ...baseProps(), selection } });
  await fireEvent.click(await screen.findByRole('button', { name: '5' }));
  expect(screen.getByRole('button', { name: 'А' }).getAttribute('aria-current')).toBe('true');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/routes/List.test.ts`
Expected: FAIL — нет кнопок параллели/букв.

- [ ] **Step 3: Implement in `List.svelte`**

- `let selectedGrade = $state<string | null>(null)`; сбрасывать его вместе с `query` в эффекте по `listKey`.
- `gradeGroups = $derived(kind === 'class' ? groupClassesByGrade(allNames) : [])`.
- Для `kind === 'class'` при пустом `query`: если `selectedGrade === null` — полоска кнопок параллелей (label — `grade`); иначе — заголовок параллели, кнопки букв (`letter || fullName`, `aria-current={selection.name === className}`) и кнопка «Все параллели» для сброса; кнопка буквы → `openEntity(className)`.
- Поиск (`query !== ''`) сохраняет прежний вид: прокручиваемый список строк `filteredNames` (для классов, учителей и кабинетов).
- Подсветка выбранного: для любимого вида — строка/кнопка с `name === selection.name` получает класс `is-selected` и `aria-current="true"` (применимо и к избранному, и к результатам поиска).

- [ ] **Step 4: Update the affected list tests**

`List.test.ts`: тест «одна строка на имя» — клик `'6'` затем `'Б'`; тест «ярлык свободных кабинетов» — убрать ожидание кнопки `'5А'` для класса (проверять только ветку кабинетов); переименовать тест «compact switcher» (речь о переключателе видов), логику не менять.

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/routes/List.test.ts`
Expected: PASS.

- [ ] **Step 6: Run the full gate**

Run: `npm run verify`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/routes/List.svelte frontend/src/routes/List.test.ts
git commit -m "feat(frontend): two-step class picker and selected highlight"
```

---

## Self-review

- **Spec coverage:** шапка (§1) → Task 4; главная (§2) → Tasks 6–7; список (§3) → Tasks 1, 8; расписание (§4) → Tasks 2–3; виды расписания (§5) → Task 2; авто-избранное (§6) → Task 5; тестирование (§7) → тесты в каждой задаче.
- **Отклонение от спеки:** `NowWidget` сохраняется как презентационный компонент, а `FavoriteSummary` добавляется поверх него (в спеке файл назван `NowWidget.svelte → FavoriteSummary.svelte`). Это уменьшает churn без потери поведения; решение отражено в Task 6.
- **Типы/имена:** `parseClassName`/`groupClassesByGrade`, `showHeading`, `note`, `onHome` используются согласованно во всех задачах.
- **Порядок:** Task 2 атомарен по причине общего типа `ScheduleView`; Task 3 зависит от него; Task 7 зависит от Task 6.
