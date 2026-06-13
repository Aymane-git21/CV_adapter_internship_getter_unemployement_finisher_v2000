import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { AuthModal } from "./components/AuthModal";
import { Nav } from "./components/Nav";
import { useSession } from "./store";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import Pricing from "./pages/Pricing";
import Settings from "./pages/Settings";
import Studio from "./pages/Studio";

export default function App() {
  const bootstrap = useSession((s) => s.bootstrap);
  const location = useLocation();

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const inStudio = location.pathname.startsWith("/studio");

  return (
    <div className="flex h-full flex-col">
      <Nav />
      <main className={inStudio ? "min-h-0 flex-1" : "flex-1 overflow-y-auto"}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/studio" element={<Studio />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Landing />} />
        </Routes>
      </main>
      <AuthModal />
    </div>
  );
}
