import Icon from "./Icon";

/** Visible notice that a built-in sample is shown instead of a generated lesson (G2 made honest). */
export default function FallbackNotice({ reason, source, topic }: { reason?: string | null; source?: string; topic?: string }) {
  const sample = source?.startsWith("sample:") ? sampleLabel(source.slice("sample:".length)) : null;
  return (
    <div className="fallback-notice" role="status">
      <strong><Icon name="alert" /> Fallback lesson used: a built-in sample, not a newly generated lesson</strong>
      <p>{reason ?? "The lesson could not be generated."}</p>
      <p>
        {topic && <>You asked for: “{topic}”. </>}
        {sample ? <>Shown instead: the built-in “{sample}” lesson.</> : <>A built-in lesson is shown instead.</>}
      </p>
    </div>
  );
}

function sampleLabel(name: string): string {
  const s = name.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
