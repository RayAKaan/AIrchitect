export type MapAdapter = {
  mount(container: HTMLElement): void;
  resize(): void;
  destroy(): void;
};

export type MapLayerVisibility = Record<string, boolean>;
