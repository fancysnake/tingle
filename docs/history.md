# History

tingle stores nothing: every run measures the tree in front of it. To watch
a number drop over months, something has to keep the values — and on GitHub
that something is a **branch**, not an artifact.

!!! tip "See one first"

    tingle keeps its own history this way, and publishes it:
    **[the chart beside this page][own]**. One line per metric, every point
    linked to the commit that produced it — that is what the rest of this
    page sets up.

!!! warning "Artifacts are not history"

    `upload-artifact` gives you a file per run. Artifacts expire (90 days by
    default), each is a separate download, and nothing plots them. Use them
    to hand a number to the next job in the same workflow, not to remember
    it.

## The short version

tingle ships an action that records the numbers and publishes a chart of
their history. History is a **main-branch** thing — one point per commit
that landed — so the whole workflow is this:

```yaml
name: Metrics

on:
  push:
    branches: [main]

jobs:
  history:
    runs-on: ubuntu-latest
    permissions:
      contents: write     # the values are committed to a branch
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install tingle
      - uses: fancysnake/tingle/actions/metrics-history@main
```

The action expects `tingle` on `PATH`, so it can also join a job that
already runs it — [the CI gate](check.md), measuring the build the gate
judged. That job has to run on main pushes as well as pull requests, and
the step has to skip the pull requests:

```yaml
      - run: tingle check
      - uses: fancysnake/tingle/actions/metrics-history@main
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

!!! warning "Record on main, not on pull requests"

    Without that `if:`, every pull request appends a point for a commit that
    may never land — and one from a fork cannot append at all: its
    `GITHUB_TOKEN` is read-only whatever `permissions:` asks for, so the
    push fails and takes the job with it.

The recording step switches the checkout to the data branch and back, so
the job's tracked files have to be clean by the time it runs — git will not
switch away from a modified file. A build that rewrites a lockfile or a
generated file has to commit or discard it first; the action stops with a
named error rather than a raw git one.

Each run takes `stat --json`, appends the values to the `gh-pages` branch
under `metrics/`, and commits a page that plots one time-series per metric,
every point linked to the commit that produced it.

Turn Pages on — *Settings → Pages → Deploy from a branch → `gh-pages`* — and
the chart is at `https://<owner>.github.io/<repo>/metrics/`.

!!! note "Pin the version"

    `@main` tracks the tip. Once it ships in a release, pin the tag —
    `@v0.5.0` — or a commit sha, like any other action.

### Permissions

The job needs `contents: write`, as above: recording a value means pushing a
commit. The built-in `GITHUB_TOKEN` carries that scope once the job asks for
it; no personal access token is needed to push to your own repository.

Grant it on the **job**, not the workflow, so the rest of the build keeps
the default read-only token.

### The data branch

The action creates the branch when it does not exist yet — an orphan, so the
history shares no commits with your source — and pushes to it from then on.
Nothing to set up before the first run.

### Inputs

| Input | Default | Meaning |
|---|---|---|
| `name` | `tingle` | chart title; keep it stable, it keys the stored series |
| `config` | auto-discovered | path to `tingle.toml` |
| `data-branch` | `gh-pages` | branch the history is committed to |
| `data-dir` | `metrics` | directory in that branch holding the chart |
| `max-points` | every build | points kept per metric chart |
| `github-token` | `github.token` | token used to push to the data branch |

### A metric that fails does not lose the point

`stat` exits 1 when a metric raises — it names the metric on stderr, and
still reports every metric that worked. The action follows that: the broken
one is dropped from the chart, the rest are recorded. Only a run where
*every* metric failed has nothing to plot, and that fails the job.

## When Pages is already taken

A repository has **one** Pages source. If yours is deployed from a workflow
artifact — MkDocs, Sphinx, any static generator, which is how these docs are
published — you cannot also serve the `gh-pages` branch. Point the data at a
branch of its own instead:

```yaml
      - uses: fancysnake/tingle/actions/metrics-history@main
        with:
          data-branch: metrics-data
```

