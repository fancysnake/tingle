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

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0                              # check needs the merge-base
- run: tingle check                             # fails the build on new debt
- run: tingle stat --json > metrics.json
- run: jq -r '.metrics[] | "\(.name)\t\(.value)"' metrics.json
- run: tingle report --cobertura > tingle.xml   # e.g. GitLab MR annotations
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

!!! warning "Shallow clones fail"

    `check` needs history to find the merge-base. A default shallow clone
    (`fetch-depth: 1`) will fail.
