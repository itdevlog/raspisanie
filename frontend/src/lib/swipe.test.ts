import { describe, it, expect, vi } from 'vitest';
import { swipe } from './swipe';
import { fireSwipe } from '../test-helpers';

/** Fresh host node per test so listeners never leak between cases. */
function host(): HTMLDivElement {
  const node = document.createElement('div');
  document.body.appendChild(node);
  return node;
}

describe('swipe action', () => {
  it('fires onLeft for a left swipe past the default threshold', () => {
    const node = host();
    const onLeft = vi.fn();
    const onRight = vi.fn();
    swipe(node, { onLeft, onRight });

    fireSwipe(node, -60);

    expect(onLeft).toHaveBeenCalledOnce();
    expect(onRight).not.toHaveBeenCalled();
  });

  it('fires onRight for a right swipe past the default threshold', () => {
    const node = host();
    const onLeft = vi.fn();
    const onRight = vi.fn();
    swipe(node, { onLeft, onRight });

    fireSwipe(node, 60);

    expect(onRight).toHaveBeenCalledOnce();
    expect(onLeft).not.toHaveBeenCalled();
  });

  it('ignores a horizontal move below the threshold', () => {
    const node = host();
    const onLeft = vi.fn();
    const onRight = vi.fn();
    swipe(node, { onLeft, onRight });

    fireSwipe(node, -39);
    fireSwipe(node, 39);

    expect(onLeft).not.toHaveBeenCalled();
    expect(onRight).not.toHaveBeenCalled();
  });

  it('honours a custom threshold', () => {
    const node = host();
    const onLeft = vi.fn();
    swipe(node, { onLeft, threshold: 10 });

    fireSwipe(node, -11);

    expect(onLeft).toHaveBeenCalledOnce();
  });

  it('ignores vertical-dominant gestures so scrolling is not hijacked', () => {
    const node = host();
    const onLeft = vi.fn();
    const onRight = vi.fn();
    swipe(node, { onLeft, onRight });

    // Long vertical drag with a small horizontal component.
    fireSwipe(node, -50, 200);
    fireSwipe(node, 50, 200);

    expect(onLeft).not.toHaveBeenCalled();
    expect(onRight).not.toHaveBeenCalled();
  });

  it('accepts a diagonal that is clearly horizontal', () => {
    const node = host();
    const onLeft = vi.fn();
    swipe(node, { onLeft });

    fireSwipe(node, -80, 20);

    expect(onLeft).toHaveBeenCalledOnce();
  });

  it('stops firing after destroy()', () => {
    const node = host();
    const onLeft = vi.fn();
    const action = swipe(node, { onLeft });

    action.destroy();
    fireSwipe(node, -60);

    expect(onLeft).not.toHaveBeenCalled();
  });

  it('swaps callbacks through update()', () => {
    const node = host();
    const first = vi.fn();
    const second = vi.fn();
    const action = swipe(node, { onLeft: first });

    action.update({ onLeft: second });
    fireSwipe(node, -60);

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledOnce();
  });

  it('ignores a touchend without a preceding touchstart', () => {
    const node = host();
    const onLeft = vi.fn();
    swipe(node, { onLeft });

    // Dispatch only the end half of a gesture.
    node.dispatchEvent(new Event('touchend', { bubbles: true }));

    expect(onLeft).not.toHaveBeenCalled();
  });
});
