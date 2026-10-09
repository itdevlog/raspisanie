// frontend/src/lib/swipe.ts
//
// Dependency-free horizontal swipe detection for touch devices, packaged as a
// Svelte action so screens can attach it declaratively (`use:swipe={{ ... }}`).
//
// The action listens for `touchstart`/`touchend`, measures the net horizontal
// displacement and fires the matching callback once the gesture clears
// `threshold` (default 40px). A gesture is only treated as a horizontal swipe
// when |dx| dominates |dy| by `DOMINANCE` (1.5×), so vertical scrolling never
// triggers navigation.
//
// Touch events (rather than `pointer*`) are enough for the target devices and
// stay trivially testable with synthetic events; no pointer fallback is needed.

/** Callbacks + tuning for {@link swipe}. */
export interface SwipeOptions {
  /** Fired on a left swipe (`dx < -threshold`): "go to the next item". */
  onLeft?: () => void;
  /** Fired on a right swipe (`dx > threshold`): "go to the previous item". */
  onRight?: () => void;
  /** Minimum horizontal travel in px; defaults to 40. */
  threshold?: number;
}

/** Return shape of the {@link swipe} Svelte action. */
export interface SwipeAction {
  update: (options: SwipeOptions) => void;
  destroy: () => void;
}

const DEFAULT_THRESHOLD = 40;
/** Horizontal travel must beat vertical travel by this factor. */
const DOMINANCE = 1.5;

/**
 * Svelte action: call `onLeft`/`onRight` when the node receives a horizontal
 * touch swipe. Vertical-dominant gestures (scrolls) are ignored.
 */
export function swipe(node: HTMLElement, options: SwipeOptions = {}): SwipeAction {
  let current: SwipeOptions = { threshold: DEFAULT_THRESHOLD, ...options };
  let startX = 0;
  let startY = 0;
  let tracking = false;

  function handleStart(event: TouchEvent): void {
    const touch = event.touches[0];
    if (!touch) {
      return;
    }
    startX = touch.clientX;
    startY = touch.clientY;
    tracking = true;
  }

  function handleEnd(event: TouchEvent): void {
    if (!tracking) {
      return;
    }
    tracking = false;
    const touch = event.changedTouches[0];
    if (!touch) {
      return;
    }
    const dx = touch.clientX - startX;
    const dy = touch.clientY - startY;
    // Ignore vertical-dominant gestures so page scrolling is never hijacked.
    if (Math.abs(dx) <= Math.abs(dy) * DOMINANCE) {
      return;
    }
    const threshold = current.threshold ?? DEFAULT_THRESHOLD;
    if (dx < -threshold) {
      current.onLeft?.();
    } else if (dx > threshold) {
      current.onRight?.();
    }
  }

  node.addEventListener('touchstart', handleStart, { passive: true });
  node.addEventListener('touchend', handleEnd, { passive: true });

  return {
    update(next: SwipeOptions) {
      current = { threshold: DEFAULT_THRESHOLD, ...next };
    },
    destroy() {
      node.removeEventListener('touchstart', handleStart);
      node.removeEventListener('touchend', handleEnd);
    },
  };
}
