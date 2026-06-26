import { NAV_ITEMS, SITE_COVER_IMAGE } from "../config";
import { styles } from "../styles";

function Header({ currentPage, onNavigate }) {
  return (
    <header style={styles.header}>
      <div style={styles.headerTopLine} />

      <div style={styles.govMasthead}>
        <div style={styles.govMastheadInner}>
          <img
            src={SITE_COVER_IMAGE}
            alt="Ảnh bìa hệ thống"
            style={styles.govLogoImage}
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
          <div style={styles.govTitleBlock}>
            <div style={styles.govKicker}>HỆ THỐNG NHẬN DIỆN THỰC THỂ BẢN ÁN HÌNH SỰ MA TÚY</div>
            <div style={styles.govMainTitle}>DRUG NER</div>
            <div style={styles.govMeta}>Xử lý PDF · Highlight thực thể · Hỗ trợ nghiên cứu bản án tiếng Việt</div>
          </div>
        </div>
      </div>

      <div style={styles.navbarWrap}>
        <nav style={styles.topNav}>
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => onNavigate(item.key)}
              style={{ ...styles.topNavBtn, ...(currentPage === item.key ? styles.topNavBtnActive : {}) }}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer style={styles.footer}>
      <div style={styles.footerInner}>
        <span><strong>Drug NER PhoBERT</strong> · Nhận diện thực thể trong bản án hình sự ma túy</span>
        <span>FastAPI · React · Vietnamese Legal NER</span>
        <span>© {new Date().getFullYear()} · v1.2</span>
      </div>
    </footer>
  );
}

export default function Layout({ currentPage, onNavigate, children }) {
  return (
    <div style={styles.appShell}>
      <Header currentPage={currentPage} onNavigate={onNavigate} />
      <main style={styles.main}>{children}</main>
      <Footer />
    </div>
  );
}
