/**
 * O jsdom não implementa ResizeObserver, DOMMatrixReadOnly nem dimensões de layout,
 * de que o React Flow depende. Mocks baseados na documentação de testes do React Flow.
 */
class ResizeObserverMock {
  private readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element) {
    const element = target as HTMLElement;
    const width = element.offsetWidth;
    const height = element.offsetHeight;
    const entry = {
      target,
      contentRect: { x: 0, y: 0, top: 0, left: 0, right: width, bottom: height, width, height },
      borderBoxSize: [{ inlineSize: width, blockSize: height }],
      contentBoxSize: [{ inlineSize: width, blockSize: height }],
    } as unknown as ResizeObserverEntry;
    this.callback([entry], this as unknown as ResizeObserver);
  }

  unobserve() {}

  disconnect() {}
}

class DOMMatrixReadOnlyMock {
  m22: number;

  constructor(transform?: string) {
    const scale = transform?.match(/scale\(([\d.]+)\)/)?.[1];
    this.m22 = scale !== undefined ? Number(scale) : 1;
  }
}

export function mockReactFlow() {
  globalThis.ResizeObserver ??= ResizeObserverMock as unknown as typeof ResizeObserver;
  globalThis.DOMMatrixReadOnly ??= DOMMatrixReadOnlyMock as unknown as typeof DOMMatrixReadOnly;

  Object.defineProperties(HTMLElement.prototype, {
    offsetHeight: {
      configurable: true,
      get(this: HTMLElement) {
        return parseFloat(this.style.height) || 1;
      },
    },
    offsetWidth: {
      configurable: true,
      get(this: HTMLElement) {
        return parseFloat(this.style.width) || 1;
      },
    },
  });

  (SVGElement.prototype as unknown as { getBBox: () => DOMRect }).getBBox = () =>
    ({ x: 0, y: 0, width: 0, height: 0 }) as DOMRect;
}
