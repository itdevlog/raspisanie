<script lang="ts">
  // Landing screen (initial view) — the original Nikasoft home.
  //
  //   * quick school-number buttons (the school switcher — the selected
  //     school's name and «Обновлено» live in the app header);
  //   * the selected school's city, when known;
  //   * large section buttons «Классы» / «Учителя» / «Кабинеты» (→ per-kind
  //     list); the «Школьный сайт» link lives in the app header (Task 4);
  //   * favorites of ALL kinds as cards: a tappable header (star + name + kind,
  //     × removes) over a per-favorite «Сейчас» summary.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    favorites as defaultFavorites,
    createAsync,
    KIND_LABELS,
    type Favorite,
    type FavoritesStore,
    type ScheduleApiClient,
    type ScheduleKind,
    type School,
    type SchoolsResponse,
    type SelectionStore,
    type TodayStore,
  } from '../lib';
  import FavoriteSummary from '../components/FavoriteSummary.svelte';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    favorites?: FavoritesStore;
    /** Open the per-kind list screen for `kind`. */
    onOpenList?: (kind: ScheduleKind) => void;
    /** Open a specific entity: select it and jump to its schedule. */
    onOpenEntity?: (kind: ScheduleKind, name: string) => void;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    favorites = defaultFavorites,
    onOpenList,
    onOpenEntity,
  }: Props = $props();

  const schoolsResource = createAsync<SchoolsResponse>(async () => {
    const response = await client.getSchools();
    // Adopt the server's today in the same round-trip.
    today.adopt(response.today);
    return response;
  });

  $effect(() => {
    void schoolsResource.load();
  });

  function handleSchoolChange(schoolId: string) {
    selection.selectSchool(schoolId);
  }

  /**
   * Short label for a school's quick-select button: the first run of digits in
   * the name («МАОУ СОШ №16» → `16`), falling back to the id suffix
   * (`school_16` → `16`) when the name carries no number.
   */
  function schoolNumber(school: School): string {
    const fromName = school.name.match(/\d+/);
    if (fromName) {
      return fromName[0];
    }
    const fromId = school.id.match(/(\d+)$/);
    return fromId ? fromId[1] : school.id;
  }

  /** One quick-select button per school, in the order the API returns them. */
  const schoolChoices = $derived(
    (schoolsResource.data?.schools ?? []).map((school) => ({
      id: school.id,
      name: school.name,
      label: schoolNumber(school),
    })),
  );

  const selectedSchool = $derived(
    schoolsResource.data?.schools.find((school) => school.id === selection.schoolId) ?? null,
  );

  // Favorites of every kind for the selected school (insertion order).
  const favoriteItems = $derived(
    selection.schoolId ? favorites.list(selection.schoolId) : ([] as Favorite[]),
  );

  function removeFavorite(kind: ScheduleKind, name: string) {
    if (selection.schoolId) {
      favorites.remove(selection.schoolId, kind, name);
    }
  }
</script>

