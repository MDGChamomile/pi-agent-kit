import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

function getAgentDir(): string {
  const configured = process.env.PI_CODING_AGENT_DIR?.trim();
  if (!configured || configured === "~") return configured === "~" ? homedir() : join(homedir(), ".pi", "agent");
  if (configured.startsWith("~/")) return join(homedir(), configured.slice(2));
  return configured;
}

export default function gitHistory(pi: ExtensionAPI) {
  const agentDir = getAgentDir();
  const git = (args: string[]) => pi.exec("git", ["-C", agentDir, ...args]);

  pi.registerCommand("snapshot", {
    description: "Review and commit changes in the Pi agent directory",
    handler: async (args, ctx) => {
      if (!ctx.hasUI) return;

      const workTree = await git(["rev-parse", "--is-inside-work-tree"]);
      if (workTree.code !== 0 || workTree.stdout.trim() !== "true") {
        ctx.ui.notify(`Not a Git repository: ${agentDir}`, "error");
        return;
      }

      const status = await git(["status", "--short", "--untracked-files=all"]);
      if (status.code !== 0) {
        ctx.ui.notify("Could not inspect the Pi agent repository.", "error");
        return;
      }
      if (!status.stdout.trim()) {
        ctx.ui.notify("No Pi agent changes to snapshot.", "info");
        return;
      }

      const confirmed = await ctx.ui.confirm(
        "Pi configuration snapshot",
        `${status.stdout.trim()}\n\nStage all listed changes and create a local commit?`,
      );
      if (!confirmed) return;

      const added = await git(["add", "--all"]);
      const message = args.trim() || `pi snapshot ${new Date().toISOString().slice(0, 19).replace("T", " ")} UTC`;
      const commit = added.code === 0 ? await git(["commit", "-m", message]) : added;
      ctx.ui.notify(
        commit.code === 0 ? "Saved the Pi configuration snapshot." : "Failed to save the Pi configuration snapshot.",
        commit.code === 0 ? "info" : "error",
      );
    },
  });
}
