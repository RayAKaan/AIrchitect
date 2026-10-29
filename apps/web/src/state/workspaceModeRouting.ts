import type { ProductMode } from './productWorkspace';

export const MODE_VIEW_TARGETS = {
  Brief: 'brief',
  Site: 'site',
  Explore: 'explore',
  Design: 'design',
  Validate: 'validate',
  Deliver: 'deliver',
} as const satisfies Record<ProductMode, string>;

export type ModeViewTarget = (typeof MODE_VIEW_TARGETS)[ProductMode];

/**
 * Resolve a product mode to its canonical workspace view.
 *
 * This mapping is intentionally exhaustive: adding a product mode requires
 * choosing a view target instead of silently falling back to the Brief view.
 */
export function resolveModeView(mode: ProductMode): ModeViewTarget {
  return MODE_VIEW_TARGETS[mode];
}

export function assertUnreachable(value: never): never {
  throw new Error(`Unhandled workspace view target: ${String(value)}`);
}
