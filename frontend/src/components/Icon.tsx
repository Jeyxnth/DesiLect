/** Our own small icon set for the app chrome (never the stage): one 24 px grid, 2 px round strokes, filled where a
 *  shape reads better filled. Decorative by default (aria-hidden); the button or text next to it carries the name. */
export type IconName = "play" | "pause" | "prev" | "next" | "replay" | "check" | "cross" | "flame" | "left" | "right" | "plus" | "alert";

const PATHS: Record<IconName, JSX.Element> = {
  play: <path d="M7 4.5v15l12.5-7.5z" fill="currentColor" stroke="none" />,
  pause: <><rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none" /><rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none" /></>,
  prev: <><path d="M19 5v14L9 12z" fill="currentColor" stroke="none" /><path d="M6 5v14" /></>,
  next: <><path d="M5 5v14l10-7z" fill="currentColor" stroke="none" /><path d="M18 5v14" /></>,
  replay: <><path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3" /><path d="M4.5 4v4.5H9" /></>,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  cross: <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />,
  flame: <path d="M13.5 2c.6 3.3-.9 5.3-2.6 7.3C9.2 11.3 7 13.3 7 16a5 5 0 0 0 10 0c0-2.4-1.1-4.3-2.3-5.6.2 1.7-.4 3.1-1.5 3.7.9-3.9-.4-8.4 0-12.1z" fill="currentColor" stroke="none" />,
  left: <path d="M19 12H5m6-6l-6 6 6 6" />,
  right: <path d="M5 12h14m-6-6l6 6-6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  alert: <><path d="M12 8v5" /><path d="M12 16.5v.5" /><path d="M10.3 3.9L2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /></>,
};

export default function Icon({ name, label }: { name: IconName; label?: string }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} focusable="false">
      {PATHS[name]}
    </svg>
  );
}
