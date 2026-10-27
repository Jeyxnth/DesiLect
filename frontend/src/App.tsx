import InputPage from "./pages/InputPage";
import PlayerPage from "./pages/PlayerPage";
import RenderPage from "./pages/RenderPage";
import { usePath } from "./router";

/** Tiny path router (no dependency): / input, /lesson/:id player, /render/:id export target. */
export default function App() {
  const path = usePath();
  const lesson = /^\/lesson\/([\w-]+)\/?$/.exec(path);
  if (lesson?.[1]) return <PlayerPage key={lesson[1]} id={lesson[1]} />;
  const render = /^\/render\/([\w-]+)\/?$/.exec(path);
  if (render?.[1]) return <RenderPage id={render[1]} />;
  return <InputPage />;
}
