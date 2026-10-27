import { createElement, type ReactElement } from "react";
import type { Beat, Cue, Language, Scene, TimelineScene } from "../types/lesson";
import { localBeats } from "./anim";
import CodeWalkthrough, { codeAnimationStarts } from "./CodeWalkthrough";
import DiagramScene, { diagramAnimationStarts } from "./DiagramScene";
import TitleCard, { titleAnimationStarts } from "./TitleCard";

/**
 * Props every scene component receives. localT = lesson time - scene.start; beats and cues are
 * shifted to scene-local time too. Scenes are pure functions of these props (G3).
 */
export interface SceneProps<S extends Scene = Scene> {
  scene: S;
  localT: number;
  beats: Beat[];
  lang: Language;
  cues: Cue[];
}

function localCues(ts: TimelineScene): Cue[] {
  return ts.cues.map((c) => ({ ...c, start: c.start - ts.start, end: c.end - ts.start }));
}

/** Only our own components draw visuals (H4): the scene type picks a fixed component. */
export function renderScene(ts: TimelineScene, t: number, lang: Language): ReactElement | null {
  const common = { localT: t - ts.start, beats: localBeats(ts), cues: localCues(ts), lang };
  const scene = ts.data;
  switch (scene.type) {
    case "title_card":
      return createElement(TitleCard, { ...common, scene });
    case "diagram":
      return createElement(DiagramScene, { ...common, scene });
    case "code_walkthrough":
      return createElement(CodeWalkthrough, { ...common, scene });
    default:
      return null;
  }
}

/** Absolute times at which an animation in this scene starts (each becomes an export keyframe). */
export function animationStarts(ts: TimelineScene): number[] {
  const beats = localBeats(ts);
  const scene = ts.data;
  const local =
    scene.type === "title_card" ? titleAnimationStarts()
    : scene.type === "diagram" ? diagramAnimationStarts(scene, beats)
    : scene.type === "code_walkthrough" ? codeAnimationStarts(beats)
    : [];
  return local.filter((x) => Number.isFinite(x)).map((x) => ts.start + x);
}
