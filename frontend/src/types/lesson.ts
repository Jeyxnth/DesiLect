// Hand-written mirror of shared/schema/*.json (G1). Change both together.

export type Level = "beginner" | "intermediate";
export type Language = "en" | "hi" | "ta";
export type SceneType = "title_card" | "diagram" | "code_walkthrough";

export interface TitleCardScene {
  type: "title_card";
  heading: string; // <= 60
  subheading?: string; // <= 80
  narration: string;
}

export interface Arrow {
  from: number;
  to: number;
  label?: string; // <= 16
}

export interface DiagramScene {
  type: "diagram";
  heading: string;
  layout: "row" | "cycle" | "stack";
  items: string[]; // 2..6, each <= 24
  arrows?: Arrow[];
  narration: string;
}

export interface CodeWalkthroughScene {
  type: "code_walkthrough";
  heading: string;
  code: string; // <= 12 lines, <= 50 cols; text only (H4)
  language_hint?: string;
  highlight_lines: number[]; // 1-based
  narration: string;
}

export type Scene = TitleCardScene | DiagramScene | CodeWalkthroughScene;

export interface Lesson {
  title: string;
  level: Level;
  language: Language;
  scenes: Scene[]; // 3..6
}

export interface Cue {
  start: number;
  end: number;
  text: string;
}

export interface Beat {
  t: number;
  action: "reveal" | "highlight";
  value: number;
}

export interface TimelineScene {
  index: number;
  type: SceneType;
  start: number;
  end: number;
  heading: string;
  data: Scene;
  cues: Cue[];
  beats: Beat[];
}

export interface Timeline {
  lesson_id: string;
  language: Language;
  total_seconds: number;
  audio_url: string;
  scenes: TimelineScene[];
}

export interface ConceptRequest {
  topic: string;
  level: Level;
  language: Language;
  target_seconds: number; // 30..90
}
