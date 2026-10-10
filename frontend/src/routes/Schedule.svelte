<script lang="ts">
  // W20 Schedule screen.
  // Layout:
  //   * period tabs: Сегодня / Завтра / Неделя (dates derived from the server
  //     today, never the browser clock);
  //   * entity tabs + name picker: класс / учитель / кабинет;
  //   * body: a {@link DayView} or {@link WeekView}.
  //
  // All data comes from the injected client; the today store is the source of
  // "сегодня"/"завтра". Search and free-rooms screens are W21.
  //
  // W22 adds:
  //   * a `pinnedDate` prop: when a share link carries `?date=`, the day view
  //     opens that date instead of the server's today;
  //   * a «Поделиться» action building the same URL scheme as W16.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    favorites as defaultFavorites,
    createAsync,
    parseRuDate,
    addDays,
    dayHeading,
    shareSchedule,
    buildShareUrl,
    enablePush,
    disablePush,
    getPermission,
    supportsServiceWorker,
    offlineState,
    connectivityEnv,
    shiftMonth,
    swipe,
    watchConnectivity,
    watchServiceWorkerCache,
    type CalendarResponse,
    type ConnectivityEnv,
    type DaySchedule,
    type FavoritesStore,
    type PushResult,
    type ScheduleApiClient,
    type SelectionStore,
    type TodayStore,
    type WeekScheduleResponse,
  } from '../lib';
  import FavoriteButton from '../components/FavoriteButton.svelte';
  import OpenInTelegram from '../components/OpenInTelegram.svelte';
  import { untrack } from 'svelte';
  import PeriodTabs, { type Period } from '../components/PeriodTabs.svelte';
  import DayView from '../components/DayView.svelte';
  import WeekView from '../components/WeekView.svelte';
  import CalendarView from '../components/CalendarView.svelte';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    favorites?: FavoritesStore;
    /** Date pinned by a share link (`DD.MM.YYYY`), or null to use server today. */
    pinnedDate?: string | null;
    /** Raised when a calendar day is opened; the shell can sync the URL. */
    onOpenDay?: (date: string) => void;
    /** Return to the list view (the kind tab bar's landing screen). */
    onBack?: () => void;
    /** Browser origin used when building the share link; defaults to `location`. */
    origin?: string;
    /** Injectable navigator for tests; defaults to the global `navigator`. */
    navigatorLike?: Parameters<typeof shareSchedule>[2];
    /** Injectable connectivity env for tests; defaults to `window`. */
    connectivity?: ConnectivityEnv;
    /** Injectable push opt-in (tests); defaults to the real {@link enablePush}. */
    pushEnable?: typeof enablePush;
    /** Injectable push opt-out (tests); defaults to the real {@link disablePush}. */
    pushDisable?: typeof disablePush;
    /** Test seam: start with notifications already enabled. */
    pushInitiallyOn?: boolean;
    /** Test seam: force whether Web Push UI is available. */
    pushSupported?: boolean;
    /**
     * W41 fix: `STRIKEOUT_FREE_LSN` for the selected school, threaded from the
     * shell (`/api/schools`). Default `true` keeps the strike-through behavior.
     */
    strikeoutFreeLsn?: boolean;
    /** Show lesson numbers/times (user setting; forwarded to the day/week views). */
    showLessonTime?: boolean;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    favorites = defaultFavorites,
    pinnedDate = null,
    onOpenDay,
    onBack,
    origin = typeof window === 'undefined' ? '' : window.location.origin,
    navigatorLike = undefined,
    connectivity = typeof window === 'undefined' ? undefined : connectivityEnv(),
    pushEnable = enablePush,
    pushDisable = disablePush,
    pushInitiallyOn = false,
    pushSupported = undefined,
    strikeoutFreeLsn = true,
    showLessonTime = true,
  }: Props = $props();

  let period = $state<Period>('today');
  // Day cursor: offset from the baseline (server today, or a pinned share date).
  // «Сегодня» = 0, «Завтра» = 1; swiping left/right moves it. Clamped at 0 so
  // the day view never walks into the past before the baseline.
  let dayOffset = $state(0);
  // W38 fix: `weekOffset` is mutable now that prev/next controls exist; the API
  // accepts `offset` in -2..2.
  let weekOffset = $state(0);
  const WEEK_OFFSET_MIN = -2;
  const WEEK_OFFSET_MAX = 2;
  // W41 fix (minor): a calendar day outside a teaching period would make
  // `get_day` raise `PeriodNotFoundError` (422). Track it so we can show a
  // graceful notice instead of a load error.
  let noPeriodDate = $state<string | null>(null);
  // Month cursor for the calendar tab; initialised from the *server* today (never
  // the browser clock) and then moved by the prev/next controls.
  let monthCursor = $state<{ year: number; month: number } | null>(null);
  // A share link may pin a date; switching period tabs clears it and falls back
  // to the server today. Synced from the prop via an effect.
  let shareDate = $state<string | null>(null);
  let shareNotice = $state<string | null>(null);

  // W23: push opt-in state + offline connectivity.
  // `untrack` keeps the test-only `pushInitiallyOn` seam from being captured as
  // a reactive dependency (it is only read once, at init).
  let pushState = $state<'idle' | 'busy' | 'on'>(untrack(() => pushInitiallyOn) ? 'on' : 'idle');
  let pushNotice = $state<string | null>(null);
  let online = $state(true);
  let fromCache = $state(false);

  // The day cursor's baseline: a pinned share date wins, otherwise server today.
  const dayBase = $derived(shareDate ?? today.today);
  // The date actually shown in day mode, derived from the baseline + offset.
  const dayDate = $derived(dayBase ? addDays(dayBase, dayOffset) : null);
  const canGoPrevDay = $derived(dayOffset > 0);

  // Seed the day cursor from a pinned share date. A new pin (deep link) resets
  // the cursor to that date; swiping does not touch `pinnedDate`, so it is not
  // reset by the user's own navigation.
  $effect(() => {
    shareDate = pinnedDate;
    dayOffset = 0;
  });

  // Track connectivity for the offline indicator; fires once with the current
  // value and again on every online/offline event.
  $effect(() => {
    if (!connectivity) {
      return;
    }
    return watchConnectivity(connectivity, (value) => {
      online = value;
    });
  });

  // Track the SW's "served from TTL cache" signal (offline/stale schedule).
  $effect(() => {
    const container =
      typeof navigator === 'undefined' ? undefined : navigator.serviceWorker;
    return watchServiceWorkerCache(container, (value) => {
      fromCache = value;
    });
  });

  // Day payload for the current day cursor; unused for week/month. A date
  // pinned by a share link (`?date=`) seeds the cursor, otherwise the server's
  // today is the baseline.
  const dayResource = createAsync<DaySchedule>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      throw new Error('Выберите расписание');
    }
    const date = dayDate;
    if (!date) {
      throw new Error('Не удалось определить дату');
    }
    return client.getDay(schoolId, selection.kind, name, date);
  });

  // Week payload (Mon–Fri).
  const weekResource = createAsync<WeekScheduleResponse>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      throw new Error('Выберите расписание');
    }
    return client.getWeek(schoolId, selection.kind, name, weekOffset);
  });

  // Month-calendar payload for the active month cursor.
  const calendarResource = createAsync<CalendarResponse>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    const cursor = monthCursor;
    if (!schoolId || !name || !cursor) {
      throw new Error('Выберите расписание');
    }
    return client.getCalendar(schoolId, selection.kind, name, cursor.year, cursor.month);
  });

  const bodyKey = $derived(
    `${selection.schoolId ?? ''}|${selection.kind}|${selection.name ?? ''}|${period}|${weekOffset}|${dayDate ?? ''}|${
      period === 'month' ? `${monthCursor?.year ?? ''}|${monthCursor?.month ?? ''}` : ''
    }`,
  );

  // Seed the month cursor from the server today exactly once; user navigation
  // afterwards must not be reset by a later reload.
  $effect(() => {
    if (monthCursor === null && today.isLoaded) {
      const parsed = parseRuDate(today.today);
      if (parsed) {
        monthCursor = { year: parsed.year, month: parsed.month };
      }
    }
  });

  // Reload today from the server so "сегодня" is authoritative on entry.
  $effect(() => {
    if (!today.isLoaded) {
      void today.load().catch(() => {
        // Failure is non-fatal: the day effect simply stays idle and the UI
        // shows its loading/error state once a date is available.
      });
    }
  });

  // Load the payload for the current period. Split into two effects so only the
  // relevant resource is touched and the week offset is respected. A pinned
  // share date is standalone data, so it does not wait for the server today.
  $effect(() => {
    void bodyKey;
    if (period === 'month') {
      if (monthCursor) {
        void calendarResource.load();
      }
    } else if (period === 'week') {
      void weekResource.load();
    } else if (!noPeriodDate && dayDate) {
      void dayResource.load();
    }
  });

  // W39: favorite toggle for the shown class/teacher/room.
  const isFavorite = $derived(
    selection.schoolId !== null &&
      selection.name !== null &&
      favorites.has(selection.schoolId, selection.kind, selection.name),
  );

  function handleToggleFavorite() {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (schoolId && name) {
      favorites.toggle(schoolId, selection.kind, name);
    }
  }

  /**
   * Switching period tabs drops a pinned share date and re-bases the day
   * cursor: «Сегодня» → offset 0, «Завтра» → offset 1.
   */
  function handlePeriodChange(next: Period) {
    noPeriodDate = null;
    shareDate = null;
    if (next === 'today') {
      dayOffset = 0;
    } else if (next === 'tomorrow') {
      dayOffset = 1;
    }
    period = next;
  }

  /**
   * Open a calendar day: show its schedule and let the shell sync the URL.
   *
   * W41 fix (minor): a day outside a teaching period (`no_period`) cannot be
   * loaded — `get_day` raises 422. The calendar already carries the flag, so we
   * show a graceful notice instead of routing into a load error.
   */
  function handleSelectDay(date: string) {
    const calendarDay = calendarResource.data?.days.find((day) => day.date === date);
    if (calendarDay?.no_period) {
      noPeriodDate = date;
      shareDate = null;
      dayOffset = 0;
      period = 'today';
      onOpenDay?.(date);
      return;
    }
    noPeriodDate = null;
    shareDate = date;
    dayOffset = 0;
    period = 'today';
    onOpenDay?.(date);
  }

  /** Move the calendar cursor by whole months, rolling the year over. */
  function shiftCalendarMonth(delta: number) {
    if (monthCursor) {
      monthCursor = shiftMonth(monthCursor.year, monthCursor.month, delta);
    }
  }

  /** W38 fix: move the shown week by `delta` (API range -2..2). */
  function shiftWeek(delta: number) {
    const next = weekOffset + delta;
    if (next < WEEK_OFFSET_MIN || next > WEEK_OFFSET_MAX) {
      return;
    }
    weekOffset = next;
  }

  /**
   * Move the day cursor by `delta`. Clamped at 0: the cursor never walks before
   * the baseline (server today, or a pinned share date) — no past days. The
   * «Сегодня»/«Завтра» tabs stay meaningful: offset 0 → today, ≥1 → tomorrow.
   */
  function shiftDay(delta: number) {
    const next = dayOffset + delta;
    if (next < 0) {
      return;
    }
    dayOffset = next;
    period = next === 0 ? 'today' : 'tomorrow';
  }

  const canGoPrevWeek = $derived(weekOffset > WEEK_OFFSET_MIN);
  const canGoNextWeek = $derived(weekOffset < WEEK_OFFSET_MAX);

  /** Share the currently open entity for the displayed date (W16-identical URL). */
  async function handleShare() {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      return;
    }
    const date = dayDate ?? null;
    const url = buildShareUrl(origin, schoolId, selection.kind, name, date);
    const result = await shareSchedule(url, { title: 'Расписание', text: name }, navigatorLike);
    if (result.ok) {
      shareNotice = result.method === 'share' ? null : 'Ссылка скопирована';
    } else {
      shareNotice = result.error ?? 'Не удалось поделиться';
    }
  }

  const bodyStatus = $derived(
    period === 'week'
      ? weekResource.status
      : period === 'month'
        ? calendarResource.status
        : dayResource.status,
  );
  const bodyError = $derived(
    period === 'week'
      ? weekResource.error
      : period === 'month'
        ? calendarResource.error
        : dayResource.error,
  );
  const hasEntity = $derived(selection.name !== null);

  // W24: «Открыть в Telegram» target — the currently shown entity/date.
  const telegramTarget = $derived({
    school: selection.schoolId ?? '',
    kind: selection.kind,
    name: selection.name ?? '',
    date: dayDate ?? null,
  });

  // W23: the offline/cached indicator. `fromCache` is derived from the SW's
  // marker on the last schedule response; the SW is engaged only when the
  // service worker is supported.
  const canUsePush = $derived(
    pushSupported ??
      (supportsServiceWorker() && (typeof window === 'undefined' || 'Notification' in window)),
  );
  const isPushOn = $derived(pushState === 'on' || getPermission() === 'granted');
  const offline = $derived(offlineState({ online, fromCache }));

  /** Enable notifications for the selected class (MVP = class-only). */
  async function handleEnablePush() {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      return;
    }
    pushState = 'busy';
    pushNotice = null;
    const date = dayDate ?? null;
    const url = buildShareUrl(origin, schoolId, selection.kind, name, date);
    const result: PushResult = await pushEnable({ schoolId, name, kind: 'class', url });
    if (result.ok) {
      pushState = 'on';
    } else {
      pushState = 'idle';
      pushNotice = result.error ?? 'Не удалось включить уведомления';
    }
  }

  async function handleDisablePush() {
    pushState = 'busy';
    pushNotice = null;
    const result = await pushDisable();
    if (result.ok) {
      pushState = 'idle';
      pushNotice = 'Уведомления выключены';
    } else {
      pushState = 'on';
      pushNotice = result.error ?? 'Не удалось выключить уведомления';
    }
  }
