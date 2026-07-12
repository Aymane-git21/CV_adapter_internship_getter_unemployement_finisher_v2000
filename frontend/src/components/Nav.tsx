import { LogOut } from "lucide-react";
import { Link, NavLink, useLocation } from "react-router-dom";
import logoUrl from "../assets/CVglowup_logo.svg";
import { LANGS, useI18n } from "../i18n";
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
    <span className="hidden rounded-full border border-black/10 glass-panel px-2.5 py-1 font-mono text-[11px] text-text/70 sm:inline">
      {me.quota.remaining_today}/{me.quota.daily_limit} {t("quota.left")}
    </span>
  );
}

function LangSwitch() {
  const { lang, setLang } = useI18n();
  return (
    <div
      className="flex items-center rounded-full border border-black/10 glass-panel p-0.5"
      role="group"
      aria-label="Language"
    >
      {LANGS.map((l) => (
        <button
          key={l}
          onClick={() => setLang(l)}
          aria-pressed={lang === l}
          className={`rounded-full px-2 py-0.5 font-mono text-[10.5px] uppercase transition-colors ${
            lang === l ? "bg-primary text-white shadow-sm" : "text-text/60 hover:text-text"
          }`}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

export function Nav() {
  const { t } = useI18n();
  const me = useSession((s) => s.me);
  const setAuthOpen = useSession((s) => s.setAuthOpen);
  const logout = useSession((s) => s.logout);
  const location = useLocation();

  const navCls = ({ isActive }: { isActive: boolean }) =>
    `nav-underline rounded-md px-3 py-1.5 text-sm transition-colors ${
      isActive ? "text-text" : "text-text/70 hover:text-text"
    }`;

  return (
    <header className="z-40 flex h-14 shrink-0 items-center justify-between glass-panel border-b-white/40 px-4 sm:px-6">
      <div className="flex items-center gap-6">
        <Link to="/" className="group flex items-center gap-2.5" aria-label="CV Glowup home">
          <img
            src={logoUrl}
            alt=""
            className="size-9 transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-3"
          />
          <span className="font-sans text-[17px] font-bold tracking-tight">
            CV<span className="text-primary">Glowup</span>
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
        <LangSwitch />
        {me?.authenticated ? (
          <div className="flex items-center gap-2">
            <NavLink to="/settings" className="hidden text-sm text-text/70 hover:text-text sm:inline">
              {me.email?.split("@")[0]}
            </NavLink>
            <button
              onClick={() => void logout()}
              className="grid size-8 place-items-center rounded-md text-text/70 hover:bg-black/5 hover:text-text"
              title={t("nav.logout")}
            >
              <LogOut size={15} />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setAuthOpen(true)}
            className="rounded-md px-3 py-1.5 text-sm text-text/70 hover:text-text"
          >
            {t("nav.login")}
          </button>
        )}
        {!location.pathname.startsWith("/studio") && (
          <Link
            to="/studio"
            className="btn-flame rounded-lg px-3.5 py-1.5 text-sm font-semibold"
          >
            {t("nav.start")}
          </Link>
        )}
      </div>
    </header>
  );
}
