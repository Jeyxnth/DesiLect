import { createElement, type ReactElement } from "react";
import type { Beat, Language, Scene, TimelineScene } from "../types/lesson";
import { localBeats } from "./anim";
import CodeWalkthrough from "./CodeWalkthrough";
import DiagramScene from "./DiagramScene";
import TitleCard from "./TitleCard";

/**
 * Props every scene component receives (stable contract for step 7's polished scenes).
 * localT = lesson time - scene.start; beats are shifted to scene-local time too.
 * Scenes are pure functions of these props.
 */
export interface SceneProps<S extends Scene = Scene> {
  scene: S;
  localT: number;
  beats: Beat[];
  lang: Language;
}

/** Only our own components draw visuals (H4): the scene type picks a fixed component. */
export function renderScene(ts: TimelineScene, t: number, lang: Language): ReactElement | null {
  const common = { localT: t - ts.start, beats: localBeats(ts), lang };
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
