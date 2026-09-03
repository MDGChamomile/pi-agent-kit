# Pi Whitebox

> [!WARNING]
> **Retired:** Whitebox is preserved as a reference and is no longer actively used, maintained, or supported. Its Pi compatibility and security boundary may become stale; do not treat its historical tests or documentation as current security assurance.

Whitebox is a Linux-only Pi extension for running test, build, and project scripts inside a strict offline Bubblewrap boundary.

It keeps the model free to choose how to work while enforcing a small set of hard boundaries around project command execution and Pi's file tools.

## Boundary

In Whitebox mode:

- `whitebox_run` executes commands with the current Git workspace mounted read/write.
- The root `.git` directory is mounted read-only.
- Sandboxed commands receive no network, inherited environment variables, Pi sessions, or host credentials. They can access the workspace and the read-only runtime mounts listed below, but not the rest of the host home directory.
- Pi's `read`, `write`, `edit`, `grep`, `find`, and `ls` tools are confined to the workspace.
- Host Bash and user `!` / `!!` commands are blocked.
- Time, output, and concurrent execution are bounded.
- Startup, trusted-source overlap, runtime identity, and tool-ownership checks fail closed.

Whitebox isolates project commands and those six file tools. It does **not** sandbox the entire Pi process, the model connection, other explicitly loaded extensions, or the writable project itself.

Use a disposable checkout with no important uncommitted files or secrets. Use a separate virtual machine for strongly malicious or resource-exhaustion workloads.

## Requirements

- Linux
- Node.js 22.19 or newer; the selected distribution must include executable `node`, `npm`, and `npx`, Node headers, and the npm runtime
- Pi coding agent 0.84.2 or newer within the 0.84.x line; known-incompatible and prerelease versions are blocked, while unvalidated 0.84.x patch releases start with a warning
- `/usr/bin/bwrap` with `--disable-userns` support (Bubblewrap 0.8.0 or newer) and `/usr/bin/flock`; both must be canonical, root-owned regular executables that are non-setuid and not group/world-writable
- `bash`, `python3`, `git`, and ripgrep (`rg`) under `/usr/bin`
- `fd` as `/usr/bin/fd` or Debian/Ubuntu's `/usr/bin/fdfind`
- Optional for native builds: `make`, `cc`, and `c++` (not required for Whitebox startup)
- A normal Git repository root with a real `.git` directory; worktrees are not supported
- Unprivileged user namespaces enabled

At retirement, the boundary had been validated with Node.js 22.22.3, Pi 0.84.2 and 0.84.3, Bubblewrap 0.9.0, and Linux 6.8. Compatibility beyond that frozen matrix is not maintained.

## Historical setup (unsupported)

The checkout setup before retirement was:

```bash
git clone https://github.com/MDGChamomile/pi-agent-kit.git
cd pi-agent-kit/retired/extensions/whitebox
npm install
npm link
```

This setup installed the `piw` launcher. Pi had to be installed alongside the current Node distribution or available on `PATH`. The launcher refused to start when the selected Pi package or the Whitebox extension source overlapped the workspace. The linked Whitebox checkout had to remain outside inspected projects; inspecting this repository itself required a separate installed copy.

## Historical operation

Whitebox was started from the root of the disposable project to inspect:

```bash
cd /path/to/project
piw
```

The launcher deliberately started Pi with only Whitebox loaded:

```text
pi --no-extensions -e <whitebox>/index.ts --no-skills --no-approve --whitebox
```

Additional command-line arguments are forwarded to Pi. Explicitly loading another extension expands the trusted boundary because extensions run with host permissions; the ready status reports additional active host-side tools. Before starting, the launcher verifies the selected Pi package, executable, and supported version. Security-relevant identity, path, runtime, and tool-ownership checks fail closed. See [SECURITY.md](SECURITY.md) for the full threat model.

## Historical scope

**Good fits:**

- tests, builds, linters, and project scripts
- existing Node.js and Python tooling
- read-only Git inspection such as `git status`, `git diff`, and `git log`

**Not supported:**

- network access or package downloads
- commands needing host credentials
- interactive programs
- Git mutation such as commit, merge, rebase, fetch, pull, or push

The default command timeout is 120 seconds and the maximum is 900 seconds. Command results return only the last 12 KiB or 400 lines inline; larger output is saved as a capture for on-demand `read` or `grep`. Progress updates retain only the latest 4 KiB. File-tool calls have a 120-second parent-enforced deadline with cooperative cancellation during workspace validation. If combined observed stdout and stderr exceeds 10 MiB, the command is terminated with `output_limit`; captured bytes are capped at 10 MiB, and a new capture replaces the previous capture and its read authorization.

## Security notes

- The workspace is writable and can be damaged or deleted.
- Everything in the workspace is readable by sandboxed commands and Pi's file tools and may be sent over the model connection. Whitebox is not a confidentiality boundary for project contents.
- Project context files such as `AGENTS.md` may still be read by Pi and influence model behavior. Add `--no-context-files` only if you understand that it also disables your global context instructions.
- Read-only host files under `/usr`—including any Node packages installed there—and selected identity/runtime files under `/etc` are visible inside the sandbox so supported tools can run. Only the selected Node/npm/Pi runtime is additionally mounted under `/opt/node`; the host Node prefix is not mounted wholesale there. The inner runtime sets `PI_OFFLINE=1`; `rg` and `fd` must already be installed instead of being downloaded by Pi.
- Capture files preserve the exact raw bytes. When a capture is read or searched through a Whitebox file tool, text returned to Pi and the model is sanitized for control and bidirectional-display characters; ordinary workspace-file results keep Pi's native behavior.
- CPU, memory, and workspace disk exhaustion are not fully controlled.
- Whitebox reduces risk; it is not a substitute for an independently isolated host.

See [SECURITY.md](SECURITY.md) for the threat model and vulnerability-reporting guidance.

## Historical tests

```bash
npm test
```

The full suite creates temporary Git workspaces and checks filesystem, network, environment, namespace, lifecycle, file-tool, and actual Pi entry-point boundaries. It does not execute code from an external project. The retired copy is not exercised by live CI.

## License

MIT