</script>

<section class="schedule">
  <button type="button" class="back nika-btn nika-btn-light" aria-label="К списку" onclick={() => onBack?.()}>
    ← к списку
  </button>

  <h2>Расписание{selection.name ? ` ${selection.name}` : ''}</h2>

  {#if !selection.schoolId}
    <StateNotice title="Школа не выбрана" detail="Сначала выберите школу в списке." />
  {:else}
    {#if offline}
      <p class="offline" data-tone={offline.tone} role="status">
        <strong>{offline.title}</strong>
        <span class="offline-detail">{offline.detail}</span>
      </p>
    {/if}

    <PeriodTabs value={period} onChange={handlePeriodChange} />

    {#if shareDate}
      <p class="pinned" role="status">Расписание на {dayDate}</p>
    {/if}

    {#if !hasEntity}
      <StateNotice
        tone="muted"
        title="Выберите расписание"
        detail="Укажите класс, учителя или кабинет."
      />
    {:else if noPeriodDate}
      <StateNotice
        tone="muted"
        title="Нет учебного периода"
        detail="Дата {noPeriodDate} вне учебного периода."
      />
    {:else if period === 'week'}
      <!-- The week nav stays mounted while a week loads so the controls remain
           clickable (W38 fix). Swiping the pane moves the week too. -->
      <div
        class="week-pane"
        use:swipe={{ onLeft: () => shiftWeek(1), onRight: () => shiftWeek(-1) }}
      >
        <div class="week-nav">
          <button
            type="button"
            class="nav-arrow nika-btn nika-btn-light"
            aria-label="Предыдущая неделя"
            disabled={!canGoPrevWeek}
            onclick={() => shiftWeek(-1)}
          >
            ‹
          </button>
          <span class="week-label" role="status">
            {weekOffset === 0
              ? 'Текущая неделя'
              : weekOffset > 0
                ? `+${weekOffset} нед.`
                : `${weekOffset} нед.`}
          </span>
          <button
            type="button"
            class="nav-arrow nika-btn nika-btn-light"
            aria-label="Следующая неделя"
            disabled={!canGoNextWeek}
            onclick={() => shiftWeek(1)}
          >
            ›
          </button>
        </div>
        {#if bodyStatus === 'error'}
          <StateNotice tone="error" title="Ошибка загрузки" detail={bodyError ?? ''} />
        {:else if bodyStatus === 'loading' || bodyStatus === 'idle'}
          <p class="loading" role="status">Загрузка…</p>
        {:else if weekResource.data && weekResource.data.days.length > 0}
          <WeekView week={weekResource.data} kind={selection.kind} {strikeoutFreeLsn} {showLessonTime} />
        {:else}
          <StateNotice title="Занятий нет" detail="Расписание на неделю пустое." />
        {/if}
      </div>
    {:else if period === 'month'}
      {#if bodyStatus === 'error'}
        <StateNotice tone="error" title="Ошибка загрузки" detail={bodyError ?? ''} />
      {:else if bodyStatus === 'loading' || bodyStatus === 'idle'}
        <p class="loading" role="status">Загрузка…</p>
      {:else if monthCursor && calendarResource.data}
        <CalendarView
          month={calendarResource.data}
          year={monthCursor.year}
          monthNumber={monthCursor.month}
          today={today.today}
          onSelectDay={handleSelectDay}
          onPrevMonth={() => shiftCalendarMonth(-1)}
          onNextMonth={() => shiftCalendarMonth(1)}
        />
      {/if}
    {:else}
      <!-- Day mode: the cursor pane owns swipe (left → next, right → previous)
           and keeps prev/next controls for pointer/keyboard users. -->
      <div class="day-pane" use:swipe={{ onLeft: () => shiftDay(1), onRight: () => shiftDay(-1) }}>
        {#if dayDate}
          <div class="day-nav">
            <button
              type="button"
              class="nav-arrow nika-btn nika-btn-light"
              aria-label="Предыдущий день"
              disabled={!canGoPrevDay}
              onclick={() => shiftDay(-1)}
            >
              ‹
            </button>
            <span class="day-label" role="status">{dayHeading(dayDate)}</span>
            <button
              type="button"
              class="nav-arrow nika-btn nika-btn-light"
              aria-label="Следующий день"
              onclick={() => shiftDay(1)}
            >
              ›
            </button>
          </div>
        {/if}
        {#if bodyStatus === 'error'}
          <StateNotice tone="error" title="Ошибка загрузки" detail={bodyError ?? ''} />
        {:else if bodyStatus === 'loading' || bodyStatus === 'idle'}
          <p class="loading" role="status">Загрузка…</p>
        {:else if dayResource.data}
          <DayView day={dayResource.data} kind={selection.kind} {strikeoutFreeLsn} {showLessonTime} />
        {/if}
      </div>
    {/if}

    {#if hasEntity}
      <FavoriteButton
        active={isFavorite}
        onToggle={handleToggleFavorite}
        label={selection.name ?? undefined}
      />
      <button type="button" class="share nika-btn nika-btn-blue" onclick={handleShare}>
        Поделиться
      </button>
      <OpenInTelegram target={telegramTarget} />
      {#if shareNotice}
        <p class="share-notice" role="status">{shareNotice}</p>
      {/if}
      {#if canUsePush && selection.kind === 'class'}
        <button
          type="button"
          class="push nika-btn nika-btn-light"
          disabled={pushState === 'busy'}
          onclick={isPushOn ? handleDisablePush : handleEnablePush}
        >
          {isPushOn ? 'Выключить уведомления' : 'Включить уведомления'}
        </button>
        {#if pushNotice}
          <p class="share-notice" role="status">{pushNotice}</p>
        {/if}
      {/if}
    {/if}
  {/if}
</section>

<style>
  .schedule {
    text-align: left;
  }

  .back {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
  }

  h2 {
    font-size: var(--text-xl);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    margin: 0 0 var(--space-4);
  }

  .pinned {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  /* Swipe panes: allow vertical page scroll, own the horizontal axis. */
  .week-pane,
  .day-pane {
    touch-action: pan-y;
  }

  .week-nav,
  .day-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }

  /* Round arrow buttons around the day/week cursor. */
  .nav-arrow {
    min-width: 44px;
    padding: 0;
    border-radius: 50%;
    font-size: var(--text-xl);
    line-height: 1;
  }

  .nav-arrow:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .week-label {
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .day-label {
    font-size: var(--text-base);
    font-weight: bold;
    color: var(--color-text);
  }

  .loading {
    margin: var(--space-4) 0;
    text-align: center;
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .share {
    margin-top: var(--space-4);
  }

  .share-notice {
    margin: var(--space-2) 0 0;
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .offline {
    margin: var(--space-3) 0;
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-md);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    font-size: var(--text-sm);
  }

  .offline[data-tone='offline'] {
    color: var(--color-cancel);
    border-color: color-mix(in srgb, var(--color-cancel) 35%, var(--color-border));
    border-left: 3px solid var(--color-cancel);
  }

  .offline-detail {
    display: block;
    margin-top: var(--space-1);
    opacity: 0.8;
  }

  .push {
    margin-top: var(--space-4);
    margin-left: var(--space-2);
  }

  .push:disabled {
    opacity: 0.6;
    cursor: default;
  }

  [role='status'] {
    color: var(--color-muted);
  }
</style>
