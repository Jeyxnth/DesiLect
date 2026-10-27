import InputPage from "./pages/InputPage";
import PlayerPage from "./pages/PlayerPage";
import RenderPage from "./pages/RenderPage";

/** Tiny path router (no dependency): / input, /play player, /render export target. */
export default function App() {
  switch (window.location.pathname) {
    case "/play":
      return <PlayerPage />;
    case "/render":
      return <RenderPage />;
    default:
      return <InputPage />;
  }
}
