// src/historyStore.js
// ---------------------------------------------------------------------------
// Lưu / đọc lịch sử các bản án đã phân tích bằng localStorage.
// Không cần backend. Lưu tối đa MAX_ITEMS bản gần nhất, tự xử lý khi đầy bộ nhớ.
// ---------------------------------------------------------------------------
const KEY = "drugner_history_v1";
const MAX_ITEMS = 30;

function safeParse(json) {
  try {
    const data = JSON.parse(json);
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export function loadHistory() {
  if (typeof window === "undefined") return [];
  return safeParse(window.localStorage.getItem(KEY));
}

function persist(items) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(items));
    return true;
  } catch {
    // Vượt quá dung lượng -> bỏ bớt mục cũ nhất rồi thử lại.
    const trimmed = [...items];
    while (trimmed.length > 1) {
      trimmed.pop();
      try {
        window.localStorage.setItem(KEY, JSON.stringify(trimmed));
        return true;
      } catch {
        /* tiếp tục bỏ bớt */
      }
    }
    return false;
  }
}

// Chỉ giữ những trường cần để hiển thị lại trong NerResult (bỏ records/sections... cho nhẹ).
function trimResult(result) {
  if (!result) return {};
  return {
    filename: result.filename,
    model_name: result.model_name,
    model_display_name: result.model_display_name,
    elapsed_ms: result.elapsed_ms,
    entities: result.entities || {},
    highlighted: result.highlighted || [],
    highlighted_pdf_url: null,
  };
}

function countAll(entities) {
  return Object.values(entities || {}).reduce(
    (sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0),
    0
  );
}

export function saveAnalysis(result, selectedModel) {
  if (!result || typeof window === "undefined") return null;

  const entry = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
    savedAt: new Date().toISOString(),
    filename: result.filename || "Không rõ tên",
    model: result.model_display_name || result.model_name || selectedModel || "PhoBERT",
    elapsedMs: typeof result.elapsed_ms === "number" ? result.elapsed_ms : null,
    count: countAll(result.entities),
    result: trimResult(result),
  };

  const next = [entry, ...loadHistory()].slice(0, MAX_ITEMS);
  persist(next);
  return entry;
}

export function deleteHistoryItem(id) {
  const next = loadHistory().filter((item) => item.id !== id);
  persist(next);
  return next;
}

export function clearHistory() {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* bỏ qua */
  }
  return [];
}
