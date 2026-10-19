export type RendererMode = '3d' | 'plan' | 'section' | 'elevation' | 'axonometric';

export type RendererAdapter = {
  setMode(mode: RendererMode): void;
  select(entityIds: string[]): void;
  resize(): void;
  dispose(): void;
};
