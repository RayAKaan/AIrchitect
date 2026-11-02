export const MAX_AGENT_CONTEXT_CHARACTERS = 24_000;
const MAX_STRING_CHARACTERS = 3_000;
const MAX_ARRAY_ITEMS = 60;
const MAX_OBJECT_PROPERTIES = 80;

function compactValue(value: unknown, depth = 0): unknown {
  if (depth > 8) return '[nested value omitted]';
  if (typeof value === 'string') {
    return value.length > MAX_STRING_CHARACTERS
      ? `${value.slice(0, MAX_STRING_CHARACTERS)}… [${value.length - MAX_STRING_CHARACTERS} characters omitted]`
      : value;
  }
  if (Array.isArray(value)) {
    const items = value.slice(0, MAX_ARRAY_ITEMS).map(item => compactValue(item, depth + 1));
    if (value.length > MAX_ARRAY_ITEMS) items.push(`[${value.length - MAX_ARRAY_ITEMS} additional items omitted]`);
    return items;
  }
  if (typeof value === 'object' && value !== null) {
    const entries = Object.entries(value as Record<string, unknown>).slice(0, MAX_OBJECT_PROPERTIES);
    const result = Object.fromEntries(entries.map(([key, child]) => [key, compactValue(child, depth + 1)]));
    const omitted = Object.keys(value).length - entries.length;
    if (omitted > 0) result._omitted_properties = omitted;
    return result;
  }
  return value;
}

/** Keep the prompt bounded while preserving valid JSON and an explicit truncation signal. */
export function prepareAgentContext(context: string, maxCharacters = MAX_AGENT_CONTEXT_CHARACTERS): string {
  if (!Number.isInteger(maxCharacters) || maxCharacters < 512) {
    throw new Error('Agent context budget must be an integer of at least 512 characters.');
  }
  if (context.length <= maxCharacters) return context;
  const marker = '[Context shortened to fit the model budget. Use AIrchitect MCP tools to inspect complete canonical project data.]';
  try {
    const compacted = JSON.stringify(compactValue(JSON.parse(context)), null, 2);
    if (compacted.length <= maxCharacters) return compacted;
    const envelope = {
      context_excerpt: '',
      context_truncated: true,
      omitted_characters: compacted.length,
      instruction: marker,
    };
    let excerptBudget = Math.max(0, maxCharacters - JSON.stringify(envelope).length - 32);
    for (let attempt = 0; attempt < 12; attempt += 1) {
      envelope.context_excerpt = compacted.slice(0, excerptBudget);
      envelope.omitted_characters = Math.max(0, compacted.length - envelope.context_excerpt.length);
      const encoded = JSON.stringify(envelope);
      if (encoded.length <= maxCharacters) return encoded;
      excerptBudget = Math.floor(excerptBudget * 0.8);
    }
    envelope.context_excerpt = '';
    envelope.omitted_characters = compacted.length;
    return JSON.stringify(envelope);
  } catch {
    return `${context.slice(0, maxCharacters - marker.length - 1)}\n${marker}`;
  }
}
