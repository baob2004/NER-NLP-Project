// src/pages/HistoryPage.jsx
import { useMemo, useState } from "react";
import NerResult from "../components/NerResult";
import {
  loadHistory,
  deleteHistoryItem,
  clearHistory,
} from "../historyStore";

const FONT =
  '"Be Vietnam Pro", "Inter", "Segoe UI", Roboto, Arial, sans-serif';

const pageStyle = {
  fontFamily: FONT,
  color: "#111827",
  maxWidth: 1050,
  margin: "0 auto",
  padding: "42px 24px 56px",
  textAlign: "left",
};

function formatTime(iso) {
  try {
    return new Date(iso).toLocaleString("vi-VN");
  } catch {
    return iso;
  }
}

function entityWords(arr) {
  const seen = new Set();
  const out = [];
  (arr || []).forEach((item) => {
    const w = String(item?.word || item?.text || item || "").trim();
    if (!w || seen.has(w.toLowerCase())) return;
    seen.add(w.toLowerCase());
    out.push(w);
  });
  return out;
}

function HistoryRow({ item, index, onView, onDelete }) {
  const persons = entityWords(item.result?.entities?.PERSON).slice(0, 3);
  const charges = entityWords(item.result?.entities?.CHARGE).slice(0, 2);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "40px 1fr auto",
        gap: 16,
        alignItems: "start",
        padding: "18px 0",
        borderTop: index === 0 ? "none" : "1px solid #e5e7eb",
      }}
    >
      <div style={{ color: "#6b7280", fontWeight: 850, fontSize: 14 }}>
        {String(index + 1).padStart(2, "0")}
      </div>

      <div>
        <div style={{ fontSize: 16, fontWeight: 850, color: "#111827", marginBottom: 4 }}>
          📄 {item.filename}
        </div>
        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 6 }}>
          {formatTime(item.savedAt)} · Model: {item.model} ·{" "}
          <strong>{item.count}</strong> thực thể
          {typeof item.elapsedMs === "number" ? ` · ${item.elapsedMs}ms` : ""}
        </div>
        <div style={{ fontSize: 13.5, color: "#374151", lineHeight: 1.6 }}>
          {persons.length > 0 && (
            <div>
              <span style={{ color: "#6b7280" }}>Bị cáo: </span>
              {persons.join(", ")}
            </div>
          )}
          {charges.length > 0 && (
            <div>
              <span style={{ color: "#6b7280" }}>Tội danh: </span>
              {charges.join(", ")}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <button type="button" onClick={() => onView(item)} style={btnPrimary}>
          Xem lại
        </button>
        <button type="button" onClick={() => onDelete(item.id)} style={btnGhost}>
          Xóa
        </button>
      </div>
    </div>
  );
}

const btnPrimary = {
  border: "1px solid #1d4ed8",
  background: "#1d4ed8",
  color: "#ffffff",
  borderRadius: 8,
  padding: "8px 16px",
  fontSize: 13,
  fontWeight: 750,
  cursor: "pointer",
  whiteSpace: "nowrap",
};

const btnGhost = {
  border: "1px solid #d1d5db",
  background: "#ffffff",
  color: "#b91c1c",
  borderRadius: 8,
  padding: "8px 16px",
  fontSize: 13,
  fontWeight: 750,
  cursor: "pointer",
  whiteSpace: "nowrap",
};

export default function HistoryPage() {
  const [items, setItems] = useState(() => loadHistory());
  const [selected, setSelected] = useState(null);

  const hasItems = items.length > 0;
  const headerTitle = useMemo(
    () => `Lịch sử phân tích (${items.length})`,
    [items.length]
  );

  const handleDelete = (id) => {
    setItems(deleteHistoryItem(id));
  };

  const handleClear = () => {
    if (window.confirm("Xóa toàn bộ lịch sử phân tích?")) {
      clearHistory();
      setItems([]);
    }
  };

  // Xem lại 1 bản án đã lưu (không có PDF gốc nên tab "Xem PDF" sẽ trống).
  if (selected) {
    return (
      <div style={pageStyle}>
        <button
          type="button"
          onClick={() => setSelected(null)}
          style={{ ...btnGhost, color: "#111827", marginBottom: 18 }}
        >
          ← Quay lại lịch sử
        </button>
        <NerResult
          result={selected.result}
          selectedModel={selected.result?.model_name || ""}
          pdfUrl={null}
          onReset={() => setSelected(null)}
        />
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 6,
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <h1 style={{ fontSize: 30, fontWeight: 900, margin: 0 }}>{headerTitle}</h1>
        {hasItems && (
          <button type="button" onClick={handleClear} style={btnGhost}>
            Xóa tất cả
          </button>
        )}
      </div>

      <p style={{ fontSize: 15, lineHeight: 1.7, color: "#4b5563", margin: "0 0 26px", maxWidth: 780 }}>
        Danh sách các bản án đã phân tích trên trình duyệt này. Dữ liệu được lưu cục bộ
        (localStorage), không gửi lên máy chủ.
      </p>

      {!hasItems ? (
        <div
          style={{
            background: "#ffffff",
            border: "1px dashed #cbd5e1",
            borderRadius: 14,
            padding: "48px 24px",
            textAlign: "center",
            color: "#9ca3af",
            fontSize: 15,
          }}
        >
          Chưa có bản án nào được phân tích. Hãy vào trang “Phân tích bản án” và tải lên một file PDF.
        </div>
      ) : (
        <section
          style={{
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            borderRadius: 14,
            padding: "6px 24px",
            boxShadow: "0 8px 24px rgba(15, 23, 42, 0.04)",
          }}
        >
          {items.map((item, index) => (
            <HistoryRow
              key={item.id}
              item={item}
              index={index}
              onView={setSelected}
              onDelete={handleDelete}
            />
          ))}
        </section>
      )}
    </div>
  );
}
