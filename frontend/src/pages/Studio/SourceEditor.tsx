/* Typst source editor — CodeMirror 6 with a small handwritten Typst mode. */
import { StreamLanguage, type StringStream } from "@codemirror/language";
import CodeMirror from "@uiw/react-codemirror";
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

export function SourceEditor({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const { doc, diagnostics, editSource } = ctl;
  if (!doc) return null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="cm-shell min-h-0 flex-1 overflow-hidden">
        <CodeMirror
          value={doc.source ?? ""}
          height="100%"
          theme="dark"
          extensions={[typstMode]}
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
