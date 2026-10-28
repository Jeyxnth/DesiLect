import Icon from "./Icon";

/** Visible notice that a built-in sample is shown instead of a generated lesson (G2 made honest).
 *  onRetry: offer "Generate again", which plans the same request afresh (a fallback is never reused from the cache). */
export default function FallbackNotice({ reason, source, topic, onRetry }: {
  reason?: string | null;
  source?: string;
  topic?: string;
  onRetry?: () => void;
}) {
  const sample = source?.startsWith("sample:") ? sampleLabel(source.slice("sample:".length)) : null;
  return (
    <div className="fallback-notice" role="status">
      <strong><Icon name="alert" /> Fallback lesson used: a built-in sample, not a newly generated lesson</strong>
      <p>{reason ?? "The lesson could not be generated."}</p>
      <p>
        {topic && <>You asked for: “{topic}”. </>}
        {sample ? <>Shown instead: the built-in “{sample}” lesson.</> : <>A built-in lesson is shown instead.</>}
      </p>
      {onRetry && <RetryRow onRetry={onRetry} hint="The local planner often succeeds on another try." />}
    </div>
  );
}

/** Honest note for a lesson kept although its narration came out shorter than asked (lesson.meta.short_of). */
export function ShortNotice({ seconds, targetSeconds, onRetry }: { seconds: number; targetSeconds: number; onRetry?: () => void }) {
  return (
    <div className="fallback-notice" role="status">
      <strong><Icon name="alert" /> Shorter than you asked: about {Math.round(seconds)} s instead of {targetSeconds} s</strong>
      <p>The local planner wrote less narration than this length needs, so the lesson was kept short instead of being replaced by a built-in sample.</p>
      {onRetry && <RetryRow onRetry={onRetry} hint="Another try may give a full-length lesson." />}
    </div>
  );
}

function RetryRow({ onRetry, hint }: { onRetry: () => void; hint: string }) {
  return (
    <p className="notice-actions">
      <button type="button" className="button small" onClick={onRetry}><Icon name="replay" /> Generate again</button>
      <span>{hint}</span>
    </p>
  );
}

function sampleLabel(name: string): string {
  const s = name.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
