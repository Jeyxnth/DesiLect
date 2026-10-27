/**
 * File-name slug for downloads: "How does a Python loop work?" -> "how-does-a-python-loop-work".
 * Keeps ASCII letters and digits (accents folded); a topic with none, e.g. typed in Tamil, gives "lesson".
 */
export function topicSlug(topic: string | null | undefined, maxLength = 60): string {
  const ascii = (topic ?? "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const slug = ascii.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, maxLength).replace(/-+$/, "");
  return slug || "lesson";
}

/** <topic-slug>_<lang>.<ext>, e.g. how-does-a-python-loop-work_ta.mp4 */
export function downloadName(topic: string | null | undefined, lang: string, ext: string): string {
  return `${topicSlug(topic)}_${lang}.${ext}`;
}
