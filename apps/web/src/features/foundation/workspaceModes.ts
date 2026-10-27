export type ProductMode = 'Brief' | 'Site' | 'Explore' | 'Design' | 'Validate' | 'Deliver';

export const PRODUCT_MODES: ReadonlyArray<{ id: ProductMode; label: string; hint: string }> = [
  { id: 'Brief', label: 'Brief', hint: 'Define the project' },
  { id: 'Site', label: 'Site', hint: 'Understand the place' },
  { id: 'Explore', label: 'Explore', hint: 'Generate possibilities' },
  { id: 'Design', label: 'Design', hint: 'Develop the chosen scheme' },
  { id: 'Validate', label: 'Validate', hint: 'Check decisions and impacts' },
  { id: 'Deliver', label: 'Deliver', hint: 'Prepare professional outputs' },
];

export const PRODUCT_MODE_TAB: Record<ProductMode, string> = {
  Brief: 'Brief',
  Site: 'Site',
  Explore: 'S2',
  Design: 'Design',
  Validate: 'Release Validation',
  Deliver: 'CAD/BIM Exports',
};

export function isProductMode(value: string | null | undefined): value is ProductMode {
  return PRODUCT_MODES.some((mode) => mode.id === value);
}

export function storedProductMode(projectId: string, storage: Storage = sessionStorage): ProductMode {
  const value = storage.getItem(`airchitect:mode:${projectId}`);
  return isProductMode(value) ? value : 'Brief';
}

export function productModeEvent(projectId: string, mode: ProductMode): CustomEvent<{ projectId: string; mode: ProductMode; tab: string }> {
  return new CustomEvent('airchitect:product-mode', {
    detail: { projectId, mode, tab: PRODUCT_MODE_TAB[mode] },
  });
}
