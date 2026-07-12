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
|---|---|
| `sum` (default) | the metrics grow **in total** — paying off debt in one metric offsets taking it on in another |
| `any` | **any single** metric grows, whatever else improved |

```toml
[check]
policy = "sum"        # or "any"
ignore = ["loc"]      # metrics that never fail the check
```

`--policy sum|any` overrides the config for a single run.

Under `sum`, a metric can grow and the branch still pass. Its added lines
are still printed, because the trade is worth seeing even when it is
allowed.

## Ignoring metrics

`ignore` names metrics that are expected to grow — lines of code, say. They
take no part in the check: they neither move the total nor fail the build,
and they stay out of the output.

A name that matches no configured metric is a config error, so a typo cannot
silently ignore nothing.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | the branch worsened nothing |
| `1` | the branch is a regression under the active policy (or a metric function failed) |
| `2` | config or usage error |

## GitHub Actions

A complete workflow that fails a pull request which takes on debt:

```yaml
name: Metrics

on: [pull_request]

jobs:
  metrics:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # check needs history for the merge-base
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install tingle
      - run: tingle check
```

!!! warning "`fetch-depth: 0` is not optional"

    `actions/checkout` clones shallow by default, and `check` needs history
    to find the merge-base with the base branch. Without it the job fails on
    every run.

### Advisory: report without blocking the merge

To see the branch's debt on every pull request without gating it, put
`check` in its own job with `continue-on-error: true`. The job goes red when
the branch worsens the metrics — so the number is visible in the checks list
— but the workflow's overall conclusion stays green, so the merge is not
blocked. This is how tingle's own CI runs it.

```yaml
  metrics:
    runs-on: ubuntu-latest
    continue-on-error: true     # report, but never block the merge
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: pip install tingle
      - run: tingle check
```

!!! note "Branch protection overrides this"

    `continue-on-error` keeps the *workflow* from failing, but it does not
    make a check non-required. If the job is listed as a required status
    check in a branch protection rule, it will still block the merge. Leave
    it out of that list.

This pairs well with `[check] ignore` and `policy = "sum"`: start advisory
to learn what your branches actually do to the numbers, then drop
`continue-on-error` once the baseline is honest.

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
