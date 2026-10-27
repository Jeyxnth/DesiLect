/** Play/pause, previous/next scene, replay, each with its keyboard shortcut (handled in Player). */
export interface ControlsProps {
  playing: boolean;
  onToggle: () => void;
  onPrev: () => void;
  onNext: () => void;
  onReplay: () => void;
}

export default function Controls({ playing, onToggle, onPrev, onNext, onReplay }: ControlsProps) {
  return (
    <div className="controls" role="toolbar" aria-label="Player controls">
      <button onClick={onPrev} aria-label="Previous scene" aria-keyshortcuts="ArrowLeft" title="Previous scene (←)">
        <span aria-hidden="true">⏮</span> Prev <kbd>←</kbd>
      </button>
      <button className="controls-main" onClick={onToggle} aria-label={playing ? "Pause" : "Play"} aria-keyshortcuts="Space" title="Play / pause (Space)">
        <span aria-hidden="true">{playing ? "❚❚" : "▶"}</span> {playing ? "Pause" : "Play"} <kbd>Space</kbd>
      </button>
      <button onClick={onNext} aria-label="Next scene" aria-keyshortcuts="ArrowRight" title="Next scene (→)">
        Next <span aria-hidden="true">⏭</span> <kbd>→</kbd>
      </button>
      <button onClick={onReplay} aria-label="Replay" aria-keyshortcuts="R" title="Replay (R)">
        <span aria-hidden="true">↺</span> Replay <kbd>R</kbd>
      </button>
    </div>
  );
}
