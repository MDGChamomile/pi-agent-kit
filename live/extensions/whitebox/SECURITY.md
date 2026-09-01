# Whitebox security policy and threat model

Whitebox is an early, Linux-only safety boundary for inspecting disposable project checkouts with Pi. It reduces exposure to project commands; it is not a general-purpose malware sandbox or a substitute for an independently isolated virtual machine.

## Supported version

Whitebox is currently maintained from the `main` branch of this repository. There are no separately supported releases. Runtime startup requires the bounded Pi version range listed in the README and blocks prerelease versions, later minor or major lines, and versions known to be incompatible. Stable patch releases inside that range but outside the validated test matrix start with a warning after package identity checks pass. Security-relevant startup, trusted-source overlap, tool-ownership, path, namespace, and runtime checks remain fail-closed.

## Intended protections

When started through `piw`, Whitebox is designed to:

- run project commands without network access, inherited environment variables, host credentials, or access to the host home directory beyond the workspace and documented read-only runtime mounts;
- expose only the writable project workspace, a read-only root `.git` directory, temporary filesystems, and the documented read-only runtimes;
- confine Pi's `read`, `write`, `edit`, `grep`, `find`, and `ls` tools to the workspace;
- block host Bash and user `!` / `!!` commands;
- fail closed when startup, trusted-source overlap, tool ownership, path, namespace, or runtime checks fail;
- require the selected executable to match the owning Pi package's declared `bin.pi`, and use that same canonical package for the host process and sandbox file worker;
- preserve raw capture bytes while sanitizing capture text returned to Pi/model context; and
- bound command and file-tool time, captured output, temporary storage, and concurrent workspace execution. File-tool deadlines use cooperative cancellation during workspace validation, so a non-interruptible host filesystem call may delay observed cancellation.

## Trusted components

Whitebox trusts the host kernel, Bubblewrap, `flock`, the Pi process, the model provider connection, the selected Node/npm/Pi runtime files, the Whitebox extension source, and any additional extension the user explicitly loads. These components run outside or form part of the Whitebox boundary. The launcher rejects a workspace that overlaps the Whitebox source or selected Pi package so sandboxed commands cannot rewrite code trusted by a later run.

## Out of scope

Whitebox does not protect against:

- damage, deletion, or disclosure of anything placed in the writable workspace;
- project secrets being read by commands or Pi and sent over the model connection;
- project context files such as `AGENTS.md` influencing model behavior;
- vulnerabilities in the host kernel or trusted runtime components;
- strongly malicious workloads that require a virtual machine or separate host;
- complete CPU, memory, process, or workspace disk exhaustion control;
- the Pi process, model connection, or explicitly loaded third-party extensions; or
- interactive programs, network-dependent work, host credential use, or Git mutation.

Symlinks, hard links, nested mounts, IPC nodes, root `.git` writes, process descendants, output limits, and actual Pi entry-point behavior are covered by the integration tests. Passing tests are evidence for the tested environment, not a security certification.

## Reporting a suspected vulnerability

Do not publish exploit details, credentials, or sensitive host information in a public issue. Use GitHub's [private vulnerability reporting](https://github.com/MDGChamomile/pi-agent-kit/security/advisories/new) to send a confidential report to the maintainer.

Non-sensitive defects and hardening suggestions may be reported through the normal issue tracker.
