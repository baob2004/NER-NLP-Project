// ============================================================
// src/components/PdfViewer.jsx
// Render PDF bang PDF.js ra <canvas> -> hien thi duoc trong MOI trinh duyet
// va moi ngu canh iframe (khong dung <iframe>, khong can plugin PDF).
// Nut "Tai PDF" dung fetch->blob nen khong bi chan popup.
//
// ── CACH DUNG (3 buoc) ──────────────────────────────────────
// 1) Cai thu vien:    npm install pdfjs-dist
// 2) Luu file nay vao: src/components/PdfViewer.jsx
// 3) Trong src/components/NERResult.jsx:
//      a) Them dong import o dau file:
//             import PdfViewer from "./PdfViewer";
//      b) TIM dong render tab PDF (gan cuoi component Recognized... / tabs):
//             {tab === "pdf" && <PdfPanel pdfUrl={pdfUrl} result={result} />}
//         THAY BANG:
//             {tab === "pdf" && (
//               <PdfViewer
//                 pdfUrl={result?.highlighted_pdf_url ? `${API}${result.highlighted_pdf_url}` : pdfUrl}
//                 downloadUrl={
//                   (result?.labeled_pdf_url || result?.files?.labeled_pdf_url)
//                     ? `${API}${result.labeled_pdf_url || result.files.labeled_pdf_url}`
//                     : null
//                 }
//                 filename="ban-an-da-gan-nhan.pdf"
//               />
//             )}
//      c) (Tuy chon) Xoa ham PdfPanel cu vi khong dung nua.
// 4) npm run build  ->  copy frontend/dist  ->  git push
//
// LUU Y: neu build bao loi duong dan worker ".mjs", doi sang ".js"
//        (ban pdfjs-dist cu). Khuyen dung: npm install pdfjs-dist@latest
// ============================================================

import { useEffect, useRef, useState } from "react";

const btn = {
  fontSize: 13,
  fontWeight: 700,
  color: "#111827",
  border: "1px solid #d1d5db",
  borderRadius: 8,
  padding: "6px 12px",
  background: "#fff",
  cursor: "pointer",
};

export default function PdfViewer({ pdfUrl, downloadUrl, filename = "ban-an-da-gan-nhan.pdf" }) {
  const containerRef = useRef(null);
  const [status, setStatus] = useState("loading"); // loading | done | error
  const [numPages, setNumPages] = useState(0);

  useEffect(() => {
    let cancelled = false;

    if (!pdfUrl) {
      setStatus("error");
      return;
    }

    async function render() {
      setStatus("loading");
      try {
        const pdfjsLib = await import("pdfjs-dist");
        const workerSrc = (await import("pdfjs-dist/build/pdf.worker.min.mjs?url")).default;
        pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;

        const pdf = await pdfjsLib.getDocument(pdfUrl).promise;
        if (cancelled) return;
        setNumPages(pdf.numPages);

        const container = containerRef.current;
        if (!container) return;
        container.innerHTML = "";

        const scale = 1.4;
        for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
          const page = await pdf.getPage(pageNum);
          if (cancelled) return;

          const viewport = page.getViewport({ scale });
          const canvas = document.createElement("canvas");
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          canvas.style.width = "100%";
          canvas.style.height = "auto";
          canvas.style.display = "block";
          canvas.style.margin = "0 auto 14px";
          canvas.style.boxShadow = "0 4px 16px rgba(15,23,42,0.12)";
          canvas.style.borderRadius = "6px";

          const ctx = canvas.getContext("2d");
          container.appendChild(canvas);
          await page.render({ canvasContext: ctx, viewport }).promise;
        }

        if (!cancelled) setStatus("done");
      } catch (e) {
        console.error("PDF render error:", e);
        if (!cancelled) setStatus("error");
      }
    }

    render();
    return () => {
      cancelled = true;
    };
  }, [pdfUrl]);

  async function handleDownload() {
    const url = downloadUrl || pdfUrl;
    if (!url) return;
    try {
      const res = await fetch(url);
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(objUrl), 2000);
    } catch (e) {
      // Fallback: mo o tab moi neu fetch/download bi chan
      window.open(url, "_blank", "noopener");
    }
  }

  return (
    <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "12px 16px",
          borderBottom: "1px solid #eef2f7",
          flexWrap: "wrap",
        }}
      >
        <strong style={{ fontSize: 14 }}>
          PDF đã gán nhãn{numPages ? ` · ${numPages} trang` : ""}
        </strong>
        <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button type="button" onClick={handleDownload} style={btn}>
            ⬇ Tải PDF
          </button>
          {(downloadUrl || pdfUrl) && (
            <a
              href={downloadUrl || pdfUrl}
              target="_blank"
              rel="noreferrer"
              style={{ ...btn, textDecoration: "none", display: "inline-block" }}
            >
              Mở tab mới
            </a>
          )}
        </span>
      </div>

      <div style={{ maxHeight: 760, overflowY: "auto", padding: 16, background: "#f8fafc" }}>
        {status === "loading" && (
          <div style={{ textAlign: "center", color: "#64748b", padding: 40 }}>Đang tải PDF…</div>
        )}
        {status === "error" && (
          <div style={{ textAlign: "center", color: "#64748b", padding: 40 }}>
            Không hiển thị được PDF tại đây.{" "}
            {(downloadUrl || pdfUrl) && (
              <a href={downloadUrl || pdfUrl} target="_blank" rel="noreferrer">
                Mở PDF ở tab mới
              </a>
            )}
          </div>
        )}
        <div ref={containerRef} />
      </div>
    </div>
  );
}
