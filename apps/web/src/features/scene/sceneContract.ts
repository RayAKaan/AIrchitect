export type Vec3 = readonly [number, number, number];

export type SceneNode = Readonly<{
  id: string;
  elementType: string;
  meshIndex: number;
  sourceModelHash: string;
  geometryHash: string;
}>;

export type SceneBounds = Readonly<{
  minimum: Vec3;
  maximum: Vec3;
}>;

export type ModelScene = Readonly<{
  modelHash: string;
  nodes: readonly SceneNode[];
  meshes: readonly unknown[];
  bounds: SceneBounds;
}>;

export type SystemPreviewScene = Readonly<{
  model_hash: string;
  nodes: readonly SceneNode[];
  bounds: SceneBounds;
}>;

function isVec3(value: unknown): value is Vec3 {
  return Array.isArray(value) && value.length === 3 && value.every((item) => typeof item === 'number' && Number.isFinite(item));
}

export function parseScene(value: unknown): ModelScene {
  if (!value || typeof value !== 'object') throw new Error('scene must be an object');
  const scene = value as Partial<SystemPreviewScene> & { meshes?: unknown };
  if (typeof scene.model_hash !== 'string' || scene.model_hash.length === 0) throw new Error('scene model_hash is required');
  if (!Array.isArray(scene.nodes)) throw new Error('scene nodes must be an array');
  if (!scene.bounds || !isVec3(scene.bounds.minimum) || !isVec3(scene.bounds.maximum)) throw new Error('scene bounds are invalid');

  const nodes = scene.nodes.map((node, index) => {
    if (!node || typeof node !== 'object') throw new Error(`scene node ${index} is invalid`);
    const candidate = node as Partial<SceneNode>;
    if (typeof candidate.id !== 'string' || typeof candidate.elementType !== 'string' || typeof candidate.meshIndex !== 'number' || !Number.isInteger(candidate.meshIndex) || candidate.meshIndex < 0 || typeof candidate.sourceModelHash !== 'string' || typeof candidate.geometryHash !== 'string') {
      throw new Error(`scene node ${index} is invalid`);
    }
    return Object.freeze({
      id: candidate.id,
      elementType: candidate.elementType,
      meshIndex: candidate.meshIndex,
      sourceModelHash: candidate.sourceModelHash,
      geometryHash: candidate.geometryHash,
    });
  });

  return Object.freeze({
    modelHash: scene.model_hash,
    nodes: Object.freeze(nodes),
    meshes: Object.freeze(Array.isArray(scene.meshes) ? scene.meshes : []),
    bounds: Object.freeze({ minimum: scene.bounds.minimum, maximum: scene.bounds.maximum }),
  });
}
