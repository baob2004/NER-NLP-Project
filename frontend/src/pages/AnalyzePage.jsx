import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "../config";
import { styles } from "../styles";
import { processEntities } from "../utils";
import NerResult from "../components/NerResult";
import { saveAnalysis } from "../historyStore";

function ModelSelector({ models, selectedModel, setSelectedModel, modelRoot }) {
  return (
    <div style={styles.modelBox}>
      <div style={styles.sectionHeader}>Chọn model NER</div>
      <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} style={styles.modelSelect}>
        {models.length === 0 ? (
          <option value="">Không tìm thấy model</option>
        ) : (
          models.map((m) => (
            <option key={m.name} value={m.name}>{m.display_name || "PhoBERT"}{m.is_loaded ? "  (đã load)" : ""}</option>
          ))
        )}
      </select>
      <div style={{ ...styles.muted, marginTop: 8 }}>Model hiển thị: PhoBERT</div>
    </div>
  );
}

function UploadZone({ onFile, loading }) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  const handle = useCallback((file) => {
    if (file && file.type === "application/pdf") onFile(file);
  }, [onFile]);

  return (
    <div
      onClick={() => !loading && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files[0]); }}
      style={{
        ...styles.uploadZone,
        borderColor: drag ? "#2563eb" : "#cbd5e1",
        background: drag ? "#eff6ff" : "#fafafa",
        cursor: loading ? "not-allowed" : "pointer",
        opacity: loading ? 0.65 : 1,
      }}
    >
      <input ref={inputRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={(e) => handle(e.target.files[0])} />
      <div style={{ fontSize: 48, marginBottom: 8 }}>📄</div>
      <div style={{ fontWeight: 850, fontSize: 16 }}>{loading ? "Đang xử lý..." : "Kéo thả hoặc click để chọn PDF"}</div>
      <div style={{ color: "#64748b", fontSize: 13, marginTop: 4 }}>Bản án hình sự tiếng Việt · Tối đa 50MB</div>
    </div>
  );
}

export default function AnalyzePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [filename, setFilename] = useState(null);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [modelRoot, setModelRoot] = useState("");
  const [pdfUrl, setPdfUrl] = useState(null);

  useEffect(() => {
    async function loadModels() {
      try {
        const res = await fetch(`${API}/models`);
        const data = await res.json();
        setModels(data.models || []);
        setModelRoot(data.model_root || "");
        setSelectedModel(data.default_model || data.models?.[0]?.name || "");
      } catch (e) {
        console.error("Không tải được danh sách model:", e);
      }
    }
    loadModels();
  }, []);

  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
  }, [pdfUrl]);

  const handleFile = async (file) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setFilename(file.name);

    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    const nextPdfUrl = URL.createObjectURL(file);
    setPdfUrl(nextPdfUrl);

    try {
      const form = new FormData();
      form.append("file", file);
      if (selectedModel) form.append("model_name", selectedModel);

      const res = await fetch(`${API}/analyze`, { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      data.entities = processEntities(data.entities);
      setResult(data);
      saveAnalysis(data, selectedModel); // lưu vào lịch sử (localStorage)
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setResult(null);
    setError(null);
    setFilename(null);
    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl);
      setPdfUrl(null);
    }
  };

  return (
    <div style={styles.page}>
      <h1 style={styles.pageTitle}>Phân tích bản án hình sự ma túy</h1>
      <br></br>
      {!result && !loading && (
        <>
          <ModelSelector models={models} selectedModel={selectedModel} setSelectedModel={setSelectedModel} modelRoot={modelRoot} />
          <UploadZone onFile={handleFile} loading={loading} />
          {error && <div style={styles.errorBox}><span>⚠️</span> {error}</div>}
        </>
      )}

      {loading && (
        <div style={styles.loadingBox}>
          <div style={styles.spinner} />
          <div style={{ fontWeight: 800, fontSize: 16 }}>Đang phân tích {filename}...</div>
          <div style={{ color: "#64748b", fontSize: 13 }}>Trích xuất đoạn văn → chạy model PhoBERT → trả kết quả NER</div>
        </div>
      )}

      {result && <NerResult result={result} selectedModel={selectedModel} pdfUrl={pdfUrl} onReset={reset} />}
    </div>
  );
}
