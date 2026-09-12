/* Pure merge rules for server responses to document edits, kept out of the
   useDocument hook so they are unit-testable without React. */
import type { DocumentPayload } from "../../api";

/* A PUT echo carries the server's render and keyword re-score for the edit
   that was SENT. If the user kept typing while it was in flight, the local
   copy is newer: keep its data/text (its own debounced PUT follows) and take
   everything the server computed. */
export function mergeEcho(
  current: DocumentPayload | undefined,
  sent: { data?: object; text_content?: string },
  echo: DocumentPayload,
): DocumentPayload {
  if (!current) return echo;
  const dataMoved = sent.data !== undefined && current.data !== sent.data;
  const textMoved = sent.text_content !== undefined && current.text_content !== sent.text_content;
  if (!dataMoved && !textMoved) return echo;
  return {
    ...echo,
    ...(dataMoved ? { data: current.data, mode: current.mode } : {}),
    ...(textMoved ? { text_content: current.text_content } : {}),
  };
}

/* Compile and chat responses report the re-scored keyword match; fold it into
   the stored document so the score card moves with the edit. A field the
   response does not carry leaves the stored value alone. */
export function withScore(
  doc: DocumentPayload,
  res: { score_after?: number | null; keywords?: DocumentPayload["keywords"] },
): DocumentPayload {
  if (res.score_after === undefined && res.keywords === undefined) return doc;
  return {
    ...doc,
    score_after: res.score_after === undefined ? doc.score_after : res.score_after,
    keywords: res.keywords === undefined ? doc.keywords : res.keywords,
  };
}
