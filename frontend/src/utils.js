export function cleanWord(word) {
  if (!word) return "";
  return String(word).replace(/[^\p{L}\p{N}\s,.\-/]/gu, "").replace(/\s+/g, " ").trim();
}

export function deduplicateEntities(items) {
  if (!items || items.length === 0) return [];
  const seen = new Map();

  for (const item of items) {
    const key = cleanWord(item.word).toLowerCase();
    if (!key) continue;
    if (!seen.has(key) || Number(item.score || 0) > Number(seen.get(key).score || 0)) {
      seen.set(key, { ...item, word: cleanWord(item.word) });
    }
  }

  return Array.from(seen.values());
}

export function processEntities(rawEntities) {
  if (!rawEntities) return {};
  const result = {};

  for (const [type, items] of Object.entries(rawEntities)) {
    result[type] = deduplicateEntities(items);
  }

  return result;
}

export function normalizeForCompare(value) {
  return String(value || "").replace(/\s+/g, " ").trim().toLowerCase();
}

export function countEntities(entities = {}) {
  return Object.values(entities).reduce((sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0), 0);
}