<section class="home">
  {#if schoolsResource.status === 'error'}
    <StateNotice tone="error" title="Ошибка загрузки школ" detail={schoolsResource.error ?? ''} />
  {:else if schoolsResource.status === 'loading' || schoolsResource.status === 'idle'}
    <p role="status">Загрузка…</p>
  {:else if schoolsResource.data}
    {#if schoolChoices.length > 0}
      <nav class="school-quick" aria-label="Быстрый выбор школы">
        {#each schoolChoices as choice (choice.id)}
          <button
            type="button"
            class="school-number nika-btn nika-btn-light"
            class:is-active={choice.id === selection.schoolId}
            aria-pressed={choice.id === selection.schoolId}
            title={choice.name}
            onclick={() => handleSchoolChange(choice.id)}
          >
            {choice.label}
          </button>
        {/each}
      </nav>
    {/if}

    {#if selectedSchool?.city}
      <p class="school-city">{selectedSchool.city}</p>
    {/if}

    {#if !selection.schoolId}
      <StateNotice tone="muted" title="Выберите школу" detail="Затем выберите нужный раздел." />
    {:else}
      {#if favoriteItems.length > 0}
        <section class="favorites" aria-labelledby="favorites-heading">
          <h3 id="favorites-heading">Избранное</h3>
          <ul class="favorite-list">
            {#each favoriteItems as favorite (favorite.kind + '|' + favorite.name)}
              <li class="favorite-card">
                <div class="favorite-header">
                  <button
                    type="button"
                    class="favorite-open nika-btn nika-btn-light"
                    aria-label={`Открыть расписание: ${favorite.name}`}
                    onclick={() => onOpenEntity?.(favorite.kind, favorite.name)}
                  >
                    <span class="star" aria-hidden="true">★</span>
                    <span class="favorite-name">{favorite.name}</span>
                    <span class="favorite-kind">{KIND_LABELS[favorite.kind]}</span>
                  </button>
                  <button
                    type="button"
                    class="favorite-remove"
                    aria-label={`Удалить из избранного: ${favorite.name}`}
                    onclick={() => removeFavorite(favorite.kind, favorite.name)}
                  >
                    ×
                  </button>
                </div>
                <FavoriteSummary
                  {client}
                  schoolId={favorite.schoolId}
                  kind={favorite.kind}
                  name={favorite.name}
                  today={today.today}
                />
              </li>
            {/each}
          </ul>
        </section>
      {/if}

      <nav class="sections" aria-label="Разделы">
        <button
          type="button"
          class="section-btn nika-btn nika-btn-blue"
          data-section="class"
          onclick={() => onOpenList?.('class')}
        >
          Классы
        </button>
        <button
          type="button"
          class="section-btn nika-btn nika-btn-blue"
          data-section="teacher"
          onclick={() => onOpenList?.('teacher')}
        >
          Учителя
        </button>
        <button
          type="button"
          class="section-btn nika-btn nika-btn-blue"
          data-section="room"
          onclick={() => onOpenList?.('room')}
        >
          Кабинеты
        </button>
      </nav>
    {/if}
  {/if}
</section>

<style>
  .home {
    text-align: left;
  }

  /* Quick school-number buttons: compact pills that wrap on narrow screens. */
  .school-quick {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: 0 0 var(--space-5);
  }

  .school-number {
    min-width: 44px;
    padding: var(--space-2) var(--space-3);
    font-size: var(--text-base);
  }

  /* The active school is a single solid accent fill (no gradient/gloss), so it
     reads the same across every skin. Inactive buttons stay light. */
  .school-number.is-active {
    background: var(--color-accent);
    background-image: none;
    border-color: var(--color-accent);
    color: var(--color-accent-contrast);
    text-shadow: none;
  }

  .school-city {
    margin: 0 0 var(--space-5);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  h3 {
    font-size: var(--text-lg);
    margin: 0 0 var(--space-3);
  }

  .favorites {
    margin-bottom: var(--space-5);
  }

  /* Favorites: cards — a tappable header over a per-favorite «Сейчас» summary. */
  .favorite-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-3);
  }

  .favorite-card {
    border: 1px solid var(--color-border);
    border-radius: var(--nika-radius);
    background: var(--color-surface);
    box-shadow: var(--nika-shadow);
    padding: var(--space-3);
  }

  .favorite-header {
    display: flex;
    align-items: stretch;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
  }

  .favorite-open {
    flex: 1;
    justify-content: flex-start;
    text-align: left;
  }

  .star {
    color: var(--nika-btn-yellow-bg);
    font-size: var(--text-lg);
    line-height: 1;
    text-shadow: 0 1px 0 rgba(0, 0, 0, 0.15);
  }

  .favorite-name {
    flex: 1;
  }

  .favorite-kind {
    font-size: var(--text-xs);
    color: var(--color-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .favorite-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 44px;
    min-height: 44px;
    padding: 0 var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--nika-radius);
    background: var(--color-surface);
    color: var(--color-cancel);
    font-size: var(--text-lg);
    line-height: 1;
    cursor: pointer;
    box-shadow: var(--nika-shadow);
  }

  .favorite-remove:hover {
    background: var(--color-cancel-soft);
  }

  /* Home menu: «Классы» and «Учителя» sit side by side (spec §2); «Кабинеты»
     spans both columns on its own row. Stays within the 40rem layout width. */
  /* Three quick sections share one row; they stay within the 40rem layout. */
  .sections {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-3);
    margin: var(--space-4) 0;
  }

  .section-btn {
    font-size: var(--text-lg);
    padding: var(--space-4) var(--space-2);
  }

  [role='status'] {
    color: var(--color-muted);
  }
</style>
