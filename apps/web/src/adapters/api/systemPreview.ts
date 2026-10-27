import type { ApiClient } from './client';
import { parseScene, type ModelScene } from '../../features/scene/sceneContract';

export type RoomRequirement = Readonly<{ room_id: string; name: string; target_area_m2: number; min_area_m2?: number | null; max_area_m2?: number | null; level_index?: number; required?: boolean }>;
export type AdjacencyRequirement = Readonly<{ first_room_id: string; second_room_id: string; relationship: 'adjacent' | 'near' | 'separate'; priority?: number }>;
export type DesignIntentInput = Readonly<{ project_id: string; site_id: string; site_width_m: number; site_depth_m: number; floors?: number; floor_to_floor_m?: number; setback_front_m?: number; setback_rear_m?: number; setback_left_m?: number; setback_right_m?: number; rooms: readonly RoomRequirement[]; adjacencies?: readonly AdjacencyRequirement[] }>;

export type SystemPreview = Readonly<{
  project_id: string;
  model: unknown;
  geometry: readonly unknown[];
  scene: ModelScene;
  cad: unknown;
  engineering: unknown;
  quantities: unknown;
  regulatory: unknown;
  warnings?: readonly string[];
  read_only: true;
}>;

export async function fetchSystemPreview(client: ApiClient, intent: DesignIntentInput): Promise<SystemPreview> {
  const response = await client.request<Record<string, unknown>>(`/projects/${encodeURIComponent(intent.project_id)}/design/system-preview`, {
    method: 'POST',
    body: JSON.stringify(intent),
  });
  if (response.project_id !== intent.project_id || response.read_only !== true) throw new Error('System preview response failed identity/read-only checks');
  return Object.freeze({
    ...(response as Omit<SystemPreview, 'scene'>),
    scene: parseScene(response.scene),
    read_only: true,
  });
}
