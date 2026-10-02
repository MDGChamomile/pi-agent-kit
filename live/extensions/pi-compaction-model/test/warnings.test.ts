import { expect, mock, spyOn, test } from "bun:test";
import type { ExtensionContext, SettingsManager } from "@earendil-works/pi-coding-agent";
import { loadConfig } from "../src/config.js";
import { warn } from "../src/warnings.js";

for (const hasUI of [true, false]) {
  test(`routes warning text and error details with hasUI=${hasUI}`, () => {
    const notify = mock((_message: string, _type?: "info" | "warning" | "error") => {});
    const ctx = { hasUI, ui: { notify } } as unknown as ExtensionContext;
    const consoleWarn = spyOn(console, "warn").mockImplementation(() => {});
    const error = new Error("synthetic provider failure");
    try {
      warn(ctx, "plain warning");
      warn(ctx, "request failed", error);
      warn(ctx, "request failed", "synthetic string failure");
      if (hasUI) {
        expect(notify.mock.calls).toEqual([
          ["[pi-compaction-model] plain warning", "warning"],
          ["[pi-compaction-model] request failed synthetic provider failure", "warning"],
          ["[pi-compaction-model] request failed synthetic string failure", "warning"],
        ]);
        expect(consoleWarn).not.toHaveBeenCalled();
      } else {
        expect(consoleWarn.mock.calls).toEqual([
          ["[pi-compaction-model] plain warning"],
          ["[pi-compaction-model] request failed", error],
          ["[pi-compaction-model] request failed", "synthetic string failure"],
        ]);
        expect(notify).not.toHaveBeenCalled();
      }
    } finally {
      consoleWarn.mockRestore();
    }
  });

  test(`routes configuration warnings with hasUI=${hasUI}`, () => {
    const notify = mock((_message: string, _type?: "info" | "warning" | "error") => {});
    const ctx = {
      hasUI, ui: { notify }, isProjectTrusted: () => false,
    } as unknown as ExtensionContext;
    let section: unknown = { model: "" };
    const settings = {
      getGlobalSettings: () => ({ compactionModel: section }),
      getProjectSettings: () => { throw new Error("untrusted project must not be read"); },
    } as unknown as SettingsManager;
    const consoleWarn = spyOn(console, "warn").mockImplementation(() => {});
    try {
      expect(loadConfig(ctx, settings)).toBeNull();
      section = { model: "provider/model", thinkingLevel: "invalid", reasons: ["invalid"] };
      expect(loadConfig(ctx, settings)).toEqual({
        model: "provider/model", thinkingLevel: undefined,
        reasons: ["manual", "threshold", "overflow"],
      });
      const messages = [
        "[pi-compaction-model] compactionModel.model must be a non-empty provider/model string; using Pi's active model.",
        "[pi-compaction-model] Invalid thinkingLevel 'invalid'; using the provider default.",
        "[pi-compaction-model] reasons must contain only manual, threshold, or overflow; handling all reasons.",
      ];
      if (hasUI) {
        expect(notify.mock.calls).toEqual(messages.map((message) => [message, "warning"]));
        expect(consoleWarn).not.toHaveBeenCalled();
      } else {
        expect(consoleWarn.mock.calls).toEqual(messages.map((message) => [message]));
        expect(notify).not.toHaveBeenCalled();
      }
    } finally {
      consoleWarn.mockRestore();
    }
  });
}
