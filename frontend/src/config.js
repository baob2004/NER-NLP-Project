export const API = import.meta.env.VITE_API_URL ?? "";

// Đổi ảnh bìa/logo đầu trang tại đây.
// Cách dùng: đặt ảnh của bạn vào thư mục public, ví dụ public/banner.png,
// rồi đổi SITE_COVER_IMAGE thành "/banner.png".
export const SITE_COVER_IMAGE = "/banner.png";

export const ENTITY_CONFIG = {
  PERSON: {
    label: "Bị cáo",
    short: "PERSON",
    color: "#dc2626", // đỏ
    bg: "#fee2e2",
    icon: "👤",
    enabled: true,
  },

  CHARGE: {
    label: "Tội danh",
    short: "CHARGE",
    color: "#9333ea", // tím
    bg: "#f3e8ff",
    icon: "⚖️",
    enabled: true,
  },

  LEGAL_ARTICLE: {
    label: "Điều luật",
    short: "LEGAL_ARTICLE",
    color: "#2563eb", // xanh dương
    bg: "#dbeafe",
    icon: "📜",
    enabled: true,
  },

  SENTENCE: {
    label: "Hình phạt",
    short: "SENTENCE",
    color: "#111827", // đen/xám đậm
    bg: "#e5e7eb",
    icon: "🔒",
    enabled: true,
  },

  DRUG: {
    label: "Loại ma túy",
    short: "DRUG",
    color: "#059669", // xanh ngọc
    bg: "#d1fae5",
    icon: "💊",
    enabled: true,
  },

  DRUG_WEIGHT: {
    label: "Khối lượng",
    short: "DRUG_WEIGHT",
    color: "#ea580c", // cam
    bg: "#ffedd5",
    icon: "⚗️",
    enabled: true,
  },

  CRIME_TIME: {
    label: "Thời gian phạm tội",
    short: "CRIME_TIME",
    color: "#0891b2", // cyan
    bg: "#cffafe",
    icon: "🕒",
    enabled: true,
  },

  CRIME_LOC: {
    label: "Địa điểm phạm tội",
    short: "CRIME_LOC",
    color: "#65a30d", // lime
    bg: "#ecfccb",
    icon: "📍",
    enabled: true,
  },
};

export const SECTION_LABELS = {
  noi_dung:   "Nội dung vụ án",
  nhan_dinh:  "Nhận định của Tòa án",
  quyet_dinh: "Quyết định",
};

export const NAV_ITEMS = [
  { key: "home", label: "Trang chủ" },
  { key: "history", label: "Lịch sử" },   
  { key: "guideline", label: "Guideline" },
  { key: "resources", label: "Nguồn liên quan" },
];
