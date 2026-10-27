import { useEffect, useState } from "react";
import type { ConceptRequest } from "./types/lesson";

/** Navigation state: autoplay is set when the input page opens a lesson it just generated; prefill + autostart
 *  when "Try next" sends a topic to the input page (bonus B2). */
export interface NavState {
  autoplay?: boolean;
  prefill?: Partial<ConceptRequest>;
  autostart?: boolean;
}

const EVENT = "blu:navigate";

/**
 * Client-side navigation (no reload). Staying in the same document keeps the user's Generate click
 * as "user activation", so the player is allowed to start audio on its own.
 */
export function navigate(path: string, state: NavState = {}): void {
  window.history.pushState(state, "", path);
  window.dispatchEvent(new Event(EVENT));
}

export function navState(): NavState {
  return (window.history.state as NavState | null) ?? {};
}

/** The current path; re-renders on navigate() and on browser back/forward. */
export function usePath(): string {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const update = () => setPath(window.location.pathname);
    window.addEventListener("popstate", update);
    window.addEventListener(EVENT, update);
    return () => {
      window.removeEventListener("popstate", update);
      window.removeEventListener(EVENT, update);
    };
  }, []);
  return path;
}
