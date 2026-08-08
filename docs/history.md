# History

tingle stores nothing: every run measures the tree in front of it. To watch
a number drop over months, something has to keep the values — and on GitHub
that something is a **branch**, not an artifact.

!!! warning "Artifacts are not history"

    `upload-artifact` gives you a file per run. Artifacts expire (90 days by
    default), each is a separate download, and nothing plots them. Use them
    to hand a number to the next job in the same workflow, not to remember
    it.

## The short version

tingle ships a reusable workflow that records the numbers on every main
build and publishes a chart of the history. The whole caller is this:

```yaml
name: Metrics

on:
  push:
    branches: [main]

jobs:
  history:
    permissions:
      contents: write     # the values are committed to a branch
    uses: fancysnake/tingle/.github/workflows/metrics-history.yml@main
```

Each run installs tingle, takes `stat --json`, appends the values to the
`gh-pages` branch under `metrics/`, and commits a page that plots one
time-series per metric, every point linked to the commit that produced it.

Turn Pages on — *Settings → Pages → Deploy from a branch → `gh-pages`* — and
the chart is at `https://<owner>.github.io/<repo>/metrics/`.

!!! note "Pin the version"

    `@main` tracks the tip. Once it ships in a release, pin the tag —
    `@v0.5.0` — or a commit sha, like any other action.

### Permissions

`contents: write` has to be granted **by the caller**, as above. A called
workflow can narrow what the caller holds, never widen it, so declaring the
permission inside the reusable workflow would not help. The built-in
`GITHUB_TOKEN` is enough; no personal access token is needed to push to your
own repository.

### Inputs

| Input | Default | Meaning |
|---|---|---|
| `name` | `tingle` | chart title; keep it stable, it keys the stored series |
| `python-version` | `3.x` | Python that runs tingle |
| `tingle-version` | latest | version to install, e.g. `0.4.0` |
| `config` | auto-discovered | path to `tingle.toml` |
| `data-branch` | `gh-pages` | branch the history is committed to |
| `data-dir` | `metrics` | directory in that branch holding the chart |
| `max-points` | every build | points kept per metric chart |

## When Pages is already taken

A repository has **one** Pages source. If yours is deployed from a workflow
artifact — MkDocs, Sphinx, any static generator, which is how these docs are
published — you cannot also serve the `gh-pages` branch. Point the data at a
branch of its own instead:

```yaml
    with:
      data-branch: metrics-data
```

Nothing renders it, but the history is now a file you own:
`metrics/data.js` on that branch, a single `window.BENCHMARK_DATA = {...}`
assignment keyed by commit. Fetch that branch during your docs build and
plot it into a page of your site, or read it from anywhere else that wants
the numbers.

## What it does, unrolled

Three steps, if you would rather inline them — or adapt them to a CI that is
not GitHub Actions:

```yaml
      - run: tingle stat --json > stat.json
      - run: jq '[.metrics[] | select(.error == null) | {name, unit: "count", value}]' stat.json > points.json
      - uses: benchmark-action/github-action-benchmark@v1
        with:
          name: tingle
          tool: customSmallerIsBetter
          output-file-path: points.json
          github-token: ${{ secrets.GITHUB_TOKEN }}
          auto-push: true
          benchmark-data-dir-path: metrics
```

`customSmallerIsBetter` is that action's generic contract — a list of
`{name, unit, value}` objects, lower is better — which is exactly the shape
of a tingle metric. The `jq` drops metrics that errored, since they have no
value to plot; the workflow names them in the log first.

!!! note "Leave the alerts off"

    The action can comment on, and fail, a run whose value regressed. The
    reusable workflow turns both off: [`tingle check`](check.md) already
    gates pull requests, and it judges the branch's own impact rather than
    the raw jump between two builds. The action's threshold is also a ratio,
    which says nothing useful about a count sitting at 0.
