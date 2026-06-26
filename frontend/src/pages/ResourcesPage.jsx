import { styles } from "../styles";

const FONT =
  '"Be Vietnam Pro", "Inter", "Segoe UI", Roboto, Arial, sans-serif';

const RESOURCES = [
  {
    title: "Công bố bản án, quyết định của Tòa án",
    url: "https://congbobanan.toaan.gov.vn/",
    desc: "Nguồn chính để tìm và tải bản án hình sự ma túy phục vụ thu thập dữ liệu, lọc đoạn và gán nhãn NER.",
  },
  {
    title: "Cơ sở dữ liệu quốc gia về văn bản pháp luật",
    url: "https://vbpl.vn/",
    desc: "Tra cứu văn bản pháp luật chính thống, gồm Bộ luật Hình sự và các văn bản liên quan.",
  },
  {
    title: "Văn bản pháp quy Tòa án",
    url: "https://vbpq.toaan.gov.vn/",
    desc: "Nguồn tham khảo văn bản pháp quy, nghị quyết và hướng dẫn nghiệp vụ của hệ thống Tòa án.",
  },
  {
    title: "Hệ thống văn bản Chính phủ",
    url: "https://chinhphu.vn/he-thong-van-ban",
    desc: "Tra cứu luật, nghị định, quyết định và văn bản liên quan đến quản lý nhà nước, phòng chống ma túy.",
  },
];

const pageStyle = {
  ...styles.page,
  fontFamily: FONT,
  color: "#111827",
  maxWidth: 1050,
  margin: "0 auto",
  padding: "42px 24px 56px",
  textAlign: "left",
};

const titleStyle = {
  fontSize: 30,
  fontWeight: 900,
  lineHeight: 1.25,
  margin: "0 0 10px",
  textAlign: "left",
};

const descStyle = {
  fontSize: 15,
  lineHeight: 1.7,
  color: "#4b5563",
  margin: "0 0 26px",
  maxWidth: 780,
  textAlign: "left",
};

function ResourceRow({ item, index }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "48px 1fr 120px",
        gap: 16,
        alignItems: "start",
        padding: "18px 0",
        borderTop: index === 0 ? "none" : "1px solid #e5e7eb",
      }}
    >
      <div
        style={{
          color: "#6b7280",
          fontWeight: 850,
          fontSize: 14,
          lineHeight: 1.6,
        }}
      >
        {String(index + 1).padStart(2, "0")}
      </div>

      <div>
        <div
          style={{
            fontSize: 17,
            fontWeight: 850,
            color: "#111827",
            lineHeight: 1.45,
            marginBottom: 5,
          }}
        >
          {item.title}
        </div>

        <div
          style={{
            fontSize: 14,
            lineHeight: 1.65,
            color: "#4b5563",
          }}
        >
          {item.desc}
        </div>
      </div>

      <a
        href={item.url}
        target="_blank"
        rel="noreferrer"
        style={{
          justifySelf: "end",
          textDecoration: "none",
          color: "#111827",
          border: "1px solid #d1d5db",
          borderRadius: 8,
          padding: "8px 12px",
          fontSize: 13,
          fontWeight: 750,
          background: "#ffffff",
          whiteSpace: "nowrap",
        }}
      >
        Mở trang
      </a>
    </div>
  );
}

export default function ResourcesPage() {
  return (
    <div style={pageStyle}>
      <h1 style={titleStyle}>Thông tin bản án và nguồn luật</h1>

      <p style={descStyle}>
        Các nguồn cần thiết để thu thập bản án và đối chiếu điều luật, tội danh trong bài toán NER bản án hình sự ma túy.
      </p>

      <section
        style={{
          background: "#ffffff",
          border: "1px solid #e5e7eb",
          borderRadius: 14,
          padding: "6px 24px",
          boxShadow: "0 8px 24px rgba(15, 23, 42, 0.04)",
        }}
      >
        {RESOURCES.map((item, index) => (
          <ResourceRow key={item.url} item={item} index={index} />
        ))}
      </section>
    </div>
  );
}
