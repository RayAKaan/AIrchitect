export type ConstraintStrength = 'hard' | 'soft';
export type ConstraintSource = 'brief' | 'regulation' | 'human' | 'system';

export type DesignConstraint = {
  id: string;
  label: string;
  parameter: string;
  value: string | number | boolean;
  unit?: string;
  strength: ConstraintStrength;
  source: ConstraintSource;
  locked: boolean;
};

export function normalizeConstraint(input: Omit<DesignConstraint, 'id'> & { id?: string }): DesignConstraint {
  const label = input.label.trim();
  const parameter = input.parameter.trim();
  if (!label || !parameter) throw new Error('Constraint label and parameter are required');
  return {
    ...input,
    id: input.id?.trim() || `${input.strength}:${parameter}`,
    label,
    parameter,
  };
}

export function splitConstraints(constraints: readonly DesignConstraint[]) {
  return {
    hard: constraints.filter((constraint) => constraint.strength === 'hard'),
    soft: constraints.filter((constraint) => constraint.strength === 'soft'),
  };
}

export function canEditConstraint(constraint: DesignConstraint): boolean {
  return !constraint.locked && constraint.source !== 'regulation';
}
