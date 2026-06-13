/* AdSense slot — renders only for free-tier traffic on deployments where
   VITE/Config provides an AdSense client id. Paid plans and BYOK users never
   see ads. Gated entirely by backend config, so enabling ads is a deploy-time
   decision, not a code change. */
import { useEffect, useRef } from "react";
import { byokStore } from "../api";
import { useSession } from "../store";

declare global {
  interface Window {
    adsbygoogle?: unknown[];
  }
}

export function AdSlot({ slot, className = "" }: { slot: string; className?: string }) {
  const me = useSession((s) => s.me);
  const config = useSession((s) => s.config);
  const pushed = useRef(false);

  const client = config?.adsense_client;
  const freeTier = !me?.authenticated || me.plan === "free";
  const show = !!client && freeTier && !byokStore.get();

  useEffect(() => {
    if (!show || pushed.current) return;
    const id = "adsbygoogle-js";
    if (!document.getElementById(id)) {
      const s = document.createElement("script");
      s.id = id;
      s.async = true;
      s.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${client}`;
      s.crossOrigin = "anonymous";
      document.head.appendChild(s);
    }
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
      pushed.current = true;
    } catch {
      /* blocked or not ready — fail silent */
    }
  }, [show, client]);

  if (!show) return null;

  return (
    <div className={`overflow-hidden rounded-lg border border-ink-800 bg-ink-900/60 ${className}`}>
      <p className="px-2 pt-1 text-right font-mono text-[9px] uppercase tracking-wider text-fg-faint">Ad</p>
      <ins
        className="adsbygoogle block"
        style={{ display: "block", minHeight: 90 }}
        data-ad-client={client}
        data-ad-slot={slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </div>
  );
}
