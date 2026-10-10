import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';
import { registerServiceWorker, settings } from './lib';

const target = document.getElementById('app');
if (!target) {
  throw new Error('Не найден контейнер приложения #app');
}

// Apply the persisted skin/accent/font before the first paint.
settings.apply();

const app = mount(App, { target });

// W23: register the PWA service worker (offline cache + push). Guarded for
// browsers without service-worker support and best-effort: a registration
// failure (insecure context, HTTP) must not break the app.
registerServiceWorker()?.catch(() => {
  // Offline cache/push simply stay unavailable; the app works online.
});

export default app;
