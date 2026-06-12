import { Link } from "react-router-dom";
import { useI18n } from "../i18n";

export default function Landing() {
  const { t } = useI18n();
  return (
    <div className="grid min-h-[70vh] place-items-center p-8 text-center">
      <div>
        <p className="eyebrow mb-3">CV Glowup</p>
        <h1 className="mb-6 font-serif text-4xl font-semibold">Landing — Phase 3</h1>
        <Link to="/studio" className="rounded-md bg-blue-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-400">
          {t("nav.start")}
        </Link>
      </div>
    </div>
  );
}
