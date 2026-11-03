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
  if (typeof mesh.element_id !== 'string' || !mesh.element_id || typeof mesh.element_type !== 'string' || !mesh.element_type || typeof mesh.source_model_hash !== 'string' || !mesh.source_model_hash || typeof mesh.geometry_hash !== 'string' || !mesh.geometry_hash || !Array.isArray(vertices) || vertices.length < 3 || !vertices.every(isVec3) || !Array.isArray(faces) || faces.length === 0 || !faces.every((face) => Array.isArray(face) && face.length >= 3 && face.every((item) => typeof item === 'number' && Number.isInteger(item) && item >= 0 && item < vertices.length))) throw new Error(`scene mesh ${index} is invalid`);
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
    if (typeof node.id !== 'string' || !node.id || typeof node.element_type !== 'string' || typeof node.mesh_index !== 'number' || !Number.isInteger(node.mesh_index) || node.mesh_index < 0 || node.mesh_index >= meshes.length || typeof node.source_model_hash !== 'string' || typeof node.geometry_hash !== 'string') throw new Error(`scene node ${index} is invalid`);
    const mesh = meshes[node.mesh_index];
    if (mesh.elementId !== node.id || mesh.elementType !== node.element_type || mesh.sourceModelHash !== node.source_model_hash || mesh.geometryHash !== node.geometry_hash || node.source_model_hash !== scene.model_hash) throw new Error(`scene node ${index} lineage does not match its mesh and model`);
    return Object.freeze({ id: node.id, elementType: node.element_type, meshIndex: node.mesh_index, sourceModelHash: node.source_model_hash, geometryHash: node.geometry_hash });
  });
  return Object.freeze({ modelHash: scene.model_hash, nodes: Object.freeze(nodes), meshes: Object.freeze(meshes), bounds: Object.freeze({ minimum: bounds.minimum, maximum: bounds.maximum }) });
}


export type SceneView = 'plan' | 'front' | 'side';
export type ProjectedFace = Readonly<{ elementId: string; points: readonly (readonly [number, number])[] }>;
export type SceneProjection = Readonly<{ view: SceneView; bounds: Readonly<{ minimum: readonly [number, number]; maximum: readonly [number, number] }>; faces: readonly ProjectedFace[] }>;

export function projectScene(scene: ModelScene, view: SceneView): SceneProjection {
  const axes: Readonly<Record<SceneView, readonly [number, number]>> = {
    plan: [0, 1],
    front: [0, 2],
    side: [1, 2],
  };
  const [horizontal, vertical] = axes[view];
  const faces: ProjectedFace[] = [];
  const projectedPoints: (readonly [number, number])[] = [];
  for (const node of scene.nodes) {
    const mesh = scene.meshes[node.meshIndex];
    if (!mesh || mesh.geometryHash !== node.geometryHash || mesh.sourceModelHash !== scene.modelHash) {
      throw new Error(`scene node ${node.id} has stale geometry lineage`);
    }
    for (const face of mesh.faces) {
      const points = face.map((index) => {
        const vertex = mesh.vertices[index];
        const point = [vertex[horizontal], vertex[vertical]] as const;
        projectedPoints.push(point);
        return point;
      });
      faces.push(Object.freeze({ elementId: node.id, points: Object.freeze(points) }));
    }
  }
  if (projectedPoints.length === 0) throw new Error('scene has no projectable faces');
  const minimum: [number, number] = [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY];
  const maximum: [number, number] = [Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY];
  for (const point of projectedPoints) {
    for (const axis of [0, 1] as const) {
      minimum[axis] = Math.min(minimum[axis], point[axis]);
      maximum[axis] = Math.max(maximum[axis], point[axis]);
    }
  }
  return Object.freeze({
    view,
    bounds: Object.freeze({ minimum: Object.freeze(minimum), maximum: Object.freeze(maximum) }),
    faces: Object.freeze(faces),
  });
}
