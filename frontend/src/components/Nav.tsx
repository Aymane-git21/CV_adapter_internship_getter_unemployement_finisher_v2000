import { FileText, LogOut } from "lucide-react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useI18n } from "../i18n";
import { useSession } from "../store";
import { byokStore } from "../api";

function QuotaPill() {
  const me = useSession((s) => s.me);
  const { t } = useI18n();
  if (!me) return null;
  if (byokStore.get()) {
    return (
      <span className="hidden rounded-full border border-ok-400/30 bg-ok-950 px-2.5 py-1 font-mono text-[11px] text-ok-400 sm:inline">
        {t("quota.byok")}
      </span>
    );
  }
  if (!me.authenticated) return null;
  return (
    <span className="hidden rounded-full border border-ink-700 bg-ink-900 px-2.5 py-1 font-mono text-[11px] text-fg-dim sm:inline">
      {me.quota.remaining_today}/{me.quota.daily_limit} {t("quota.left")}
    </span>
  );
}

export function Nav() {
  const { t, lang, setLang } = useI18n();
  const me = useSession((s) => s.me);
  const setAuthOpen = useSession((s) => s.setAuthOpen);
  const logout = useSession((s) => s.logout);
  const location = useLocation();

  const navCls = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm transition-colors ${
      isActive ? "bg-ink-800 text-fg" : "text-fg-dim hover:text-fg"
    }`;

  return (
    <header className="z-40 flex h-14 shrink-0 items-center justify-between border-b border-ink-800 bg-ink-950/90 px-4 backdrop-blur sm:px-6">
      <div className="flex items-center gap-6">
        <Link to="/" className="flex items-center gap-2.5" aria-label="CV Glowup home">
          <span className="grid size-7 place-items-center rounded-md bg-blue-500 text-paper">
            <FileText size={15} strokeWidth={2.4} />
          </span>
          <span className="font-serif text-[17px] font-semibold tracking-tight">
            CV<span className="text-blue-300">Glowup</span>
          </span>
        </Link>
        <nav className="hidden items-center gap-1 md:flex">
          <NavLink to="/studio" className={navCls}>{t("nav.studio")}</NavLink>
          <NavLink to="/pricing" className={navCls}>{t("nav.pricing")}</NavLink>
          {me?.authenticated && (
            <NavLink to="/dashboard" className={navCls}>{t("nav.dashboard")}</NavLink>
          )}
        </nav>
      </div>

      <div className="flex items-center gap-3">
        <QuotaPill />
        <button
          onClick={() => setLang(lang === "en" ? "fr" : "en")}
          className="rounded-md border border-ink-700 px-2 py-1 font-mono text-[11px] uppercase text-fg-dim hover:text-fg"
          aria-label="Switch language"
        >
          {lang === "en" ? "FR" : "EN"}
        </button>
        {me?.authenticated ? (
          <div className="flex items-center gap-2">
            <NavLink to="/settings" className="hidden text-sm text-fg-dim hover:text-fg sm:inline">
              {me.email?.split("@")[0]}
            </NavLink>
            <button
              onClick={() => void logout()}
              className="grid size-8 place-items-center rounded-md text-fg-dim hover:bg-ink-800 hover:text-fg"
              title={t("nav.logout")}
            >
              <LogOut size={15} />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setAuthOpen(true)}
            className="rounded-md px-3 py-1.5 text-sm text-fg-dim hover:text-fg"
          >
            {t("nav.login")}
          </button>
        )}
        {!location.pathname.startsWith("/studio") && (
          <Link
            to="/studio"
            className="rounded-md bg-blue-500 px-3.5 py-1.5 text-sm font-medium text-white shadow-[0_0_24px_-6px] shadow-blue-500/60 transition hover:bg-blue-400"
          >
            {t("nav.start")}
          </Link>
        )}
      </div>
    </header>
  );
}
