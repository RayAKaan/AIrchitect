export type ConstraintStrength = 'hard' | 'soft';
export type ConstraintSource = 'brief' | 'regulation' | 'human' | 'system';
export type DesignConstraint = { id: string; label: string; parameter: string; value: string | number | boolean; unit?: string; strength: ConstraintStrength; source: ConstraintSource; locked: boolean };
export type ConstraintCheck = { constraint: DesignConstraint; satisfied: boolean | null; reason: string };

export function normalizeConstraint(input: Omit<DesignConstraint, 'id'> & { id?: string }): DesignConstraint {
  const label = input.label.trim(); const parameter = input.parameter.trim();
  if (!label || !parameter) throw new Error('Constraint label and parameter are required');
  return { ...input, id: input.id?.trim() || `${input.strength}:${parameter}`, label, parameter };
}

export function splitConstraints(constraints: readonly DesignConstraint[]) { return { hard: constraints.filter((constraint) => constraint.strength === 'hard'), soft: constraints.filter((constraint) => constraint.strength === 'soft') }; }
export function canEditConstraint(constraint: DesignConstraint) { return !constraint.locked && constraint.source !== 'regulation'; }

export function evaluateConstraint(constraint: DesignConstraint, observed: unknown): ConstraintCheck {
  if (observed == null) return { constraint, satisfied: null, reason: 'No observed value is available yet.' };
  if (typeof constraint.value === 'number' && typeof observed === 'number') return { constraint, satisfied: observed <= constraint.value, reason: `Observed ${observed}; target ceiling ${constraint.value}.` };
  if (typeof constraint.value === 'boolean' && typeof observed === 'boolean') return { constraint, satisfied: observed === constraint.value, reason: `Observed ${observed}; expected ${constraint.value}.` };
  return { constraint, satisfied: String(observed).trim().toLowerCase() === String(constraint.value).trim().toLowerCase(), reason: `Observed ${String(observed)}; expected ${String(constraint.value)}.` };
}

export function detectConflicts(constraints: readonly DesignConstraint[]): string[] {
  const conflicts: string[] = [];
  const grouped = new Map<string, DesignConstraint[]>();
  for (const constraint of constraints) grouped.set(constraint.parameter, [...(grouped.get(constraint.parameter) || []), constraint]);
  for (const [parameter, items] of grouped) {
    const hardValues = items.filter((item) => item.strength === 'hard').map((item) => String(item.value));
    if (new Set(hardValues).size > 1) conflicts.push(`Conflicting hard constraints for ${parameter}.`);
  }
  return conflicts;
}

export function constraintStorageKey(projectId: string, versionId: string) { return `airchitect:constraints:${projectId}:${versionId}`; }
export function readConstraints(projectId: string, versionId: string): DesignConstraint[] { try { const raw = sessionStorage.getItem(constraintStorageKey(projectId, versionId)); return raw ? JSON.parse(raw) as DesignConstraint[] : []; } catch { return []; } }
export function writeConstraints(projectId: string, versionId: string, constraints: readonly DesignConstraint[]) { try { sessionStorage.setItem(constraintStorageKey(projectId, versionId), JSON.stringify(constraints)); } catch { /* Optional browser persistence. */ } }
