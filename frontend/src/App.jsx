import { useEffect, useState } from "react";
import Layout from "./components/Layout";
import AnalyzePage from "./pages/AnalyzePage";
import GuidelinePage from "./pages/GuidelinePage";
import ResourcesPage from "./pages/ResourcesPage";
import { styles } from "./styles";
import HistoryPage from "./pages/HistoryPage";
function AppPage({ page, onNavigate }) {
  if (page === "home") return <AnalyzePage />;
  if (page === "guideline") return <GuidelinePage />;
  if (page === "resources") return <ResourcesPage />;
  if (page == "history") return <HistoryPage/>;
  return <AnalyzePage />;
}

export default function App() {
  const [page, setPage] = useState("home");

  useEffect(() => {
    if (typeof document === "undefined") return;

    const style = document.createElement("style");
    style.textContent = `
      * { box-sizing: border-box; }
      html, body, #root { margin: 0; min-height: 100%; width: 100%; }
      @keyframes spin { to { transform: rotate(360deg); } }
      button:hover { opacity: 0.9; }
      a:hover { text-decoration: underline; }
      @media (max-width: 980px) {
        main { padding: 18px !important; }
        nav { justify-content: flex-start !important; padding: 0 16px !important; }
        nav button { padding-left: 12px !important; padding-right: 12px !important; font-size: 12px !important; }
      }
      @media (max-width: 860px) {
        div[style*="grid-template-columns: repeat(3"] { grid-template-columns: 1fr !important; }
        div[style*="grid-template-columns: repeat(2"] { grid-template-columns: 1fr !important; }
        div[style*="height: calc(100vh"] { height: auto !important; flex-direction: column !important; }
        iframe { min-height: 520px; }
      }
      @media (max-width: 720px) {
        img[alt="Ảnh bìa hệ thống"] { width: 72px !important; height: 72px !important; }
      }
    `;
    document.head.appendChild(style);
    return () => document.head.removeChild(style);
  }, []);

  return (
    <div style={styles.root}>
      <Layout currentPage={page} onNavigate={setPage}>
        <AppPage page={page} onNavigate={setPage} />
      </Layout>
    </div>
  );
}
