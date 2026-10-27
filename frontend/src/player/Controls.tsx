/** Play/pause, previous/next scene, replay. TODO(step 3): icons, keyboard shortcuts. */
export interface ControlsProps {
  playing: boolean;
  onToggle: () => void;
  onPrev: () => void;
  onNext: () => void;
  onReplay: () => void;
}

export default function Controls({ playing, onToggle, onPrev, onNext, onReplay }: ControlsProps) {
  return (
    <div className="controls">
      <button onClick={onPrev} aria-label="Previous scene">Prev</button>
      <button onClick={onToggle} aria-label={playing ? "Pause" : "Play"}>{playing ? "Pause" : "Play"}</button>
      <button onClick={onNext} aria-label="Next scene">Next</button>
      <button onClick={onReplay} aria-label="Replay">Replay</button>
    </div>
  );
}
