import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { estimateInitialContextTokens } from "./context-usage.ts";
import { discoverLoadedCounts, getRecentSessions, WelcomeComponent } from "./welcome.ts";

const DELAY_MS = 100;
const TIMEOUT_SECONDS = 30;

export default function welcome(pi: ExtensionAPI) {
  let generation = 0;
  let dismiss: (() => void) | undefined;
  let agentRunning = false;

  pi.on("session_start", (event, ctx) => {
    generation++;
    agentRunning = false;
    if (event.reason !== "startup" || ctx.mode !== "tui") return;

    const currentGeneration = generation;
    const modelName = ctx.model?.name || ctx.model?.id || "No model";
    const providerName = ctx.model?.provider || "Unknown";
    const loadedCounts = discoverLoadedCounts();
    const recentSessions = getRecentSessions(3);

    setTimeout(() => {
      if (agentRunning || currentGeneration !== generation) return;

      const hasActivity = (ctx.sessionManager?.getBranch?.() ?? []).some((entry: any) =>
        entry?.type === "message" && entry.message?.role === "assistant"
      );
      if (hasActivity) return;

      void ctx.ui.custom<void>(
        (tui, theme, _keybindings, done) => {
          const component = new WelcomeComponent(
            theme,
            modelName,
            providerName,
            recentSessions,
            loadedCounts,
            estimateInitialContextTokens(ctx),
          );
          let seconds = TIMEOUT_SECONDS;
          let closed = false;
          const interval = setInterval(() => {
            component.setCountdown(--seconds);
            tui.requestRender();
            if (seconds <= 0) close();
          }, 1000);

          function close() {
            if (closed) return;
            closed = true;
            clearInterval(interval);
            dismiss = undefined;
            done();
          }

          dismiss = close;
          return {
            focused: false,
            render: (width: number) => component.render(width),
            invalidate: () => component.invalidate(),
            handleInput: close,
            dispose: () => {
              closed = true;
              clearInterval(interval);
            },
          };
        },
        {
          overlay: true,
          overlayOptions: { anchor: "center" },
        },
      ).catch((error) => console.debug("[welcome] overlay failed:", error));
    }, DELAY_MS);
  });

  pi.on("agent_start", () => {
    agentRunning = true;
    dismiss?.();
  });

  pi.on("session_shutdown", () => {
    generation++;
    dismiss?.();
  });
}
