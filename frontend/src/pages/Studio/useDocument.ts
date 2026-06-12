/* Orchestrates one open document: optimistic edits, debounced server sync,
   live recompiles, chat edits, mode transitions. */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type DocSettings, type DocumentPayload } from "../../api";
import { useStudio } from "../../store";

export interface DocController {
  doc: DocumentPayload | null;
  svgs: string[] | null;
  loading: boolean;
  syncing: boolean;
  diagnostics: string;
  updateData: (data: object) => void;
  updateSettings: (settings: DocSettings) => Promise<void>;
  updateText: (text: string) => void;
  editSource: (source: string) => void;
  revertToData: () => Promise<void>;
  chat: (message: string) => Promise<{ ok: boolean; reply: string; diagnostics?: string }>;
  refreshPreview: () => Promise<void>;
}

export function useDocument(docId: string | null): DocController {
  const docs = useStudio((s) => s.docs);
  const svgCache = useStudio((s) => s.svgCache);
  const applyDocument = useStudio((s) => s.applyDocument);
  const setSvgs = useStudio((s) => s.setSvgs);
  const loadDocument = useStudio((s) => s.loadDocument);

  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [diagnostics, setDiagnostics] = useState("");
  const dataTimer = useRef<number>();
  const sourceTimer = useRef<number>();
  const textTimer = useRef<number>();

  const doc = docId ? (docs[docId] ?? null) : null;
  const svgs = docId ? (svgCache[docId] ?? null) : null;

  useEffect(() => {
    if (!docId || docs[docId]) return;
    setLoading(true);
    void loadDocument(docId).finally(() => setLoading(false));
  }, [docId, docs, loadDocument]);

  // Flush pending timers when switching documents.
  useEffect(() => {
    return () => {
      window.clearTimeout(dataTimer.current);
      window.clearTimeout(sourceTimer.current);
      window.clearTimeout(textTimer.current);
    };
  }, [docId]);

  const pushUpdate = useCallback(
    async (body: { data?: object; settings?: DocSettings; text_content?: string }) => {
      if (!docId) return;
      setSyncing(true);
      try {
        const updated = await api.updateDocument(docId, body);
        applyDocument(updated);
        if (updated.svgs) setSvgs(docId, updated.svgs);
        setDiagnostics("");
      } catch (e) {
        if (e instanceof ApiError && e.code === "compile_error") setDiagnostics(e.message);
      } finally {
        setSyncing(false);
      }
    },
    [docId, applyDocument, setSvgs],
  );

  const updateData = useCallback(
    (data: object) => {
      if (!docId || !doc) return;
      // Optimistic local state so typing stays instant.
      applyDocument({ ...doc, data: data as DocumentPayload["data"], mode: "data" });
      window.clearTimeout(dataTimer.current);
      dataTimer.current = window.setTimeout(() => void pushUpdate({ data }), 700);
    },
    [docId, doc, applyDocument, pushUpdate],
  );

  const updateText = useCallback(
    (text: string) => {
      if (!docId || !doc) return;
      applyDocument({ ...doc, text_content: text });
      window.clearTimeout(textTimer.current);
      textTimer.current = window.setTimeout(() => void pushUpdate({ text_content: text }), 800);
    },
    [docId, doc, applyDocument, pushUpdate],
  );

  const updateSettings = useCallback(
    async (settings: DocSettings) => {
      window.clearTimeout(dataTimer.current);
      await pushUpdate({ settings });
    },
    [pushUpdate],
  );

  const editSource = useCallback(
    (source: string) => {
      if (!docId || !doc) return;
      applyDocument({ ...doc, source, mode: "source" });
      window.clearTimeout(sourceTimer.current);
      sourceTimer.current = window.setTimeout(async () => {
        setSyncing(true);
        try {
          const res = await api.compile(docId, source);
          if (res.ok) {
            setSvgs(docId, res.svgs);
            setDiagnostics("");
          } else {
            setDiagnostics(res.diagnostics);
          }
        } catch (e) {
          setDiagnostics(e instanceof Error ? e.message : "Compile failed.");
        } finally {
          setSyncing(false);
        }
      }, 850);
    },
    [docId, doc, applyDocument, setSvgs],
  );

  const revertToData = useCallback(async () => {
    if (!doc?.data) return;
    await pushUpdate({ data: doc.data });
  }, [doc, pushUpdate]);

  const chat = useCallback(
    async (message: string) => {
      if (!docId) return { ok: false, reply: "No document open." };
      const res = await api.chat(docId, message);
      if (res.ok) {
        const current = useStudio.getState().docs[docId];
        if (current) {
          applyDocument({
            ...current,
            data: (res.data as DocumentPayload["data"]) ?? current.data,
            source: res.source ?? current.source,
            text_content: res.text_content ?? current.text_content,
          });
        }
        if (res.svgs) setSvgs(docId, res.svgs);
      }
      return { ok: res.ok, reply: res.reply, diagnostics: res.diagnostics };
    },
    [docId, applyDocument, setSvgs],
  );

  const refreshPreview = useCallback(async () => {
    if (!docId || !doc?.source || doc.kind === "message") return;
    const res = await api.compile(docId);
    if (res.ok) setSvgs(docId, res.svgs);
  }, [docId, doc, setSvgs]);

  // First open: if the doc came without svgs (cache miss), compile once.
  useEffect(() => {
    if (docId && doc && !svgs && doc.kind !== "message" && doc.source) {
      void refreshPreview();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docId, doc?.id, svgs]);

  return {
    doc, svgs, loading, syncing, diagnostics,
    updateData, updateSettings, updateText, editSource, revertToData, chat, refreshPreview,
  };
}
