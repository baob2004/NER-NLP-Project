import { ENTITY_CONFIG } from "../config";
import { styles } from "../styles";

export default function HomePage({ onNavigate }) {
  const activeLabels = Object.values(ENTITY_CONFIG).filter((x) => x.enabled);

  return (
    <div style={styles.page}>
      <section style={styles.homeHeroClean}>
        <div style={styles.homeHeroContent}>
          <div style={styles.homeEyebrow}>ĐỒ ÁN NER BẢN ÁN HÌNH SỰ MA TÚY</div>
          <h1 style={styles.homeTitle}>Nhận diện thực thể trong bản án tiếng Việt</h1>
          <p style={styles.homeLead}>
            Tải lên bản án PDF, hệ thống trích xuất văn bản và đánh dấu các thực thể phục vụ nghiên cứu, gán nhãn và đánh giá mô hình PhoBERT.
          </p>
          <div style={styles.heroActions}>
            <button type="button" style={styles.primaryBtn} onClick={() => onNavigate("analyze")}>
              Phân tích bản án
            </button>
            <button type="button" style={styles.secondaryBtnLight} onClick={() => onNavigate("guideline")}>
              Xem guideline
            </button>
          </div>
        </div>
      </section>

      <section style={styles.homeQuickPanel}>
        <div style={styles.homeQuickItem}>
          <span style={styles.homeQuickLabel}>Bước 1</span>
          <strong style={styles.homeQuickTitle}>Chọn model</strong>
          <p style={styles.homeQuickText}>Chọn phiên bản model đã train trong backend.</p>
        </div>
        <div style={styles.homeQuickItem}>
          <span style={styles.homeQuickLabel}>Bước 2</span>
          <strong style={styles.homeQuickTitle}>Tải PDF</strong>
          <p style={styles.homeQuickText}>Upload bản án hình sự ma túy cần phân tích.</p>
        </div>
        <div style={styles.homeQuickItem}>
          <span style={styles.homeQuickLabel}>Bước 3</span>
          <strong style={styles.homeQuickTitle}>Xem kết quả</strong>
          <p style={styles.homeQuickText}>Kiểm tra highlight, tóm tắt và danh sách thực thể.</p>
        </div>
      </section>

      <section style={styles.homeBottomGrid}>
        <div style={styles.homePlainCard}>
          <h2 style={styles.homeCardTitle}>Nhóm nhãn đang sử dụng</h2>
          <div style={styles.labelListCompact}>
            {activeLabels.map((cfg) => (
              <span
                key={cfg.short}
                style={{
                  ...styles.labelPillPlain,
                  borderColor: `${cfg.color}55`,
                  color: cfg.color,
                  background: cfg.bg,
                }}
              >
                {cfg.short} · {cfg.label}
              </span>
            ))}
          </div>
        </div>

        <div style={styles.homePlainCard}>
          <h2 style={styles.homeCardTitle}>Nguồn dữ liệu tham khảo</h2>
          <p style={styles.homeCardText}>
            Trang nguồn liên quan tổng hợp các địa chỉ tra cứu bản án và văn bản pháp luật phục vụ đề tài.
          </p>
          <button type="button" style={styles.linkLikeBtn} onClick={() => onNavigate("resources")}>
            Mở trang nguồn liên quan
          </button>
        </div>
      </section>
    </div>
  );
}
