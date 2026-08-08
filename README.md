# Pi Agent Kit

A curated, open-source collection of skills and extensions for the [Pi coding agent](https://github.com/earendil-works/pi).

## Install

```bash
pi install git:github.com/MDGChamomile/pi-agent-kit
```

Try it without installing:

```bash
pi -e git:github.com/MDGChamomile/pi-agent-kit
```

Pi packages run with your user permissions. Review the source before installing or updating.

## Skills

| Skill | Purpose | Invoke |
| --- | --- | --- |
| `deep-plan` | Turn a vague repository change into an aligned execution record | `/skill:deep-plan` |
| `meta-prompt` | Write or improve a compact, ready-to-use prompt | `/skill:meta-prompt` |

## Extensions

| Extension | Purpose |
| --- | --- |
| `welcome` | Show a startup overview with model, resources, and recent sessions |
| `git-history` | Add `/snapshot` to review and commit changes in the Pi agent directory |

`/snapshot` stages all changes in the configured Pi agent directory only after showing the status and receiving confirmation. Use it only when that directory is an intentional Git repository.

## Layout

```text
extensions/   Pi TypeScript extensions
skills/       Agent Skills-compatible skill directories
```

Pi discovers both resource types through the manifest in [`package.json`](package.json).

## Contributing

Issues and pull requests are welcome. Keep additions focused, portable, documented, and free of credentials or machine-specific paths.

## License

[MIT](LICENSE)
