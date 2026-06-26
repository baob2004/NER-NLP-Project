import { useMemo, useState } from "react";
import { API } from "../config";
import { styles } from "../styles";
import { cleanWord, countEntities } from "../utils";
import HighlightedText from "./HighlightedText";
import PdfViewer from "./PdfViewer";
const VIETNAMESE_FONT =
  '"Be Vietnam Pro", "Inter", "Segoe UI", Roboto, Arial, sans-serif';

const baseFont = {
  fontFamily: VIETNAMESE_FONT,
  fontFeatureSettings: '"kern" 1',
  textRendering: "optimizeLegibility",
};

const DETAIL_TYPES = [
  "PERSON",
  "CHARGE",
  "LEGAL_ARTICLE",
  "SENTENCE",
  "DRUG",
  "DRUG_WEIGHT",
  "CRIME_TIME",
  "CRIME_LOC",
];

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFC")
    .replace(/[“”"]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function capitalizeVietnameseSentence(value) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return text;

  return text
    .replace(/(^|[.!?]\s+)([a-zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ])/g, (match, prefix, char) => {
      return prefix + char.toLocaleUpperCase("vi-VN");
    })
    .replace(/^\s*điểm\b/iu, "Điểm")
    .replace(/^\s*khoản\b/iu, "Khoản")
    .replace(/^\s*điều\b/iu, "Điều")
    .replace(/^\s*tội\b/iu, "Tội")
    .replace(/^\s*chất\b/iu, "Chất")
    .replace(/\bđiều\b/gi, "Điều")
    .replace(/\b(blhs|bltths|mdma|pc09|vks|hđxx)\b/gi, (m) =>
      m.toLocaleUpperCase("vi-VN")
    );
}

function uniqueEntityWords(values) {
  const seen = new Set();
  const out = [];

  (values || []).forEach((item) => {
    const word = cleanWord(item?.word || item?.text || "");
    if (!word) return;

    const key = normalizeText(word);
    if (seen.has(key)) return;

    seen.add(key);
    out.push(word);
  });

  return out;
}

function uniqueEntityRows(values) {
  const seen = new Set();
  const out = [];

  (values || []).forEach((item) => {
    const word = cleanWord(item?.word || item?.text || "");
    if (!word) return;

    const key = [
      normalizeText(word),
      item?.section || "",
      item?.record_idx ?? "",
      item?.start ?? "",
      item?.end ?? "",
    ].join("|");

    if (seen.has(key)) return;
    seen.add(key);

    out.push({
      value: word,
      section: item?.section || "",
      score: typeof item?.score === "number" ? item.score : null,
      ruleBased: Boolean(item?.rule_based),
    });
  });

  return out;
}

function SummaryRow({ index, label, values }) {
  const words = uniqueEntityWords(values);

  return (
    <tr>
      <td
        style={{
          width: 240,
          padding: "14px 16px",
          borderBottom: "1px solid #e5e7eb",
          verticalAlign: "top",
          background: index % 2 === 0 ? "#ffffff" : "#f9fafb",
          color: "#111827",
          fontWeight: 850,
          lineHeight: 1.55,
          textAlign: "left",
        }}
      >
        {index}. {label}
      </td>

      <td
        style={{
          padding: "14px 16px",
          borderBottom: "1px solid #e5e7eb",
          verticalAlign: "top",
          background: index % 2 === 0 ? "#ffffff" : "#f9fafb",
          color: words.length > 0 ? "#1f2937" : "#9ca3af",
          fontWeight: words.length > 0 ? 600 : 500,
          lineHeight: 1.75,
          textAlign: "left",
        }}
      >
        {words.length === 0 ? (
          <span>Không tìm thấy</span>
        ) : (
          <div>
            {words.map((word, i) => (
              <div
                key={`${label}-${word}-${i}`}
                style={{
                  marginBottom: i === words.length - 1 ? 0 : 6,
                  paddingLeft: 14,
                  position: "relative",
                }}
              >
                <span
                  style={{
                    position: "absolute",
                    left: 0,
                    color: "#6b7280",
                  }}
                >
                  -
                </span>
                {word}
              </div>
            ))}
          </div>
        )}
      </td>
    </tr>
  );
}

function getSectionTitle(section) {
  if (section === "noi_dung") return "Nội dung vụ án";
  if (section === "nhan_dinh") return "Nhận định";
  if (section === "quyet_dinh") return "Quyết định";
  return "Không rõ";
}

function getSimpleNote(type) {
  if (type === "PERSON") return "Tên người được nhận diện là bị cáo";
  if (type === "CHARGE") return "Tội danh được nhận diện trong bản án";
  if (type === "LEGAL_ARTICLE") return "Căn cứ pháp lý hoặc điều luật áp dụng";
  if (type === "SENTENCE") return "Mức hình phạt được nhận diện";
  if (type === "DRUG") return "Tên chất ma túy được nhận diện";
  if (type === "DRUG_WEIGHT") return "Khối lượng ma túy được nhận diện";
  if (type === "CRIME_TIME") return "Mốc thời gian liên quan đến hành vi phạm tội";
  if (type === "CRIME_LOC") return "Địa điểm liên quan đến hành vi phạm tội";
  return "Thông tin được nhận diện";
}

function flattenHighlighted(highlighted = []) {
  const parts = [];
  let cursor = 0;

  highlighted.forEach((item) => {
    const text = String(item?.text || "").trim();
    if (!text) return;

    if (parts.length > 0) {
      parts.push({ text: "\n\n", spans: [] });
    }

    parts.push({
      text,
      spans: (item.spans || []).map((span) => ({ ...span })),
    });
  });

  const fullText = parts.map((part) => part.text).join("");
  const spans = [];

  parts.forEach((part) => {
    (part.spans || []).forEach((span) => {
      spans.push({
        ...span,
        start: cursor + Number(span.start || 0),
        end: cursor + Number(span.end || 0),
      });
    });
    cursor += part.text.length;
  });

  return { text: fullText, spans };
}

function RecognizedTextPanel({ highlighted }) {
  const merged = useMemo(() => flattenHighlighted(highlighted || []), [highlighted]);

  return (
    <div
      style={{
        ...baseFont,
        minHeight: 620,
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-start",
        padding: "30px 12px 46px",
      }}
    >
      <div
        style={{
          width: "min(100%, 1120px)",
          background: "#ffffff",
          border: "1px solid #e5e7eb",
          borderRadius: 22,
          boxShadow: "0 14px 38px rgba(15, 23, 42, 0.08)",
          padding: "38px 46px",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 26 }}>
          <div style={{ fontSize: 26, fontWeight: 950, color: "#111827" }}>
            Văn bản được nhận diện
          </div>
        </div>

        {merged.text ? (
          <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            <HighlightedText text={merged.text} spans={merged.spans} large />
          </div>
        ) : (
          <div style={styles.emptyState}>Không có đoạn văn nào được trích xuất.</div>
        )}
      </div>
    </div>
  );
}

function PdfPanel({ pdfUrl, result }) {
  const viewUrl = result?.highlighted_pdf_url
    ? `${API}${result.highlighted_pdf_url}`
    : pdfUrl;

  // URL tai PDF da gan nhan tu server (Content-Disposition: attachment).
  const downloadUrl =
    result?.labeled_pdf_url ? `${API}${result.labeled_pdf_url}` :
    result?.files?.labeled_pdf_url ? `${API}${result.files.labeled_pdf_url}` :
    null;

  const linkBtn = {
    textDecoration: "none",
    fontSize: 13,
    fontWeight: 750,
    color: "#111827",
    border: "1px solid #d1d5db",
    borderRadius: 8,
    padding: "6px 12px",
    background: "#ffffff",
    whiteSpace: "nowrap",
  };

  return (
    <div
      style={{
        ...baseFont,
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: 16,
        overflow: "hidden",
        minHeight: 720,
      }}
    >
      <div style={{ ...styles.pdfPanelHeader, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span>PDF {result?.highlighted_pdf_url ? "đã highlight đúng tọa độ" : "bản gốc"}</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {viewUrl && (
            <a href={viewUrl} target="_blank" rel="noreferrer" style={linkBtn}>
              Mở PDF ở tab mới
            </a>
          )}
          {downloadUrl && (
            <a href={downloadUrl} target="_blank" rel="noreferrer" style={linkBtn}>
              Tải PDF đã gán nhãn
            </a>
          )}
        </span>
      </div>

      {viewUrl ? (
        <iframe
          src={viewUrl}
          title={result?.highlighted_pdf_url ? "PDF đã highlight" : "PDF gốc"}
          style={{ ...styles.pdfIframe, minHeight: 720 }}
        />
      ) : (
        <div style={styles.emptyState}>
          Không có PDF để hiển thị. Dùng nút “Mở PDF ở tab mới” phía trên.
        </div>
      )}
    </div>
  );
}


function SummaryPanel({ entities }) {
  return (
    <section
      style={{
        ...baseFont,
        ...styles.section,
        maxWidth: "none",
        margin: 0,
        padding: "26px 28px",
        textAlign: "left",
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: 16,
        boxShadow: "0 10px 28px rgba(15, 23, 42, 0.06)",
      }}
    >
      <div
        style={{
          fontSize: 24,
          fontWeight: 950,
          color: "#111827",
          marginBottom: 20,
          textAlign: "left",
          letterSpacing: "-0.01em",
        }}
      >
        Tóm tắt kết quả nhận diện
      </div>

      <div style={{ width: "100%", overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 16,
            color: "#111827",
            textAlign: "left",
            border: "1px solid #e5e7eb",
          }}
        >
          <tbody>
            <SummaryRow index={1} label="Tên bị cáo" values={entities.PERSON} />
            <SummaryRow index={2} label="Tội danh" values={entities.CHARGE} />
            <SummaryRow index={3} label="Điều luật" values={entities.LEGAL_ARTICLE} />
            <SummaryRow index={4} label="Hình phạt" values={entities.SENTENCE} />
            <SummaryRow index={5} label="Loại ma túy" values={entities.DRUG} />
            <SummaryRow index={6} label="Khối lượng ma túy" values={entities.DRUG_WEIGHT} />
            <SummaryRow index={7} label="Thời gian phạm tội" values={entities.CRIME_TIME} />
            <SummaryRow index={8} label="Địa điểm phạm tội" values={entities.CRIME_LOC} />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function getTypeTitle(type) {
  if (type === "LEGAL_ARTICLE") return "Chi tiết điều luật";
  if (type === "DRUG") return "Chi tiết loại ma túy";
  if (type === "CHARGE") return "Chi tiết tội danh";
  return type;
}

// ---------------------------------------------------------------------------
// 1) ĐIỀU LUẬT  (khớp theo "điều <số>"; kiểm tra số có chữ "a" trước số trơn)
// ---------------------------------------------------------------------------
const LEGAL_ARTICLE_TABLE = [
  // --- Nhóm tội phạm về ma túy (Chương XX BLHS) ---
  ["điều 247", "Điều 247 BLHS – Tội trồng cây thuốc phiện, cây côca, cây cần sa hoặc các loại cây khác có chứa chất ma túy."],
  ["điều 248", "Điều 248 BLHS – Tội sản xuất trái phép chất ma túy."],
  ["điều 249", "Điều 249 BLHS – Tội tàng trữ trái phép chất ma túy."],
  ["điều 250", "Điều 250 BLHS – Tội vận chuyển trái phép chất ma túy."],
  ["điều 251", "Điều 251 BLHS – Tội mua bán trái phép chất ma túy."],
  ["điều 252", "Điều 252 BLHS – Tội chiếm đoạt chất ma túy."],
  ["điều 253", "Điều 253 BLHS – Tội tàng trữ, vận chuyển, mua bán hoặc chiếm đoạt tiền chất dùng vào việc sản xuất trái phép chất ma túy."],
  ["điều 254", "Điều 254 BLHS – Tội sản xuất, tàng trữ, vận chuyển hoặc mua bán phương tiện, dụng cụ dùng vào việc sản xuất hoặc sử dụng trái phép chất ma túy."],
  ["điều 255", "Điều 255 BLHS – Tội tổ chức sử dụng trái phép chất ma túy."],
  // 256a phải đặt TRƯỚC 256 để không bị "điều 256" bắt nhầm.
  ["điều 256a", "Điều 256a BLHS – Tội sử dụng trái phép chất ma túy (bổ sung bởi Luật số 86/2025/QH15, có hiệu lực từ 01/7/2025)."],
  ["điều 256", "Điều 256 BLHS – Tội chứa chấp việc sử dụng trái phép chất ma túy."],
  ["điều 257", "Điều 257 BLHS – Tội cưỡng bức người khác sử dụng trái phép chất ma túy."],
  ["điều 258", "Điều 258 BLHS – Tội lôi kéo người khác sử dụng trái phép chất ma túy."],
  ["điều 259", "Điều 259 BLHS – Tội vi phạm quy định về quản lý chất ma túy, tiền chất, thuốc gây nghiện, thuốc hướng thần."],

  // --- Các điều phần chung thường viện dẫn trong phần Quyết định ---
  ["điều 17", "Điều 17 BLHS – Quy định về đồng phạm."],
  ["điều 38", "Điều 38 BLHS – Hình phạt tù có thời hạn."],
  ["điều 50", "Điều 50 BLHS – Căn cứ quyết định hình phạt."],
  ["điều 51", "Điều 51 BLHS – Các tình tiết giảm nhẹ trách nhiệm hình sự."],
  ["điều 52", "Điều 52 BLHS – Các tình tiết tăng nặng trách nhiệm hình sự."],
  ["điều 54", "Điều 54 BLHS – Quyết định hình phạt dưới mức thấp nhất của khung hình phạt được áp dụng."],
  ["điều 55", "Điều 55 BLHS – Quyết định hình phạt trong trường hợp phạm nhiều tội (tổng hợp hình phạt)."],
  ["điều 65", "Điều 65 BLHS – Án treo."],
];

function getLegalArticleDetail(value) {
  const text = normalizeText(value);
  for (const [key, desc] of LEGAL_ARTICLE_TABLE) {
    if (text.includes(key)) return desc;
  }
  return "Điều luật hoặc căn cứ pháp lý được Tòa án áp dụng trong bản án.";
}

// ---------------------------------------------------------------------------
// 2) CHẤT MA TÚY  (mô tả bản chất + tên đường phố + lưu ý pháp lý)
//     Lưu ý chung: theo BLHS, KHỐI LƯỢNG và HÀM LƯỢNG chất ma túy xác định
//     qua kết luận giám định là căn cứ định khung hình phạt (Điều 248–252).
// ---------------------------------------------------------------------------
const DRUG_TABLE = [
  [["methamphetamine", "metamphetamine", "meth", "ma túy đá", "hàng đá", "ma tuý đá", " đá"],
    "Methamphetamine (ma túy đá, hàng đá) – chất ma túy tổng hợp nhóm kích thích dạng amphetamine (ATS). Khối lượng và hàm lượng Methamphetamine là căn cứ định khung hình phạt tại các Điều 248–252 BLHS."],
  [["heroin", "heroine", "bạch phiến", "hàng trắng"],
    "Heroin (bạch phiến, hàng trắng) – chất ma túy nhóm opioid bán tổng hợp từ morphine. Khối lượng heroin là một trong những căn cứ định khung quan trọng, mức cao nhất có thể đến tù chung thân hoặc tử hình."],
  [["cocaine", "cocain", "côcain"],
    "Cocaine – chất ma túy nhóm kích thích chiết xuất từ lá côca, thuộc danh mục chất ma túy bị cấm tuyệt đối."],
  [["ketamine", "ke ", "hàng khay", "khay"],
    "Ketamine (\"ke\") – chất hướng thần bị kiểm soát, thường xuất hiện trong các vụ tổ chức sử dụng/sử dụng trái phép chất ma túy."],
  [["mdma", "thuốc lắc", "ecstasy", "kẹo", "hồng phiến"],
    "MDMA (thuốc lắc, ecstasy) – chất ma túy tổng hợp nhóm kích thích – gây ảo giác, thường gặp trong các vụ tổ chức/sử dụng trái phép chất ma túy."],
  [["amphetamine"],
    "Amphetamine – chất ma túy tổng hợp nhóm kích thích (ATS), thường xác định qua kết luận giám định."],
  [["cần sa tổng hợp", "cỏ mỹ", "thảo mộc phun"],
    "Cần sa tổng hợp (\"cỏ Mỹ\") – nhóm chất kích thích thần kinh tổng hợp (synthetic cannabinoids) được phun tẩm lên thảo mộc, độc tính cao hơn cần sa tự nhiên."],
  [["cần sa", "cannabis", "marijuana", "bồ đà", "tài mà", "cỏ", "thảo mộc khô"],
    "Cần sa (cannabis) – chất ma túy có nguồn gốc thực vật chứa hoạt chất THC, gồm lá, hoa, quả khô; thường gặp trong các vụ trồng, tàng trữ, sử dụng trái phép."],
  [["nhựa thuốc phiện", "thuốc phiện", "opium", "anh túc"],
    "Thuốc phiện / nhựa thuốc phiện (opium) – chất ma túy nhóm opioid tự nhiên chiết từ cây thuốc phiện (anh túc)."],
  [["morphine", "morphin"],
    "Morphine – chất ma túy nhóm opioid. Lưu ý: nếu chỉ phát hiện qua test nước tiểu hoặc do điều trị y tế thì cần đối chiếu kết luận giám định, không đương nhiên cấu thành tội phạm."],
  [["ghb", "nước vui"],
    "GHB (\"nước vui\") – chất hướng thần dạng lỏng bị kiểm soát, thường gặp trong các vụ sử dụng trái phép chất ma túy."],
  [["cathinone", "muối tắm"],
    "Cathinone tổng hợp (\"muối tắm\") – nhóm chất kích thích tổng hợp mới, bị đưa vào danh mục chất ma túy bị kiểm soát."],
];

function getDrugDetail(value) {
  const text = normalizeText(value);
  for (const [keys, desc] of DRUG_TABLE) {
    if (keys.some((k) => text.includes(k))) return desc;
  }
  return "Chất ma túy được nhận diện trong nội dung bản án hoặc kết luận giám định. Khối lượng và hàm lượng là căn cứ định khung hình phạt theo Bộ luật Hình sự.";
}

// ---------------------------------------------------------------------------
// 3) TỘI DANH  (gắn với điều luật + cấu thành cơ bản)
//     Đặt cụm dài/đặc thù TRƯỚC cụm ngắn để tránh khớp nhầm.
// ---------------------------------------------------------------------------
const CHARGE_TABLE = [
  [["trồng cây", "trồng cần sa", "trồng thuốc phiện", "trồng cây thuốc phiện"],
    "Tội trồng cây thuốc phiện, cây côca, cây cần sa hoặc các loại cây khác có chứa chất ma túy (Điều 247 BLHS) – áp dụng khi đã được giáo dục, xử phạt hành chính hoặc thuộc các trường hợp luật định mà vẫn trồng."],
  [["tiền chất"],
    "Tội tàng trữ, vận chuyển, mua bán hoặc chiếm đoạt tiền chất dùng vào việc sản xuất trái phép chất ma túy (Điều 253 BLHS)."],
  [["phương tiện", "dụng cụ"],
    "Tội sản xuất, tàng trữ, vận chuyển hoặc mua bán phương tiện, dụng cụ dùng vào việc sản xuất hoặc sử dụng trái phép chất ma túy (Điều 254 BLHS)."],
  [["tổ chức sử dụng"],
    "Tội tổ chức sử dụng trái phép chất ma túy (Điều 255 BLHS) – áp dụng khi người phạm tội chỉ huy, phân công, điều hành, chuẩn bị địa điểm, phương tiện hoặc rủ rê người khác cùng sử dụng trái phép chất ma túy."],
  [["chứa chấp"],
    "Tội chứa chấp việc sử dụng trái phép chất ma túy (Điều 256 BLHS) – áp dụng khi cho người khác mượn, thuê địa điểm thuộc quyền quản lý của mình để sử dụng trái phép chất ma túy."],
  [["cưỡng bức"],
    "Tội cưỡng bức người khác sử dụng trái phép chất ma túy (Điều 257 BLHS) – dùng vũ lực, đe dọa hoặc thủ đoạn khác buộc người khác phải sử dụng trái phép chất ma túy."],
  [["lôi kéo", "dụ dỗ"],
    "Tội lôi kéo người khác sử dụng trái phép chất ma túy (Điều 258 BLHS) – rủ rê, dụ dỗ, xúi giục hoặc bằng thủ đoạn khác khiến người khác sử dụng trái phép chất ma túy."],
  [["sử dụng trái phép", "sử dụng ma túy"],
    "Tội sử dụng trái phép chất ma túy (Điều 256a BLHS, bổ sung năm 2025) – áp dụng với người đang trong thời gian quản lý sau cai, cai nghiện hoặc điều trị nghiện mà vẫn tiếp tục sử dụng trái phép chất ma túy."],
  [["tàng trữ"],
    "Tội tàng trữ trái phép chất ma túy (Điều 249 BLHS) – cất giữ, cất giấu, mang theo hoặc quản lý trái phép chất ma túy mà không nhằm mục đích mua bán, vận chuyển hay sản xuất."],
  [["vận chuyển"],
    "Tội vận chuyển trái phép chất ma túy (Điều 250 BLHS) – dịch chuyển trái phép chất ma túy từ nơi này đến nơi khác dưới bất kỳ hình thức nào."],
  [["mua bán"],
    "Tội mua bán trái phép chất ma túy (Điều 251 BLHS) – mua, bán, vận chuyển/tàng trữ để bán lại, trao đổi hoặc dùng tài sản trái phép để giao dịch chất ma túy."],
  [["chiếm đoạt"],
    "Tội chiếm đoạt chất ma túy (Điều 252 BLHS) – cướp, cưỡng đoạt, trộm cắp, lừa đảo hoặc thủ đoạn khác để chiếm đoạt chất ma túy."],
  [["sản xuất"],
    "Tội sản xuất trái phép chất ma túy (Điều 248 BLHS) – làm ra, điều chế, chiết xuất hoặc tạo ra chất ma túy bằng bất kỳ phương pháp nào."],
];

function getChargeDetail(value) {
  const text = normalizeText(value);
  for (const [keys, desc] of CHARGE_TABLE) {
    if (keys.some((k) => text.includes(k))) return desc;
  }
  return "Tội danh được Tòa án xác định trong phần quyết định của bản án.";
}

// ---------------------------------------------------------------------------
function getEntityDetail(type, value) {
  if (type === "LEGAL_ARTICLE") return getLegalArticleDetail(value);
  if (type === "DRUG") return getDrugDetail(value);
  if (type === "CHARGE") return getChargeDetail(value);
  return "";
}

function detailGroups(entities) {
  const detailTypes = ["LEGAL_ARTICLE", "DRUG", "CHARGE"];

  return detailTypes
    .map((type) => {
      const rows = uniqueEntityWords(entities?.[type] || [])
        .map((word, index) => ({
          index: index + 1,
          type,
          value: capitalizeVietnameseSentence(word),
          detail: getEntityDetail(type, word),
        }))
        .filter((row) => row.detail);

      return {
        type,
        title: getTypeTitle(type),
        rows,
      };
    })
    .filter((group) => group.rows.length > 0);
}

function DetailGroupTable({ group }) {
  return (
    <section
      style={{
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        overflow: "hidden",
        marginBottom: 20,
      }}
    >
      <div
        style={{
          padding: "14px 18px",
          background: "#f3f4f6",
          borderBottom: "1px solid #e5e7eb",
          textAlign: "left",
        }}
      >
        <div
          style={{
            fontSize: 20,
            fontWeight: 900,
            color: "#111827",
            lineHeight: 1.3,
          }}
        >
          {group.title}
        </div>
      </div>

      <div style={{ width: "100%", overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 15,
            color: "#111827",
            textAlign: "left",
          }}
        >
          <thead>
            <tr>
              <th
                style={{
                  width: 70,
                  padding: "11px 14px",
                  borderBottom: "1px solid #e5e7eb",
                  background: "#fafafa",
                  color: "#374151",
                  fontWeight: 850,
                  textAlign: "left",
                }}
              >
                STT
              </th>

              <th
                style={{
                  width: 260,
                  padding: "11px 14px",
                  borderBottom: "1px solid #e5e7eb",
                  background: "#fafafa",
                  color: "#374151",
                  fontWeight: 850,
                  textAlign: "left",
                }}
              >
                Thông tin
              </th>

              <th
                style={{
                  padding: "11px 14px",
                  borderBottom: "1px solid #e5e7eb",
                  background: "#fafafa",
                  color: "#374151",
                  fontWeight: 850,
                  textAlign: "left",
                }}
              >
                Giải thích
              </th>
            </tr>
          </thead>

          <tbody>
            {group.rows.map((row, index) => (
              <tr key={`${group.type}-${row.value}-${index}`}>
                <td
                  style={{
                    padding: "12px 14px",
                    borderBottom:
                      index === group.rows.length - 1 ? "none" : "1px solid #e5e7eb",
                    verticalAlign: "top",
                    color: "#374151",
                    background: index % 2 === 0 ? "#ffffff" : "#fafafa",
                    fontWeight: 700,
                  }}
                >
                  {row.index}
                </td>

                <td
                  style={{
                    padding: "12px 14px",
                    borderBottom:
                      index === group.rows.length - 1 ? "none" : "1px solid #e5e7eb",
                    verticalAlign: "top",
                    color: "#111827",
                    background: index % 2 === 0 ? "#ffffff" : "#fafafa",
                    lineHeight: 1.6,
                    fontWeight: 700,
                  }}
                >
                  {row.value}
                </td>

                <td
                  style={{
                    padding: "12px 14px",
                    borderBottom:
                      index === group.rows.length - 1 ? "none" : "1px solid #e5e7eb",
                    verticalAlign: "top",
                    color: "#4b5563",
                    background: index % 2 === 0 ? "#ffffff" : "#fafafa",
                    lineHeight: 1.65,
                    fontWeight: 500,
                  }}
                >
                  {row.detail}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DetailPanel({ entities }) {
  const groups = detailGroups(entities);

  return (
    <div
      style={{
        ...baseFont,
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: 16,
        padding: "26px 28px",
        textAlign: "left",
        boxShadow: "0 10px 28px rgba(15, 23, 42, 0.06)",
      }}
    >
      <div
        style={{
          fontSize: 24,
          fontWeight: 950,
          color: "#111827",
          marginBottom: 8,
          textAlign: "left",
          letterSpacing: "-0.01em",
        }}
      >
        Chi tiết thông tin nhận diện
      </div>

      <div
        style={{
          color: "#6b7280",
          fontSize: 15,
          lineHeight: 1.6,
          marginBottom: 20,
        }}
      >
        Phần này giải thích ý nghĩa của điều luật, loại ma túy và tội danh được hệ thống nhận diện.
      </div>

      {groups.length === 0 ? (
        <div style={{ color: "#9ca3af", fontSize: 16, textAlign: "left", lineHeight: 1.65 }}>
          Không có điều luật, loại ma túy hoặc tội danh để hiển thị chi tiết.
        </div>
      ) : (
        groups.map((group) => <DetailGroupTable key={group.type} group={group} />)
      )}
    </div>
  );
}


// ===========================================================================
//  XUẤT / TẢI KẾT QUẢ  (PDF qua cửa sổ in – font tiếng Việt chuẩn; TXT; JSON)
// ===========================================================================
const EXPORT_ROWS = [
  ["PERSON", "Tên bị cáo"],
  ["CHARGE", "Tội danh"],
  ["LEGAL_ARTICLE", "Điều luật"],
  ["SENTENCE", "Hình phạt"],
  ["DRUG", "Loại ma túy"],
  ["DRUG_WEIGHT", "Khối lượng ma túy"],
  ["CRIME_TIME", "Thời gian phạm tội"],
  ["CRIME_LOC", "Địa điểm phạm tội"],
];

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function baseFileName(result) {
  const name = String(result?.filename || "ket_qua_ner").replace(/\.pdf$/i, "");
  return name.replace(/[^\p{L}\p{N}_-]+/gu, "_").slice(0, 80) || "ket_qua_ner";
}

function triggerDownload(content, filename, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function buildReportText(result) {
  const entities = result?.entities || {};
  const lines = [];
  lines.push("KET QUA NHAN DIEN THUC THE - BAN AN HINH SU MA TUY");
  lines.push("=".repeat(60));
  lines.push("File: " + (result?.filename || ""));
  lines.push("Mo hinh: " + (result?.model_display_name || result?.model_name || "PhoBERT"));
  lines.push("");
  lines.push("TOM TAT THUC THE");
  lines.push("-".repeat(60));
  EXPORT_ROWS.forEach(([type, label]) => {
    const words = uniqueEntityWords(entities[type] || []);
    lines.push(label + ": " + (words.length ? words.join("; ") : "Khong tim thay"));
  });
  lines.push("");
  lines.push("VAN BAN NHAN DIEN");
  lines.push("-".repeat(60));
  lines.push(flattenHighlighted(result?.highlighted || []).text);
  return lines.join("\n");
}

function buildReportHTML(result, selectedModel) {
  const entities = result?.entities || {};
  const model = escapeHtml(result?.model_display_name || result?.model_name || selectedModel || "PhoBERT");
  const filename = escapeHtml(result?.filename || "");

  const summaryRows = EXPORT_ROWS.map(([type, label], i) => {
    const words = uniqueEntityWords(entities[type] || []);
    const cell = words.length
      ? words.map((w) => escapeHtml(w)).join("<br/>")
      : '<span class="muted">Không tìm thấy</span>';
    return `<tr class="${i % 2 ? "alt" : ""}"><td class="lbl">${escapeHtml(label)}</td><td>${cell}</td></tr>`;
  }).join("");

  const groups = detailGroups(entities);
  const detailHTML = groups.length
    ? groups.map((g) =>
        `<h3>${escapeHtml(g.title)}</h3>` +
        g.rows.map((r) =>
          `<div class="detail"><div class="dt-name">${escapeHtml(r.value)}</div>` +
          `<div class="muted">${escapeHtml(r.detail)}</div></div>`
        ).join("")
      ).join("")
    : '<p class="muted">Không có dữ liệu chi tiết.</p>';

  const merged = flattenHighlighted(result?.highlighted || []);
  const fullText = escapeHtml(merged.text).replace(/\n/g, "<br/>");
  const now = new Date().toLocaleString("vi-VN");

  return `<!doctype html>
<html lang="vi"><head><meta charset="utf-8"/>
<title>Kết quả NER - ${filename}</title>
<style>
  @page { size: A4; margin: 18mm 16mm; }
  * { box-sizing: border-box; }
  body {
    font-family: "Times New Roman", "Be Vietnam Pro", "DejaVu Serif", Arial, sans-serif;
    color: #111827; font-size: 13.5pt; line-height: 1.55; margin: 0;
  }
  h1 { font-size: 18pt; text-align: center; margin: 0 0 4px; }
  .sub { text-align: center; color: #4b5563; font-size: 11pt; margin-bottom: 18px; }
  h2 { font-size: 14pt; border-bottom: 2px solid #1f2937; padding-bottom: 4px; margin: 22px 0 10px; }
  h3 { font-size: 12.5pt; margin: 14px 0 6px; color: #1f2937; }
  table { width: 100%; border-collapse: collapse; margin-top: 6px; }
  td { border: 1px solid #cbd5e1; padding: 7px 10px; vertical-align: top; }
  td.lbl { width: 34%; font-weight: bold; background: #f1f5f9; }
  tr.alt td { background: #f9fafb; }
  .muted { color: #6b7280; }
  .detail { margin-bottom: 8px; }
  .dt-name { font-weight: bold; }
  .fulltext { border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px 14px; text-align: justify; }
  .foot { margin-top: 18px; font-size: 10pt; color: #9ca3af; text-align: right; }
</style></head>
<body>
  <h1>KẾT QUẢ NHẬN DIỆN THỰC THỂ</h1>
  <div class="sub">Bản án hình sự ma túy &middot; File: ${filename} &middot; Mô hình: ${model}</div>

  <h2>1. Tóm tắt thực thể</h2>
  <table><tbody>${summaryRows}</tbody></table>

  <h2>2. Chi tiết điều luật, loại ma túy và tội danh</h2>
  ${detailHTML}

  <h2>3. Văn bản được nhận diện</h2>
  <div class="fulltext">${fullText || '<span class="muted">Không có nội dung.</span>'}</div>

  <div class="foot">Xuất ngày ${escapeHtml(now)} &middot; Hệ thống Drug NER PhoBERT</div>
</body></html>`;
}

function exportResultPDF(result, selectedModel) {
  const html = buildReportHTML(result, selectedModel);
  const win = window.open("", "_blank", "width=900,height=1000");
  if (!win) {
    alert("Trình duyệt đã chặn cửa sổ in. Vui lòng cho phép pop-up rồi thử lại để lưu PDF.");
    return;
  }
  win.document.open();
  win.document.write(html);
  win.document.close();
  win.focus();
  const doPrint = () => {
    win.focus();
    win.print();
  };
  if (win.document.readyState === "complete") setTimeout(doPrint, 500);
  else win.onload = () => setTimeout(doPrint, 500);
}

export default function NerResult({ result, selectedModel, pdfUrl, onReset }) {
  const [tab, setTab] = useState("highlight");
  const entities = result?.entities || {};

  const exportBtnStyle = {
    border: "1px solid #cbd5e1",
    background: "#ffffff",
    color: "#111827",
    borderRadius: 8,
    padding: "7px 14px",
    fontSize: 13,
    fontWeight: 750,
    cursor: "pointer",
  };

  const tabs = [
    { key: "highlight", label: "Văn bản nhận diện" },
    { key: "pdf", label: "Xem PDF" },
    { key: "summary", label: "Tóm tắt" },
    { key: "detail", label: "Chi tiết" },
  ];

  return (
    <div style={baseFont}>
      <div style={{ ...styles.fileBar, ...baseFont }}>
        <span style={{ fontSize: 18, fontWeight: 900 }}>PDF</span>
        <span style={{ fontWeight: 800 }}>{result.filename}</span>
        <span style={{ color: "#6b7280", fontSize: 13 }}>
          · Model: {result.model_display_name || result.model_name || "PhoBERT"}
        </span>
        <span style={{ color: "#6b7280", fontSize: 13 }}>· {result.elapsed_ms}ms</span>
        <div style={styles.totalBadge}>{countEntities(entities)} thực thể</div>
        <div style={{ display: "flex", gap: 8, marginLeft: "auto", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => exportResultPDF(result, selectedModel)}
            style={exportBtnStyle}
            title="Mở bản in và lưu thành PDF (hỗ trợ tiếng Việt)"
          >
            Tải PDF
          </button>
          <button
            type="button"
            onClick={() =>
              triggerDownload(
                "\uFEFF" + buildReportText(result),
                baseFileName(result) + ".txt",
                "text/plain;charset=utf-8"
              )
            }
            style={exportBtnStyle}
          >
            Tải TXT
          </button>
          <button
            type="button"
            onClick={() =>
              triggerDownload(
                JSON.stringify(result?.entities || {}, null, 2),
                baseFileName(result) + ".json",
                "application/json;charset=utf-8"
              )
            }
            style={exportBtnStyle}
          >
            Tải JSON
          </button>
          <button type="button" onClick={onReset} style={styles.resetBtn}>
            Phân tích file khác
          </button>
        </div>
      </div>

      <div style={styles.tabs}>
        {tabs.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setTab(item.key)}
            style={{ ...styles.tab, ...(tab === item.key ? styles.tabActive : {}) }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "highlight" && <RecognizedTextPanel highlighted={result.highlighted} />}
      {tab === "pdf" && <PdfPanel pdfUrl={pdfUrl} result={result} />}
      {tab === "summary" && <SummaryPanel entities={entities} />}
      {tab === "detail" && <DetailPanel entities={entities} />}
    </div>
  );
}