/* Typst source editor — CodeMirror 6 with a small handwritten Typst mode.
   `#import "/typst/x.typ"` paths are clickable: they open the template
   read-only in place, with a back stack (imports inside templates chain). */
import { StreamLanguage, type StringStream } from "@codemirror/language";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  MatchDecorator,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { ArrowLeft } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { api } from "../../api";
import { useI18n } from "../../i18n";
import type { DocController } from "./useDocument";

const typstMode = StreamLanguage.define({
  token(stream: StringStream): string | null {
    if (stream.match("//")) {
      stream.skipToEnd();
      return "comment";
    }
    if (stream.match(/"(?:[^"\\]|\\.)*"?/)) return "string";
    if (stream.match(/#(?:import|let|set|show|if|else|for|while|include)\b/)) return "keyword";
    if (stream.match(/#[a-zA-Z_][\w-]*/)) return "variableName.function";
    if (stream.match(/\b\d+(\.\d+)?(pt|em|cm|mm|fr|%)?\b/)) return "number";
    if (stream.match(/\b(true|false|none|auto)\b/)) return "atom";
    if (stream.match(/[a-zA-Z_][\w-]*(?=\s*:)/)) return "propertyName";
    stream.next();
    return null;
  },
  languageData: { commentTokens: { line: "//" } },
});

const texMode = StreamLanguage.define({
  token(stream: StringStream): string | null {
    if (stream.match("%")) {
      stream.skipToEnd();
      return "comment";
    }
    if (stream.match(/\\[a-zA-Z@]+/)) return "keyword";
    if (stream.match(/\\[^a-zA-Z]/)) return "string";
    if (stream.match(/[{}[\]]/)) return "bracket";
    if (stream.match(/\b\d+(\.\d+)?(pt|em|ex|cm|mm|in)?\b/)) return "number";
    stream.next();
    return null;
  },
  languageData: { commentTokens: { line: "%" } },
});

/* Mark /typst/<name>.typ string paths as links (also active inside a viewed
   template, so common.typ imports chain). */
const tplLinkMatcher = new MatchDecorator({
  regexp: /"\/typst\/([a-z0-9_]+\.typ)"/g,
  decoration: (m) =>
    Decoration.mark({ class: "cm-tpl-link", attributes: { "data-tpl": m[1] } }),
});

const tplLinkPlugin = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;
    constructor(view: EditorView) {
      this.decorations = tplLinkMatcher.createDeco(view);
    }
    update(u: ViewUpdate) {
      this.decorations = tplLinkMatcher.updateDeco(u, this.decorations);
    }
  },
  { decorations: (v) => v.decorations },
);

type TplView = { name: string; content: string };

export function SourceEditor({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const { doc, diagnostics, editSource } = ctl;
  const [tplStack, setTplStack] = useState<TplView[]>([]);
  const openTpl = useRef<(name: string) => void>(() => undefined);

  openTpl.current = (name: string) => {
    void api
      .templateSource(name)
      .then((content) => setTplStack((s) => [...s, { name, content }]))
      .catch(() => undefined);
  };

  // Stable extension; the ref keeps the handler current across renders.
  const tplClick = useMemo(
    () =>
      EditorView.domEventHandlers({
        mousedown: (e) => {
          const el = (e.target as HTMLElement).closest?.(".cm-tpl-link");
          const name = el?.getAttribute("data-tpl");
          if (name) {
            openTpl.current(name);
            return true;
          }
          return false;
        },
      }),
    [],
  );

  if (!doc) return null;
  const isLatex = (doc.settings.compiler ?? "typst") === "latex";
  const viewing = tplStack[tplStack.length - 1];

  if (viewing) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <div className="flex shrink-0 items-center gap-2 border-b border-ink-700 bg-ink-900 px-3 py-2">
          <button
            onClick={() => setTplStack((s) => s.slice(0, -1))}
            className="flex items-center gap-1.5 rounded px-1.5 py-1 font-mono text-[11px] uppercase tracking-wider text-text/70 transition-colors hover:text-text"
          >
            <ArrowLeft size={13} />
            {t("studio.source.back")}
          </button>
          <span className="min-w-0 truncate font-mono text-[11.5px] text-text/80">
            /typst/{viewing.name}
          </span>
          <span className="ml-auto shrink-0 rounded-full border border-black/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-text/50">
            {t("studio.source.readonly")}
          </span>
        </div>
        <div className="cm-shell min-h-0 flex-1 overflow-hidden">
          <CodeMirror
            value={viewing.content}
            height="100%"
            theme="dark"
            editable={false}
            extensions={[typstMode, tplLinkPlugin, tplClick]}
            basicSetup={{
              lineNumbers: true,
              foldGutter: false,
              highlightActiveLine: false,
              autocompletion: false,
              searchKeymap: true,
            }}
            style={{ height: "100%" }}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="cm-shell min-h-0 flex-1 overflow-hidden">
        <CodeMirror
          value={doc.source ?? ""}
          height="100%"
          theme="dark"
          extensions={isLatex ? [texMode] : [typstMode, tplLinkPlugin, tplClick]}
          onChange={(value) => editSource(value)}
          basicSetup={{
            lineNumbers: true,
            foldGutter: false,
            highlightActiveLine: true,
            autocompletion: false,
            searchKeymap: true,
          }}
          style={{ height: "100%" }}
        />
      </div>
      {diagnostics && (
        <div className="max-h-40 shrink-0 overflow-y-auto border-t border-signal-500/30 bg-signal-950 p-3">
          <p className="eyebrow mb-1.5 text-danger">{t("studio.compile.error")}</p>
          <pre className="whitespace-pre-wrap font-mono text-[11.5px] leading-relaxed text-danger/90">
            {diagnostics}
          </pre>
        </div>
      )}
    </div>
  );
}
