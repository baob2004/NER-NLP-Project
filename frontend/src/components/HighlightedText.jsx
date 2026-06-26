import { ENTITY_CONFIG } from "../config";
import { styles } from "../styles";
import { normalizeForCompare } from "../utils";

function getSpanWord(sp) {
  return String(sp?.word || sp?.text || "").trim();
}

function getEntityLabel(entity, cfg = {}) {
  return String(cfg.shortLabel || cfg.short || entity || "ENTITY").toUpperCase();
}

function findSpanByWord(text, word, fromIndex = 0) {
  const safeText = String(text || "");
  const safeWord = String(word || "").trim();
  if (!safeText || !safeWord) return null;

  let idx = safeText.indexOf(safeWord, fromIndex);
  if (idx !== -1) return { start: idx, end: idx + safeWord.length };

  idx = safeText.indexOf(safeWord);
  if (idx !== -1) return { start: idx, end: idx + safeWord.length };

  const lowerText = safeText.toLowerCase();
  const lowerWord = safeWord.toLowerCase();

  idx = lowerText.indexOf(lowerWord, fromIndex);
  if (idx !== -1) return { start: idx, end: idx + safeWord.length };

  idx = lowerText.indexOf(lowerWord);
  if (idx !== -1) return { start: idx, end: idx + safeWord.length };

  const normalizedWord = normalizeForCompare(safeWord);
  if (!normalizedWord) return null;

  const minLen = Math.max(1, safeWord.length - 8);
  const maxLen = Math.min(safeText.length, safeWord.length + 20);

  for (let i = Math.max(0, fromIndex); i < safeText.length; i++) {
    for (let len = minLen; len <= maxLen && i + len <= safeText.length; len++) {
      if (normalizeForCompare(safeText.slice(i, i + len)) === normalizedWord) {
        return { start: i, end: i + len };
      }
    }
  }

  for (let i = 0; i < safeText.length; i++) {
    for (let len = minLen; len <= maxLen && i + len <= safeText.length; len++) {
      if (normalizeForCompare(safeText.slice(i, i + len)) === normalizedWord) {
        return { start: i, end: i + len };
      }
    }
  }

  return null;
}

function buildSafeHighlightSpans(text, spans) {
  const safeText = String(text || "");
  if (!safeText || !Array.isArray(spans) || spans.length === 0) return [];

  const fixed = [];
  let searchFrom = 0;

  for (const sp of spans) {
    const word = getSpanWord(sp);
    let start = Number(sp?.start);
    let end = Number(sp?.end);

    const hasValidOffset =
      Number.isInteger(start) &&
      Number.isInteger(end) &&
      start >= 0 &&
      end > start &&
      end <= safeText.length;

    const slice = hasValidOffset ? safeText.slice(start, end) : "";
    const offsetMatchesWord = !word || normalizeForCompare(slice) === normalizeForCompare(word);

    if (!hasValidOffset || !offsetMatchesWord) {
      const found = findSpanByWord(safeText, word, searchFrom);
      if (!found) continue;
      start = found.start;
      end = found.end;
    }

    fixed.push({ ...sp, start, end, word: word || safeText.slice(start, end) });
    searchFrom = Math.max(searchFrom, end);
  }

  const sorted = fixed.sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start;
    return b.end - a.end;
  });

  const cleaned = [];
  let cursor = 0;
  for (const sp of sorted) {
    if (sp.start < cursor) continue;
    cleaned.push(sp);
    cursor = sp.end;
  }

  return cleaned;
}

export default function HighlightedText({ text, spans, large = false }) {
  const safeText = String(text || "");
  const safeSpans = buildSafeHighlightSpans(safeText, spans);

  const paragraphStyle = {
    ...styles.rawText,
    ...(large
      ? {
          fontSize: 19,
          lineHeight: 2.05,
          textAlign: "left",
          margin: 0,
          color: "#0f172a",
        }
      : {}),
  };

  if (safeSpans.length === 0) {
    return <p style={paragraphStyle}>{safeText}</p>;
  }

  const parts = [];
  let cursor = 0;

  safeSpans.forEach((sp, i) => {
    if (sp.start > cursor) {
      parts.push(<span key={`t-${i}-${cursor}`}>{safeText.slice(cursor, sp.start)}</span>);
    }

    const cfg = ENTITY_CONFIG[sp.entity] || {};
    const label = getEntityLabel(sp.entity, cfg);

    parts.push(
      <mark
        key={`e-${i}-${sp.start}-${sp.end}`}
        title={cfg.label || sp.entity}
        style={{
          background: cfg.bg || "#fef9c3",
          color: cfg.color || "#92400e",
          borderBottom: `2px solid ${cfg.color || "#d97706"}`,
          borderRadius: large ? 8 : 4,
          padding: large ? "3px 6px" : "1px 4px",
          fontWeight: 800,
          cursor: "help",
          boxDecorationBreak: "clone",
          WebkitBoxDecorationBreak: "clone",
        }}
      >
        {safeText.slice(sp.start, sp.end)}
        <span
          style={{
            marginLeft: 7,
            display: "inline-block",
            verticalAlign: "middle",
            fontSize: large ? "0.58em" : "0.62em",
            lineHeight: 1.2,
            fontWeight: 950,
            letterSpacing: 0.45,
            textTransform: "uppercase",
            color: "#ffffff",
            background: cfg.color || "#d97706",
            borderRadius: 999,
            padding: large ? "3px 7px" : "2px 6px",
          }}
        >
          {label}
        </span>
      </mark>
    );

    cursor = sp.end;
  });

  if (cursor < safeText.length) {
    parts.push(<span key="tail">{safeText.slice(cursor)}</span>);
  }

  return <p style={paragraphStyle}>{parts}</p>;
}
