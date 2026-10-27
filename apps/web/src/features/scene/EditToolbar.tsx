import { useState } from 'react';

type EditCommand =
  | { readonly kind: 'translate'; readonly element_id: string; readonly dx_m: number; readonly dy_m: number; readonly dz_m: number }
  | { readonly kind: 'rotate'; readonly element_id: string; readonly angle_deg: number }
  | { readonly kind: 'resize'; readonly element_id: string; readonly scale: number };

type EditToolbarProps = Readonly<{
  elementId: string | null;
  onPreview: (command: EditCommand) => void;
  onCommit: (command: EditCommand) => void;
  disabled?: boolean;
}>;

export function EditToolbar({ elementId, onPreview, onCommit, disabled = false }: EditToolbarProps) {
  const [mode, setMode] = useState<'translate' | 'rotate' | 'resize'>('translate');
  const [value, setValue] = useState('1');

  const buildCommand = (): EditCommand | null => {
    if (!elementId) return null;
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return null;
    if (mode === 'translate') return { kind: 'translate', element_id: elementId, dx_m: numeric, dy_m: 0, dz_m: 0 };
    if (mode === 'rotate') return { kind: 'rotate', element_id: elementId, angle_deg: numeric };
    if (numeric <= 0) return null;
    return { kind: 'resize', element_id: elementId, scale: numeric };
  };

  const submit = (action: (command: EditCommand) => void) => {
    const command = buildCommand();
    if (command) action(command);
  };

  return (
    <div className="edit-toolbar" aria-label="Canonical model edit controls">
      <label>
        Operation
        <select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)} disabled={!elementId || disabled}>
          <option value="translate">Move X</option>
          <option value="rotate">Rotate Z</option>
          <option value="resize">Resize</option>
        </select>
      </label>
      <label>
        Value
        <input value={value} onChange={(event) => setValue(event.target.value)} inputMode="decimal" disabled={!elementId || disabled} />
      </label>
      <button type="button" className="btn outline" disabled={!elementId || disabled} onClick={() => submit(onPreview)}>Preview</button>
      <button type="button" className="btn" disabled={!elementId || disabled} onClick={() => submit(onCommit)}>Apply</button>
    </div>
  );
}

export type { EditCommand };
