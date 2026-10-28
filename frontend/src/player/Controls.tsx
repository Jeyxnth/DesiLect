import Icon from "../components/Icon";

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
      <button onClick={onPrev} aria-label="Previous scene" aria-keyshortcuts="ArrowLeft" title="Previous scene (Left arrow)">
        <Icon name="prev" /> Prev <kbd><Icon name="left" /></kbd>
      </button>
      <button className="controls-main" onClick={onToggle} aria-label={playing ? "Pause" : "Play"} aria-keyshortcuts="Space" title="Play / pause (Space)">
        <Icon name={playing ? "pause" : "play"} /> {playing ? "Pause" : "Play"} <kbd>Space</kbd>
      </button>
      <button onClick={onNext} aria-label="Next scene" aria-keyshortcuts="ArrowRight" title="Next scene (Right arrow)">
        Next <Icon name="next" /> <kbd><Icon name="right" /></kbd>
      </button>
      <button onClick={onReplay} aria-label="Replay" aria-keyshortcuts="R" title="Replay (R)">
        <Icon name="replay" /> Replay <kbd>R</kbd>
      </button>
    </div>
  );
}
