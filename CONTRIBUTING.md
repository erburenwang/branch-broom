# Contributing

Branch Broom is a Python 3.11+ CLI with no runtime dependencies. It only inspects local Git metadata and never contacts a remote.

## Local checks

```sh
python -m compileall -q src
python -m branch_broom --help
```

For a manual feature check, use a disposable Git repository. Do not run `scan --apply` against a repository whose branches you want to keep.

## Change guidelines

- Keep scans read-only by default.
- Never add remote deletion, force deletion, fetching, or file-content scanning to the apply path.
- Preserve JSON field names and document schema changes.
- Keep Git invocations as argument arrays with shell execution disabled.
