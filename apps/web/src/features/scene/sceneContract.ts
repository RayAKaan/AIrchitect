export type Vec3 = readonly [number, number, number];
export type Face = readonly number[];

export type SceneMesh = Readonly<{
  elementId: string;
  elementType: string;
  sourceModelHash: string;
  vertices: readonly Vec3[];
  faces: readonly Face[];
  geometryHash: string;
}>;

export type SceneNode = Readonly<{
  id: string;
  elementType: string;
  meshIndex: number;
  sourceModelHash: string;
  geometryHash: string;
}>;

export type SceneBounds = Readonly<{ minimum: Vec3; maximum: Vec3 }>;
export type ModelScene = Readonly<{ modelHash: string; nodes: readonly SceneNode[]; meshes: readonly SceneMesh[]; bounds: SceneBounds }>;

type RawScene = { model_hash?: unknown; nodes?: unknown; meshes?: unknown; bounds?: unknown };

function isVec3(value: unknown): value is Vec3 { return Array.isArray(value) && value.length === 3 && value.every((item) => typeof item === 'number' && Number.isFinite(item)); }
function parseMesh(value: unknown, index: number): SceneMesh {
  if (!value || typeof value !== 'object') throw new Error(`scene mesh ${index} is invalid`);
  const mesh = value as Record<string, unknown>;
  const vertices = mesh.vertices;
  const faces = mesh.faces;
  if (typeof mesh.element_id !== 'string' || typeof mesh.element_type !== 'string' || typeof mesh.source_model_hash !== 'string' || typeof mesh.geometry_hash !== 'string' || !Array.isArray(vertices) || !vertices.every(isVec3) || !Array.isArray(faces) || !faces.every((face) => Array.isArray(face) && face.every((item) => typeof item === 'number' && Number.isInteger(item) && item >= 0))) throw new Error(`scene mesh ${index} is invalid`);
  return Object.freeze({ elementId: mesh.element_id, elementType: mesh.element_type, sourceModelHash: mesh.source_model_hash, vertices, faces, geometryHash: mesh.geometry_hash });
}

export function parseScene(value: unknown): ModelScene {
  if (!value || typeof value !== 'object') throw new Error('scene must be an object');
  const scene = value as RawScene;
  if (typeof scene.model_hash !== 'string' || !scene.model_hash) throw new Error('scene model_hash is required');
  if (!Array.isArray(scene.nodes) || !Array.isArray(scene.meshes)) throw new Error('scene nodes and meshes must be arrays');
  if (!scene.bounds || typeof scene.bounds !== 'object') throw new Error('scene bounds are required');
  const bounds = scene.bounds as Record<string, unknown>;
  if (!isVec3(bounds.minimum) || !isVec3(bounds.maximum)) throw new Error('scene bounds are invalid');
  const meshes = scene.meshes.map(parseMesh);
  const nodes = scene.nodes.map((value, index) => {
    if (!value || typeof value !== 'object') throw new Error(`scene node ${index} is invalid`);
    const node = value as Record<string, unknown>;
    if (typeof node.id !== 'string' || typeof node.element_type !== 'string' || typeof node.mesh_index !== 'number' || !Number.isInteger(node.mesh_index) || node.mesh_index < 0 || node.mesh_index >= meshes.length || typeof node.source_model_hash !== 'string' || typeof node.geometry_hash !== 'string') throw new Error(`scene node ${index} is invalid`);
    return Object.freeze({ id: node.id, elementType: node.element_type, meshIndex: node.mesh_index, sourceModelHash: node.source_model_hash, geometryHash: node.geometry_hash });
  });
  return Object.freeze({ modelHash: scene.model_hash, nodes: Object.freeze(nodes), meshes: Object.freeze(meshes), bounds: Object.freeze({ minimum: bounds.minimum, maximum: bounds.maximum }) });
}
