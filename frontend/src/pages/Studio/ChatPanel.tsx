/* The document assistant — chat messages that edit the document directly. */
import { Loader2, Send, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../../i18n";
import type { DocController } from "./useDocument";

interface ChatMsg {
  role: "user" | "assistant";
  text: string;
  error?: boolean;
}

export function ChatPanel({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = async () => {
    const message = input.trim();
    if (!message || busy || !ctl.doc) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: message }]);
    setBusy(true);
    try {
      const res = await ctl.chat(message);
      setMessages((m) => [
        ...m,
        { role: "assistant", text: res.ok ? res.reply : `${res.reply}\n${res.diagnostics ?? ""}`, error: !res.ok },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: e instanceof Error ? e.message : "That edit failed — try again.", error: true },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        <div className="flex items-start gap-2.5">
          <span className="grid size-6 shrink-0 place-items-center rounded-full bg-flame-950 text-primary/80">
            <Sparkles size={12} />
          </span>
          <p className="rounded-lg rounded-tl-none border border-black/10 glass-panel px-3 py-2 text-[13px] text-text/70">
            {t("studio.chat.hello")}
          </p>
        </div>
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <p className="max-w-[85%] rounded-lg rounded-tr-none bg-flame-600 px-3 py-2 text-[13px] text-white">
                {m.text}
              </p>
            </div>
          ) : (
            <div key={i} className="flex items-start gap-2.5">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-flame-950 text-primary/80">
                <Sparkles size={12} />
              </span>
              <p
                className={`max-w-[85%] whitespace-pre-wrap rounded-lg rounded-tl-none border px-3 py-2 text-[13px] ${
                  m.error
                    ? "border-signal-500/30 bg-signal-950 text-danger"
                    : "border-black/10 glass-panel text-text/70"
                }`}
              >
                {m.text}
              </p>
            </div>
          ),
        )}
        {busy && (
          <div className="flex items-center gap-2.5 pl-9 text-text/50">
            <Loader2 size={13} className="animate-spin" />
            <span className="font-mono text-[11px]">editing…</span>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); void send(); }}
        className="flex shrink-0 items-end gap-2 border-t border-black/10 p-3"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); }
          }}
          placeholder={t("studio.chat.placeholder")}
          rows={2}
          className="flex-1 resize-none rounded-lg border border-black/10 glass-panel px-3 py-2 text-[13px] placeholder:text-text/50 focus:border-flame-500"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary text-white transition hover:bg-primary/90 disabled:opacity-40"
          aria-label={t("studio.chat.send")}
        >
          <Send size={14} />
        </button>
      </form>
    </div>
  );
}
