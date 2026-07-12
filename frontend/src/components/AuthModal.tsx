import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import logoUrl from "../assets/CVglowup_logo.svg";
import { api, ApiError } from "../api";
import { useI18n } from "../i18n";
import { useSession } from "../store";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (cfg: object) => void;
          renderButton: (el: HTMLElement, cfg: object) => void;
        };
      };
    };
  }
}

export function AuthModal() {
  const { t } = useI18n();
  const open = useSession((s) => s.authOpen);
  const setOpen = useSession((s) => s.setAuthOpen);
  const refreshMe = useSession((s) => s.refreshMe);
  const config = useSession((s) => s.config);

  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const googleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || !config?.google_client_id) return;
    const id = "google-gsi";
    const ready = () => {
      if (!window.google || !googleRef.current) return;
      window.google.accounts.id.initialize({
        client_id: config.google_client_id,
        callback: async (resp: { credential: string }) => {
          try {
            await api.googleLogin(resp.credential);
            await refreshMe();
            setOpen(false);
          } catch (e) {
            setError(e instanceof Error ? e.message : "Google sign-in failed.");
          }
        },
      });
      window.google.accounts.id.renderButton(googleRef.current, { theme: "filled_black", width: 320 });
    };
    if (document.getElementById(id)) ready();
    else {
      const s = document.createElement("script");
      s.src = "https://accounts.google.com/gsi/client";
      s.id = id;
      s.onload = ready;
      document.head.appendChild(s);
    }
  }, [open, config?.google_client_id, refreshMe, setOpen]);

  if (!open) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") await api.register(email, password);
      else await api.login(email, password);
      await refreshMe();
      setOpen(false);
      setEmail("");
      setPassword("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong — try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-md"
      onClick={() => setOpen(false)}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-sm rounded-xl glass-panel p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-start justify-between">
          <div>
            <p className="eyebrow mb-1.5 flex items-center gap-2">
              <img src={logoUrl} alt="" className="size-6" aria-hidden="true" /> CV Glowup
            </p>
            <h2 className="font-sans text-xl font-semibold text-text">
              {mode === "login" ? t("auth.title.login") : t("auth.title.register")}
            </h2>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="grid size-8 place-items-center rounded-md text-text/70 hover:bg-black/5 hover:text-text"
            aria-label={t("common.cancel")}
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("auth.email")}
            className="w-full rounded-md border border-white/50 bg-white/40 px-3 py-2.5 text-sm text-text placeholder:text-text/50 focus:border-primary focus:outline-none"
          />
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t("auth.password")}
            className="w-full rounded-md border border-white/50 bg-white/40 px-3 py-2.5 text-sm text-text placeholder:text-text/50 focus:border-primary focus:outline-none"
          />
          {error && <p className="text-sm text-danger">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="btn-flame w-full rounded-md py-2.5 text-sm font-semibold disabled:opacity-50"
          >
            {busy ? "…" : mode === "login" ? t("auth.login") : t("auth.register")}
          </button>
        </form>

        {config?.google_client_id && <div ref={googleRef} className="mt-4 flex justify-center" />}

        <button
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="mt-4 w-full text-center text-xs text-text/70 hover:text-text"
        >
          {mode === "login" ? t("auth.switch.toRegister") : t("auth.switch.toLogin")}
        </button>
        <p className="mt-3 text-center text-[11px] text-text/50">{t("auth.guestNote")}</p>
      </div>
    </div>
  );
}
