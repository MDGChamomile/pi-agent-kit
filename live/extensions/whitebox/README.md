# Pi Whitebox

[한국어](README.ko.md)

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
- Node.js 22.19 or newer
- Pi coding agent 0.84.2 or 0.84.3 (exact tested-version allowlist; other versions fail closed)
- `/usr/bin/bwrap` with `--disable-userns` support (Bubblewrap 0.8.0 or newer) and `/usr/bin/flock`
- `bash`, `python3`, `git`, and ripgrep (`rg`) under `/usr/bin`
- `fd` as `/usr/bin/fd` or Debian/Ubuntu's `/usr/bin/fdfind`
- Optional for native builds: `make`, `cc`, and `c++` (not required for Whitebox startup)
- A normal Git repository root with a real `.git` directory; worktrees are not supported
- Unprivileged user namespaces enabled

The current boundary has been tested with Node.js 22.22.3, Pi 0.84.2 and 0.84.3, Bubblewrap 0.9.0, and Linux 6.8.

## Install from a checkout

```bash
git clone https://github.com/MDGChamomile/pi-agent-kit.git
cd pi-agent-kit/live/extensions/whitebox
npm install
npm link
```

This installs the `piw` launcher. Pi must already be installed alongside the current Node distribution or available on `PATH`. The launcher refuses to start when the selected Pi package or the Whitebox extension source overlaps the workspace. Keep the linked Whitebox checkout outside projects you inspect; use a separate installed copy if you need to inspect this repository itself.

## Run

Start Whitebox from the root of the disposable project you want to inspect:

```bash
cd /path/to/project
piw
```

The launcher deliberately starts Pi with only Whitebox loaded:

```text
pi --no-extensions -e <whitebox>/index.ts --no-skills --no-approve --whitebox
```

Additional command-line arguments are forwarded to Pi. Explicitly loading another extension expands the trusted boundary because extensions run with host permissions; the ready status reports additional active host-side tools. The launcher locates the owning package from `package.json`, requires its `bin.pi` target to match the selected executable, pins the sandbox worker to that canonical package, and accepts only the exact Pi versions listed above. The `peerDependencies` wildcard follows Pi's package contract; runtime compatibility is enforced by the allowlist instead.

## Supported work

**Good fits:**

- tests, builds, linters, and project scripts
- existing Node.js and Python tooling
- read-only Git inspection such as `git status`, `git diff`, and `git log`

**Not supported:**

- network access or package downloads
- commands needing host credentials
- interactive programs
- Git mutation such as commit, merge, rebase, fetch, pull, or push

The default command timeout is 120 seconds and the maximum is 900 seconds. Command results return only the last 12 KiB or 400 lines inline; larger output is saved as a capture for on-demand `read` or `grep`. Progress updates retain only the latest 4 KiB. File-tool calls have a 120-second parent-enforced deadline with cooperative cancellation during workspace validation. Captured output is capped at 10 MiB, and a new capture replaces the previous capture and its read authorization.

## Security notes

- The workspace is writable and can be damaged or deleted.
- Everything in the workspace is readable by sandboxed commands and Pi's file tools and may be sent over the model connection. Whitebox is not a confidentiality boundary for project contents.
- Project context files such as `AGENTS.md` may still be read by Pi and influence model behavior. Add `--no-context-files` only if you understand that it also disables your global context instructions.
- Read-only host files under `/usr`, selected identity/runtime files under `/etc`, and a curated Node/npm/Pi runtime under `/opt/node` are visible inside the sandbox so supported tools can run. Other globally installed Node packages are not mounted. The inner runtime sets `PI_OFFLINE=1`; `rg` and `fd` must already be installed instead of being downloaded by Pi.
- Capture files preserve the exact raw bytes. When a capture is read or searched through a Whitebox file tool, text returned to Pi and the model is sanitized for control and bidirectional-display characters; ordinary workspace-file results keep Pi's native behavior.
- CPU, memory, and workspace disk exhaustion are not fully controlled.
- Whitebox reduces risk; it is not a substitute for an independently isolated host.

See [SECURITY.md](SECURITY.md) for the threat model and vulnerability-reporting guidance.

## Test

```bash
npm test
```

The full suite creates temporary Git workspaces and checks filesystem, network, environment, namespace, lifecycle, file-tool, and actual Pi entry-point boundaries. It does not execute code from an external project.

GitHub-hosted runners do not permit the network-namespace operation required by Whitebox. CI therefore runs `npm run test:portable` for the portable policy and extension-wiring tests; `npm test` remains the required full integration check on a supported Linux host.

## License

MIT
