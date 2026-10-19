export const designTokens = {
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  radii: { sm: 4, md: 8, lg: 12 },
  focusRing: '2px solid currentColor',
} as const;

export type DesignTokens = typeof designTokens;
