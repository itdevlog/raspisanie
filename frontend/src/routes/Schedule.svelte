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
    createAsync,
    shareSchedule,
    buildShareUrl,
    enablePush,
    disablePush,
    getPermission,
    supportsServiceWorker,
    offlineState,
    connectivityEnv,
    watchConnectivity,
    watchServiceWorkerCache,
    type ConnectivityEnv,
    type DaySchedule,
    type PushResult,
    type ScheduleApiClient,
    type ScheduleKind,
    type SelectionStore,
    type TodayStore,
    type WeekScheduleResponse,
  } from '../lib';
  import EntityPicker from '../components/EntityPicker.svelte';
  import OpenInTelegram from '../components/OpenInTelegram.svelte';
  import { untrack } from 'svelte';
  import PeriodTabs, { type Period } from '../components/PeriodTabs.svelte';
  import DayView from '../components/DayView.svelte';
  import WeekView from '../components/WeekView.svelte';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    /** Date pinned by a share link (`DD.MM.YYYY`), or null to use server today. */
    pinnedDate?: string | null;
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
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    pinnedDate = null,
    origin = typeof window === 'undefined' ? '' : window.location.origin,
    navigatorLike = undefined,
    connectivity = typeof window === 'undefined' ? undefined : connectivityEnv(),
    pushEnable = enablePush,
    pushDisable = disablePush,
    pushInitiallyOn = false,
    pushSupported = undefined,
  }: Props = $props();

  let period = $state<Period>('today');
  const weekOffset = $state(0);
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

  $effect(() => {
    shareDate = pinnedDate;
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

  // Names for the active kind within the selected school.
  const namesResource = createAsync<string[]>(async () => {
    const schoolId = selection.schoolId;
    if (!schoolId) {
      return [];
    }
    if (selection.kind === 'class') {
      return (await client.getClasses(schoolId)).classes;
    }
    if (selection.kind === 'teacher') {
      return (await client.getTeachers(schoolId)).teachers;
    }
    return (await client.getRooms(schoolId)).rooms;
  });

  // Day payload for today/tomorrow; unused for the week period. A date pinned by
  // a share link (`?date=`) takes precedence over the server's today.
  const dayResource = createAsync<DaySchedule>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      throw new Error('Выберите расписание');
    }
    const date = shareDate ?? (period === 'tomorrow' ? today.tomorrow : today.today);
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

  const kindNamesKey = $derived(`${selection.schoolId ?? ''}|${selection.kind}`);
  const bodyKey = $derived(
    `${selection.schoolId ?? ''}|${selection.kind}|${selection.name ?? ''}|${period}|${weekOffset}|${shareDate ?? ''}`,
  );

  // Reload the name list whenever the school/kind changes.
  $effect(() => {
    // Reading the key here registers the reactive dependency; `void` keeps the
    // statement an expression without changing behavior.
    void kindNamesKey;
    void namesResource.load();
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
    if (period === 'week') {
      void weekResource.load();
    } else if (shareDate || today.isLoaded) {
      void dayResource.load();
    }
  });

  function handleKindChange(kind: ScheduleKind) {
    selection.selectKind(kind);
  }

  function handleNameChange(name: string) {
    selection.selectEntity(selection.kind, name);
  }

  /** Switching period tabs drops a pinned share date and uses server today. */
  function handlePeriodChange(next: Period) {
    shareDate = null;
    period = next;
  }

  /** Share the currently open entity for the displayed date (W16-identical URL). */
  async function handleShare() {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      return;
    }
    const date = shareDate ?? (period === 'tomorrow' ? today.tomorrow : today.today) ?? null;
    const url = buildShareUrl(origin, schoolId, selection.kind, name, date);
    const result = await shareSchedule(url, { title: 'Расписание', text: name }, navigatorLike);
    if (result.ok) {
      shareNotice = result.method === 'share' ? null : 'Ссылка скопирована';
    } else {
      shareNotice = result.error ?? 'Не удалось поделиться';
    }
  }

  const bodyStatus = $derived(period === 'week' ? weekResource.status : dayResource.status);
  const bodyError = $derived(period === 'week' ? weekResource.error : dayResource.error);
  const hasEntity = $derived(selection.name !== null);

  // W24: «Открыть в Telegram» target — the currently shown entity/date.
  const telegramTarget = $derived({
    school: selection.schoolId ?? '',
    kind: selection.kind,
    name: selection.name ?? '',
    date: shareDate ?? (period === 'tomorrow' ? today.tomorrow : today.today) ?? null,
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
    const date = shareDate ?? (period === 'tomorrow' ? today.tomorrow : today.today) ?? null;
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
  <h2>Расписание</h2>

  {#if !selection.schoolId}
    <StateNotice title="Школа не выбрана" detail="Сначала выберите школу на главной." />
  {:else}
    <EntityPicker
      kind={selection.kind}
      name={selection.name}
      names={namesResource.data ?? []}
      disabled={namesResource.isLoading}
      onKindChange={handleKindChange}
      onNameChange={handleNameChange}
    />

    {#if namesResource.status === 'error'}
      <StateNotice
        tone="error"
        title="Не удалось загрузить список"
        detail={namesResource.error ?? ''}
      />
    {/if}

    {#if offline}
      <p class="offline" data-tone={offline.tone} role="status">
        <strong>{offline.title}</strong>
        <span class="offline-detail">{offline.detail}</span>
      </p>
    {/if}

    <PeriodTabs value={period} onChange={handlePeriodChange} />

    {#if shareDate}
      <p class="pinned" role="status">Расписание на {shareDate}</p>
    {/if}

    {#if !hasEntity}
      <StateNotice
        tone="muted"
        title="Выберите расписание"
        detail="Укажите класс, учителя или кабинет."
      />
    {:else if bodyStatus === 'error'}
      <StateNotice tone="error" title="Ошибка загрузки" detail={bodyError ?? ''} />
    {:else if bodyStatus === 'loading' || bodyStatus === 'idle'}
      <p role="status">Загрузка…</p>
    {:else if period === 'week'}
      {#if weekResource.data && weekResource.data.days.length > 0}
        <WeekView week={weekResource.data} kind={selection.kind} />
      {:else}
        <StateNotice title="Занятий нет" detail="Расписание на неделю пустое." />
      {/if}
    {:else if dayResource.data}
      <DayView day={dayResource.data} kind={selection.kind} />
    {/if}

    {#if hasEntity}
      <button type="button" class="share" onclick={handleShare}>Поделиться</button>
      <OpenInTelegram target={telegramTarget} />
      {#if shareNotice}
        <p class="share-notice" role="status">{shareNotice}</p>
      {/if}
      {#if canUsePush && selection.kind === 'class'}
        <button
          type="button"
          class="push"
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

  h2 {
    font-size: 1.25rem;
    margin: 0 0 0.75rem;
  }

  .pinned {
    margin: 0 0 0.5rem;
    font-size: 0.9rem;
    opacity: 0.8;
  }

  .share {
    margin-top: 0.75rem;
    padding: 0.5rem 0.9rem;
    border-radius: 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    background: transparent;
    color: inherit;
    cursor: pointer;
    font-size: 1rem;
  }

  .share-notice {
    margin: 0.35rem 0 0;
    font-size: 0.85rem;
    opacity: 0.75;
  }

  .offline {
    margin: 0.5rem 0;
    padding: 0.5rem 0.75rem;
    border-radius: 0.5rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    font-size: 0.9rem;
  }

  .offline[data-tone='offline'] {
    color: #b00020;
  }

  .offline-detail {
    display: block;
    margin-top: 0.15rem;
    opacity: 0.8;
  }

  .push {
    margin-top: 0.75rem;
    margin-left: 0.5rem;
    padding: 0.5rem 0.9rem;
    border-radius: 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    background: transparent;
    color: inherit;
    cursor: pointer;
    font-size: 1rem;
  }

  .push:disabled {
    opacity: 0.6;
    cursor: default;
  }

  [role='status'] {
    opacity: 0.7;
  }
</style>
