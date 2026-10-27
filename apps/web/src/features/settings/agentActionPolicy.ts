export type AgentActionClass = 'read' | 'propose' | 'commit';

export type AgentAction = {
  name: string;
  class: AgentActionClass;
  description: string;
};

export const AIRCHITECT_AGENT_ACTIONS: readonly AgentAction[] = [
  { name: 'get_project_context', class: 'read', description: 'Read authoritative project state.' },
  { name: 'preview_intent', class: 'read', description: 'Interpret natural-language intent without mutation.' },
  { name: 'preview_change', class: 'propose', description: 'Validate a proposed canonical change and its impact.' },
  { name: 'commit_change', class: 'commit', description: 'Apply an approved proposal through the canonical mutation path.' },
];

export function requiresHumanApproval(action: AgentActionClass): boolean {
  return action !== 'read';
}

export function isSafeToRunAutomatically(action: AgentActionClass): boolean {
  return action === 'read';
}
