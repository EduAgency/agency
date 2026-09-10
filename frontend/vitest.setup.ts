import "@testing-library/jest-dom/vitest";

/**
 * jsdom implements neither of these, and both are load-bearing in this app:
 * `matchMedia` gates every reduced-motion check, and `requestAnimationFrame`
 * is how the form engine defers focus onto its error summary.
 */
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
}

if (!window.requestAnimationFrame) {
  window.requestAnimationFrame = ((callback: FrameRequestCallback) =>
    setTimeout(() => callback(0), 0) as unknown as number) as typeof window.requestAnimationFrame;
}

// jsdom has no layout engine, so this is a no-op that stops the form engine
// throwing when it brings an invalid field into view.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
