<script lang="ts">
  // Per-favorite «Сейчас» summary: `/now` for one saved entity with a
  // tomorrow fallback. When today has neither a current nor a next lesson
  // (day over, weekend), the widget repeats the request for the next day and
  // shows it under a «Завтра» badge. Presentation lives in NowWidget.
  import { createAsync } from '../lib/async.svelte';
  import { addDays } from '../lib/dates';
  import type { NowResponse, ScheduleKind } from '../lib/api/types';
  import type { ScheduleApiClient } from '../lib/api/client';
  import NowWidget from './NowWidget.svelte';

  interface Props {
    client: ScheduleApiClient;
    schoolId: string;
    kind: ScheduleKind;
    name: string;
    /** Server-provided today, `DD.MM.YYYY`. */
    today: string;
  }
  let { client, schoolId, kind, name, today }: Props = $props();

  /** «Завтра» while showing the fallback day, `null` otherwise. */
  let note = $state<string | null>(null);

  const nowResource = createAsync<NowResponse>(async () => {
    note = null;
    const response = await client.getNow(schoolId, kind, name, today);
    if (response.current !== null || response.next !== null) {
      return response;
    }
    const tomorrow = addDays(today, 1);
    if (!tomorrow) {
      return response;
    }
    note = 'Завтра';
    return client.getNow(schoolId, kind, name, tomorrow);
  });

  const nowKey = $derived(`${schoolId}|${kind}|${name}|${today}`);

  $effect(() => {
    void nowKey;
    void nowResource.load();
  });
</script>

<NowWidget data={nowResource.data} status={nowResource.status} error={nowResource.error} {note} />
