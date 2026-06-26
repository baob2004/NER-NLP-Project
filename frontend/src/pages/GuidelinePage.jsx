import { styles } from "../styles";

const FONT =
  '"Be Vietnam Pro", "Inter", "Segoe UI", Roboto, Arial, sans-serif';

const LABELS = [
  {
    title: "PERSON",
    name: "Bị cáo",
    shortRule: "Tên bị cáo trong bản án hiện tại.",
    do: [
      "Gán tên đầy đủ của bị cáo.",
      "Gán alias hoặc biến thể tên nếu thể hiện rõ là bị cáo.",
      "Có thể gán tên dạng “Bùi Phúc T”, “Trần Thanh L”.",
    ],
    dont: [
      "Không gán bị hại, nhân chứng, công an, kiểm sát viên, thẩm phán.",
      "Không gán chữ viết tắt đứng riêng như T, H, N1.",
    ],
  },
  {
    title: "DRUG",
    name: "Loại ma túy",
    shortRule: "Tên chất ma túy cụ thể liên quan trực tiếp đến vụ án.",
    do: [
      "Gán Heroine/Heroin, Methamphetamine, Ketamine, MDMA, cần sa, thuốc lắc, hồng phiến, ma túy đá.",
    ],
    dont: [
      "Không gán từ chung như “ma túy”, “chất ma túy”.",
      "Không gán chất chỉ xuất hiện trong test nước tiểu nếu không liên quan tang vật chính.",
    ],
  },
  {
    title: "DRUG_WEIGHT",
    name: "Khối lượng ma túy",
    shortRule: "Khối lượng ma túy dùng cho kết luận/phán quyết.",
    do: [
      "Gán số đo như 0,2 gam, 29,1634 g, 200 mg, 1 kg.",
    ],
    dont: [
      "Không gán số lượng bao gói như 01 gói, 02 viên, 01 túi nilon.",
      "Không gán mẫu hoàn lại sau giám định nếu không dùng để kết luận tội danh.",
    ],
  },
  {
    title: "CRIME_TIME",
    name: "Thời gian phạm tội",
    shortRule: "Mốc ngày/giờ của hành vi phạm tội hoặc lúc bắt quả tang.",
    do: [
      "Gán mốc cụ thể như “khoảng 13 giờ ngày 07/10/2025”.",
      "Nếu nhiều ngày cụ thể liên tiếp, gán từng ngày riêng.",
    ],
    dont: [
      "Không gán ngày xét xử, ngày cáo trạng, ngày kết luận giám định.",
      "Không gán mốc mơ hồ như “cùng ngày”, “sau đó”, “hôm sau”.",
    ],
  },
  {
    title: "CRIME_LOC",
    name: "Địa điểm phạm tội",
    shortRule: "Địa điểm cụ thể của hành vi phạm tội, giao nhận, mua bán hoặc bắt quả tang.",
    do: [
      "Gán địa chỉ có tên đường, thôn, bản, xã, phường, quận, huyện, tỉnh.",
      "Ví dụ: “phòng 302 Nhà nghỉ Đại Lộc 1”, “bản Nậm Vì 1, xã Mường Nhé”.",
    ],
    dont: [
      "Không gán nơi mơ hồ như “tại đây”, “khu vực trên”.",
      "Không gán nơi cư trú/trụ sở tố tụng nếu không phải địa điểm phạm tội.",
    ],
  },
  {
    title: "CHARGE",
    name: "Tội danh",
    shortRule: "Tội danh ma túy do Tòa án kết luận hoặc tuyên bố.",
    do: [
      "Gán tội danh như Tàng trữ, Mua bán, Vận chuyển, Tổ chức sử dụng, Sử dụng trái phép chất ma túy.",
    ],
    dont: [
      "Không gán tội danh chỉ là đề nghị của Viện kiểm sát nếu Tòa chưa kết luận.",
      "Không gán tội ngoài phạm vi ma túy.",
    ],
  },
  {
    title: "LEGAL_ARTICLE",
    name: "Điều luật",
    shortRule: "Điều/khoản/điểm BLHS liên quan trực tiếp đến tội danh và hình phạt.",
    do: [
      "Gán cụm như điểm c khoản 1 Điều 249, khoản 1 Điều 255, Điều 38, Điều 55.",
    ],
    dont: [
      "Không gán BLTTHS, án phí, thi hành án, xử lý vật chứng.",
      "Không kéo dài sang tên luật nếu cụm điều khoản đã đủ rõ.",
    ],
  },
  {
    title: "SENTENCE",
    name: "Hình phạt",
    shortRule: "Hình phạt chính thức Tòa tuyên cho tội ma túy.",
    do: [
      "Gán mức tù chính thức và tiền phạt bổ sung nếu là hình phạt hình sự.",
    ],
    dont: [
      "Không gán đề nghị mức án của Viện kiểm sát.",
      "Không gán án phí, tịch thu, sung công, bồi thường.",
    ],
  },
];

const pageStyle = {
  ...styles.page,
  fontFamily: FONT,
  color: "#111827",
  width: "100%",
  maxWidth: "none",
  margin: 0,
  padding: "42px 24px 56px",
  textAlign: "left",
};

const contentStyle = {
  width: "100%",
  maxWidth: 1050,
  margin: "0 auto",
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

const panelStyle = {
  width: "100%",
  background: "#ffffff",
  border: "1px solid #e5e7eb",
  borderRadius: 14,
  padding: "4px 26px",
  textAlign: "left",
  boxShadow: "0 8px 24px rgba(15, 23, 42, 0.04)",
};

function RuleText({ label, items }) {
  return (
    <div style={{ marginTop: 14, textAlign: "left" }}>
      <div
        style={{
          fontSize: 14,
          fontWeight: 800,
          color: "#111827",
          marginBottom: 6,
          textAlign: "left",
        }}
      >
        {label}
      </div>

      <ul
        style={{
          margin: 0,
          paddingLeft: 22,
          fontSize: 14,
          lineHeight: 1.7,
          color: "#374151",
          textAlign: "left",
        }}
      >
        {items.map((item, index) => (
          <li key={`${label}-${index}`} style={{ marginBottom: 4, textAlign: "left" }}>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function GuidelineItem({ item, defaultOpen }) {
  return (
    <details
      open={defaultOpen}
      style={{
        borderTop: "1px solid #e5e7eb",
        padding: 0,
        textAlign: "left",
      }}
    >
      <summary
        style={{
          cursor: "pointer",
          listStyle: "none",
          padding: "17px 0",
          outline: "none",
          textAlign: "left",
        }}
      >
        <div style={{ textAlign: "left", width: "100%" }}>
          <div
            style={{
              fontSize: 18,
              fontWeight: 900,
              color: "#111827",
              lineHeight: 1.35,
              textAlign: "left",
            }}
          >
            {item.title} · {item.name}
          </div>

          <div
            style={{
              fontSize: 14,
              color: "#6b7280",
              marginTop: 4,
              lineHeight: 1.55,
              textAlign: "left",
            }}
          >
            {item.shortRule}
          </div>
        </div>
      </summary>

      <div style={{ paddingBottom: 20, textAlign: "left" }}>
        <RuleText label="Nên gán" items={item.do} />
        <RuleText label="Không gán" items={item.dont} />
      </div>
    </details>
  );
}

export default function GuidelinePage() {
  return (
    <div style={pageStyle}>
      <div style={contentStyle}>
        <div style={panelStyle}>
          {LABELS.map((item, index) => (
            <GuidelineItem
              key={item.title}
              item={item}
              defaultOpen={index === 0}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
