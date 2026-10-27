import { createElement, type ReactElement } from "react";
import type { Beat, Scene, TimelineScene } from "../types/lesson";
import CodeWalkthrough from "./CodeWalkthrough";
import DiagramScene from "./DiagramScene";
import TitleCard from "./TitleCard";

/** Props every scene component receives. t is absolute lesson time in seconds. */
export interface SceneProps<S extends Scene = Scene> {
  data: S;
  t: number;
  start: number;
  end: number;
  beats: Beat[];
}

/** Only our own components draw visuals (H4): the scene type picks a fixed component. */
export function renderScene(scene: TimelineScene, t: number): ReactElement | null {
  const common = { t, start: scene.start, end: scene.end, beats: scene.beats };
  const data = scene.data;
  switch (data.type) {
    case "title_card":
      return createElement(TitleCard, { ...common, data });
    case "diagram":
      return createElement(DiagramScene, { ...common, data });
    case "code_walkthrough":
      return createElement(CodeWalkthrough, { ...common, data });
    default:
      return null;
  }
}
