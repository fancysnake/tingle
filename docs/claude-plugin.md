# Claude Code plugin

`tingle-config` is a [Claude Code](https://claude.com/claude-code) skill that
writes tingle configuration. Ask Claude to set tingle up, add a metric, or
review the config a project already has, and the skill surveys before it
edits: the languages and tools actually in use, the layout, the rules the
project has already written down. A marker the code does not leave behind
does not become a metric.

## Install

This repository is the marketplace:

```console
claude plugin marketplace add fancysnake/tingle
claude plugin install tingle-config@tingle
```

The skill loads itself when a request is about tingle. Nothing else needs
configuring:

```text
> set up tingle for this repo
> add a metric for the tests we skip
> review tingle.toml — is anything in there not worth counting?
```

## What it does

1. **Finds the current state** — whether tingle is installed, whether a
   config exists, and what the installed version supports.
2. **Surveys the project** — manifests and tool configs for the languages in
   play, the layout for [ranges](configuration.md#ranges), stated rules for
   the metrics worth having, then greps each candidate marker for its count.
3. **Writes the config** — the [bundled templates](library.md) for Python
   tools, hand-written [metrics](metrics.md) for everything else, with the
   caveats that bite: which types read a config file rather than a range,
   how a base is overridden, what `regex_count` cannot match in diff mode.
4. **Verifies** — `tingle list`, `tingle stat` and `tingle report` over what
   it wrote, excusing false positives with `ignore_lines`.

The skill is a compressed form of [Configuration](configuration.md) and
[Metric types](metrics.md), which stay authoritative where the two disagree.

## Beyond Python

tingle is a Python package, but the markers it counts are not. The skill
carries starting patterns for JS/TS, Rust, Go, Ruby, PHP, Java/Kotlin, C#,
shell, templates, CSS, Markdown, YAML, Dockerfile, Terraform and CI configs,
and knows to reach for `pipx run tingle` or `uvx tingle` in a repository
that has no Python environment of its own.

## Versions

The plugin carries the package version: the skill describes this code, so it
has no release of its own. `claude plugin update` therefore moves it on any
tingle release, whether or not the skill itself changed.
