import { Globe, LogOut } from "lucide-react";
import { Link, NavLink, useLocation } from "react-router-dom";
import logoUrl from "../assets/CVglowup_logo.svg";
import { LANGS, useI18n, type Lang } from "../i18n";
import { useSession } from "../store";
import { byokStore } from "../api";

const LANG_LABELS: Record<Lang, string> = { en: "English", fr: "Français", de: "Deutsch" };

function QuotaPill({ dark }: { dark: boolean }) {
  const me = useSession((s) => s.me);
  const { t } = useI18n();
  if (!me) return null;
  if (byokStore.get()) {
    return <span className="hidden text-[12.5px] text-ok-400 sm:inline">{t("quota.byok")}</span>;
  }
  if (!me.authenticated) return null;
  const left = me.quota.remaining_today;
  // Nudge exactly when the limit becomes tangible, never before.
  const low = me.plan !== "pro" && left <= Math.max(1, Math.floor(me.quota.daily_limit * 0.15));
  return (
    <span
      className={`hidden items-center gap-2 whitespace-nowrap text-[12.5px] sm:inline-flex ${
        dark ? "text-[#f5ede2]/60" : "text-text/60"
      }`}
    >
      {left}/{me.quota.daily_limit} {t("quota.left")}
      {low && (
        <Link to="/pricing" className="font-semibold text-flame-500 hover:text-flame-400">
          {t("quota.upgrade")}
        </Link>
      )}
    </span>
  );
}

function LangSwitch({ dark }: { dark: boolean }) {
  const { lang, setLang } = useI18n();
  return (
    <label
      className={`flex cursor-pointer items-center gap-1.5 text-[13px] ${
        dark ? "text-[#f5ede2]/70 hover:text-[#f5ede2]" : "text-text/70 hover:text-text"
      }`}
      title="Language"
    >
      <Globe size={14} aria-hidden className="opacity-70" />
      <select
        value={lang}
        onChange={(e) => setLang(e.target.value as Lang)}
        aria-label="Language"
        className="cursor-pointer appearance-none bg-transparent text-[13px] text-inherit outline-none"
      >
        {LANGS.map((l) => (
          <option key={l} value={l} className="text-text">
            {LANG_LABELS[l]}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Nav() {
  const { t } = useI18n();
  const me = useSession((s) => s.me);
  const setAuthOpen = useSession((s) => s.setAuthOpen);
  const logout = useSession((s) => s.logout);
  const location = useLocation();

  // The landing runs the dark "forge" register; every other page is light.
  const dark = location.pathname === "/";

  const navCls = ({ isActive }: { isActive: boolean }) =>
    `nav-underline rounded-md px-3 py-1.5 text-sm transition-colors ${
      dark
        ? isActive
          ? "text-[#f5ede2]"
          : "text-[#f5ede2]/70 hover:text-[#f5ede2]"
        : isActive
          ? "text-text"
          : "text-text/70 hover:text-text"
    }`;

  return (
    <header
      className={`z-40 flex h-14 shrink-0 items-center justify-between px-4 sm:px-6 ${
        dark
          ? "border-b border-white/10 bg-[#12100e] text-[#f5ede2]"
          : "glass-panel border-b-white/40"
      }`}
    >
      <div className="flex items-center gap-3 md:gap-6">
        <Link to="/" className="group flex items-center gap-2.5" aria-label="CV Glowup home">
          <img
            src={logoUrl}
            alt=""
            className="size-9 transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-3"
          />
          <span className="hidden font-sans text-[17px] font-bold tracking-tight min-[480px]:inline">
            CV<span className={dark ? "text-flame-400" : "text-primary"}>Glowup</span>
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

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <QuotaPill dark={dark} />
        <LangSwitch dark={dark} />
        {me?.authenticated ? (
          <div className="flex items-center gap-2">
            <NavLink
              to="/settings"
              className={`hidden text-sm sm:inline ${
                dark ? "text-[#f5ede2]/70 hover:text-[#f5ede2]" : "text-text/70 hover:text-text"
              }`}
            >
              {me.email?.split("@")[0]}
            </NavLink>
            <button
              onClick={() => void logout()}
              className={`grid size-8 place-items-center rounded-md ${
                dark
                  ? "text-[#f5ede2]/70 hover:bg-white/10 hover:text-[#f5ede2]"
                  : "text-text/70 hover:bg-black/5 hover:text-text"
              }`}
              title={t("nav.logout")}
            >
              <LogOut size={15} />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setAuthOpen(true)}
            className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm ${
              dark ? "text-[#f5ede2]/70 hover:text-[#f5ede2]" : "text-text/70 hover:text-text"
            }`}
          >
            {t("nav.login")}
          </button>
        )}
        {!location.pathname.startsWith("/studio") && (
          <Link
            to="/studio"
            className="btn-flame whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-semibold"
          >
            {t("nav.start")}
          </Link>
        )}
      </div>
    </header>
  );
}
