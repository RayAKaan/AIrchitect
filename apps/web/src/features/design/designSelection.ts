export type SelectionState = {
  selectedId: string | null;
  rationale: string;
  confirmed: boolean;
};

export function emptySelection(): SelectionState {
  return { selectedId: null, rationale: '', confirmed: false };
}

export function selectConcept(selection: SelectionState, id: string): SelectionState {
  const nextId = id.trim();
  if (!nextId) throw new Error('A concept id is required');
  return { ...selection, selectedId: nextId, confirmed: false };
}

export function confirmConcept(selection: SelectionState, rationale: string): SelectionState {
  if (!selection.selectedId) throw new Error('Select a concept before confirming it');
  const normalized = rationale.trim();
  if (normalized.length < 3) throw new Error('A decision rationale is required');
  return { ...selection, rationale: normalized, confirmed: true };
}