This is how tingle records its own metrics. The branch still holds the chart
the action generates — it is simply not served from there, so fetch it into
your source tree **before** the build, in the job that publishes the site:

```yaml
      - uses: fancysnake/tingle/actions/metrics-history/publish@main
        with:
          data-branch: metrics-data
          into: docs/history/chart
      - run: mkdocs build --strict
```

`into:` is a path your generator copies verbatim into its output — `docs/`
for MkDocs, `content/` or `static/` elsewhere. The chart is then a page of
your documentation like any other, and the link to it is a relative one your
build checks, rather than an absolute URL nobody validates. tingle's own is
[the chart this page opened with][own], published exactly this way.

| Input | Default | Meaning |
|---|---|---|
| `data-branch` | `gh-pages` | branch the history was recorded to |
| `data-dir` | `metrics` | directory in that branch holding the chart |
| `into` | required | directory the chart is copied into |
| `github-token` | `github.token` | token used to read the data branch |

The chart is self-contained — an `index.html` that loads its `data.js`
beside it — so commit a placeholder `index.html` at `into:` and ignore the
`data.js` that lands next to it. The step tolerates exactly one failure, the
data branch not existing yet, which is every repository's first run: the
placeholder is what ships in its place, and the build still passes. Every
other failure stops the job rather than deploying a site whose chart link is
dead.

  [own]: history/chart/index.html

The history is also a file you own: `metrics/data.js`, a single
`window.BENCHMARK_DATA = {...}` assignment. Its `entries` are keyed by chart
name — the `name` input — and each is an array of points, one per recorded
build, carrying that build's commit metadata and a `benches` list of
`{name, unit, value}` objects:

```js
window.BENCHMARK_DATA = {
  lastUpdate: 1767225600000,
  repoUrl: "https://github.com/owner/repo",
  entries: {
    tingle: [
      {
        commit: { id: "…", timestamp: "…", message: "…", url: "…" },
        date: 1767225600000,
        tool: "customSmallerIsBetter",
        benches: [{ name: "noqa-comments", unit: "count", value: 3 }]
      }
    ]
  }
};
```

Fetch that branch during your docs build and plot it into a page of your
site, or read it from anywhere else that wants the numbers.

## What it does, unrolled

The payload is two steps, if you would rather inline them — or adapt them to
a CI that is not GitHub Actions. Every input above is left at its default
here, so this is the action's own body:

```yaml
      - run: |
          status=0
          tingle stat --json > stat.json || status=$?
          [ "$status" -le 1 ] || exit "$status"
          jq '[.metrics[] | select(.error == null) | {name, unit: "count", value}]' \
            stat.json > points.json
          if [ "$(jq length points.json)" -eq 0 ]; then
            echo "::error::every metric errored; there is nothing to record"
            exit 1
          fi
      - uses: benchmark-action/github-action-benchmark@52576c92bccf6ac60c8223ec7eb2565637cae9ba # v1.22.1
        with:
          name: tingle
          tool: customSmallerIsBetter
          output-file-path: points.json
          github-token: ${{ github.token }}
          auto-push: true
          benchmark-data-dir-path: metrics
          comment-on-alert: false
          fail-on-alert: false
```

`customSmallerIsBetter` is that action's generic contract — a list of
`{name, unit, value}` objects, lower is better — which is exactly the shape
of a tingle metric. The `jq` drops metrics that errored, since they have no
value to plot, and the exit-status line keeps a single broken metric from
killing the run.

Inlined this way, the branch is your problem: the benchmark action fetches
it and fails on a raw git error if it is missing. Create it once —

```sh
git checkout --orphan gh-pages && git commit --allow-empty -m "Start gh-pages"
git push origin gh-pages
```

— or use the action, which does it for you.

!!! note "Leave the alerts off"

    The action can comment on, and fail, a run whose value regressed. This
    one turns both off: [`tingle check`](check.md) already gates pull
    requests, and it judges the branch's own impact rather than the raw jump
    between two builds. The alert threshold is also a ratio, which says
    nothing useful about a count sitting at 0.
