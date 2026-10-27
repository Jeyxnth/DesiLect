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
  label?: string; // <= 32 (English plans: 16; the slack is for Indic scripts)
}

export interface DiagramScene {
  type: "diagram";
  heading: string;
  layout: "row" | "cycle" | "stack";
  items: string[]; // 2..6, each <= 48 (English plans: 24; the slack is for Indic scripts)
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

/** Set by the backend, never by the planner model. */
export interface LessonMeta {
  fallback: boolean; // true when the built-in sample was used instead of a generated plan
  source?: string; // e.g. "ollama:llama3.2:3b" or "sample:python_loop"
  topic?: string;
  reason?: string; // why the fallback was used, shown to the user
  translation_fallback?: boolean; // translation failed, so the narration stayed in English
}

/** One end-of-lesson question (bonus B1). Text arrives already in the lesson language. */
export interface QuizQuestion {
  question: string; // <= 320 (English plans: 160)
  options: [string, string, string, string]; // each <= 160 (English: 80), all different
  answer_index: number; // 0..3
  explanation: string; // <= 400 (English: 200)
}

export interface Lesson {
  title: string;
  level: Level;
  language: Language;
  scenes: Scene[]; // 3..6
  quiz?: QuizQuestion[]; // 2..3, optional: a bad quiz is dropped, never the lesson
  meta?: LessonMeta;
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
  quiz?: QuizQuestion[]; // copied from the lesson; the player shows it after the last scene, the MP4 never does
}

export interface ConceptRequest {
  topic: string;
  level: Level;
  language: Language;
  target_seconds: number; // 30..90
  speed?: number; // narration speed 0.7..1.3, default 1.0 (ConceptRequest in backend/app/pipeline/jobs.py)
  voice?: Voice; // default female; each language maps it to a concrete voice
}

export type Voice = "female" | "male";
