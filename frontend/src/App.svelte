<script lang="ts">
  // W18: placeholder app shell only. Real screens/routing/stores arrive in later tasks.
  const title = 'Расписание';
  const status = 'Загрузка…';
</script>

<main>
  <h1>{title}</h1>
  <p aria-live="polite">{status}</p>
</main>

<style>
  main {
    text-align: center;
  }

  h1 {
    font-size: 1.75rem;
    margin: 0 0 0.5rem;
  }

  p {
    margin: 0;
    opacity: 0.7;
  }
</style>
