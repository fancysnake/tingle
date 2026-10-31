---
description: "tingle check fails CI when a pull request adds tech-debt markers: it measures the branch against its merge-base and exits 1 when its metrics grow — in total by default, or any one under the any policy."
---

# CI gate

`tingle check` is [`stat --diff`](diff.md) with an opinion. It measures the
same branch impact, then **exits 1 if the branch made things worse** — so a
pull request that takes on debt fails the build.

Output is trimmed to what CI needs: the metrics that grew, and only the
lines the branch added.

```console
$ tingle check
noqa-comment (regex_count): +2
  + src/api/views.py:23
  + src/api/views.py:41

ruff-ignores (toml_list_length): +1
  + pyproject.toml: D203

$ echo $?
1
```

A branch that worsens nothing prints nothing and exits 0.

## Policies

Two policies decide what "worse" means:

| Policy | Fails when |
| --- | --- |
| `sum` (default) | the metrics grow **in total** — paying off debt in one metric offsets taking it on in another |
| `any` | **any single** metric grows, whatever else improved |

```toml
[check]
policy = "sum"        # or "any"
ignore = ["loc"]      # metrics that never fail the check
```

Only the config decides what the gate judges and how: `check` takes no
option that changes the policy or narrows the metrics, so loosening the gate
is a config change a review can see.

Under `sum`, a metric can grow and the branch still pass. Its added lines
are still printed, because the trade is worth seeing even when it is
allowed.

## Ignoring metrics

`ignore` names metrics that are expected to grow — lines of code, say. They
take no part in the check: they neither move the total nor fail the build,
and they stay out of the output.

A name that matches no configured metric is a config error, so a typo cannot
silently ignore nothing.

## Gating on spread rather than volume

`ignore` is the blunt instrument. Where a metric is not so much expected to grow
as expected to *churn*, the sharper answer is to gate on how far the thing has
spread instead of how often it is written:
[`regex_spread` and `symbol_spread`](metrics.md#spread-regex_spread-and-symbol_spread)
count the files a thing appears in, so a branch that reworks legacy code passes
while a branch that carries it into a new file does not.

It is the difference between "stop using this" and "stop spreading this", and
only the second can be gated on without failing every bug fix.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | the branch worsened nothing |
| `1` | the branch is a regression under the active policy (or a metric function failed) |
| `2` | config or usage error |

## GitHub Actions

A complete workflow that fails a pull request which takes on debt:

```yaml
name: Metrics

on: [pull_request]

jobs:
  tingle:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # check needs history for the merge-base
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install tingle
      - run: tingle check
```

!!! warning "`fetch-depth: 0` is not optional"

    `actions/checkout` clones shallow by default, and `check` needs history
    to find the merge-base with the base branch. Without it the job fails on
    every run.

### Adopting the gate

There is no advisory mode: `continue-on-error` is a tolerated failure, the
very thing tingle counts. Settle the config before the gate goes in. Run
[`tingle report`](cli.md#tingle-report) over the whole tree, fix each false
positive in the config with a narrower pattern, an `ignore_lines` entry or a
range `exclude`, and name in `[check] ignore` the metrics that are expected
to grow. From then on, the gate fails every branch that takes on debt.

### Feedback on the pull request

A failing job says the branch took on debt; the reviewer still has to open
the log to see where. The `pr-feedback` action puts it where review happens.
It runs `check`, then:

- **annotates** each line the branch added debt on, under the metrics that
  grew: an error when the check fails, a warning when the policy let it pass;
- **comments** once on the pull request with the per-metric delta and every
  addition, and edits that comment on each push rather than adding another.

It fails the step exactly when `check` does, so it replaces the `check` step:

```yaml
  tingle:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write    # the comment
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: pip install tingle
      - uses: fancysnake/tingle/actions/pr-feedback@main
```

| Input | Default | Meaning |
| --- | --- | --- |
| `config` | auto-discovered | path to `tingle.toml`; annotations follow it into a subdirectory |
| `comment` | `true` | `false` keeps the annotations and posts no comment |
| `key` | the config path | names the comment a run owns; give each config its own when one pull request runs several |
| `github-token` | `github.token` | token used to read and write the comments |

!!! note "What GitHub will not show"

    GitHub shows at most ten annotations of each level per step, so a branch
    adding more is annotated in part; the comment lists every addition. A
    pull request from a fork gets a read-only token: the annotations still
    land, the comment is skipped with a warning.

Annotations sit on lines; an addition with no line — a list entry such as a
new ruff ignore, or a whole new file — annotates the file instead.

### Publishing the numbers

`check` only judges. To also record the values, add `stat --json` — it is a
separate command and does not affect the exit code:

```yaml
      - run: tingle stat --json > metrics.json
      - run: jq -r '.metrics[] | "\(.name)\t\(.value)"' metrics.json
      - uses: actions/upload-artifact@v4
        with:
          name: metrics
          path: metrics.json
```

An artifact is a file, not a history — it expires and nothing plots it. To
keep the values and chart them over time, see [History](history.md).

## GitLab

Set `GIT_DEPTH: 0` so the merge-base is reachable. `tingle report
--cobertura` emits Cobertura XML in which each occurrence line is an
uncovered line, which the MR widget consumes directly.

```yaml
tingle:
  variables:
    GIT_DEPTH: 0
  script:
    - tingle check
    - tingle report --cobertura > tingle.xml
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: tingle.xml
```

## Git hooks

CI judges the branch; a hook only reports, before the commit leaves your
machine. `tingle report --diff --base HEAD` measures your uncommitted changes
against the last commit and lists what they add and remove; it fails only
on a config bug: a metric that errors, or a config or diff it cannot load.
A hook that failed on new debt would leave `--no-verify` as the way past a
false positive, and that is a suppression; the fix belongs in the config, and
the gate in CI.

The hook measures the working tree. pre-commit stashes unstaged edits but not
untracked files, so a stray untracked file with a `# noqa` in it shows up in
the report even though the commit leaves it out.

### pre-commit

```yaml
repos:
  - repo: https://github.com/fancysnake/tingle
    rev: v0.10.0
    hooks:
      - id: tingle
```

pre-commit installs tingle from the tag `rev` names, so the hook needs no
`pip install`. The hook is `verbose`, so pre-commit prints its report even
though it passes.

To report on the whole branch at push instead, run the hook at the push stage
and drop its `--base HEAD`, so it falls back to `[diff] base`, then `main`:

```yaml
      - id: tingle
        stages: [pre-push]
        args: [--diff]
```

The push hook measures your checkout, not the commits you push: the working
tree and its untracked files against the merge-base, with nothing stashed.
Push from a clean tree and the two agree.

### hk

tingle publishes no hk package; the step is one line in your `hk.pkl`, and it
runs the `tingle` on your `PATH`:

```pkl
amends "package://github.com/jdx/hk/releases/download/v2.8.1/hk@2.8.1#/Config.pkl"

hooks {
  ["pre-commit"] {
    steps {
      ["tingle"] { check = "tingle report --diff --base HEAD" }
    }
  }
}
```
