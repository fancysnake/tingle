---
name: glimpse
description: GLIMPSE Architecture Reference — layer responsibilities, slicing rules, growing rules, import boundaries, patterns, and drift red flags.
---

# GLIMPSE Architecture Reference

## Layers

```text
gates   Entry points: request handlers, forms, routing, CLI commands. pacts + mills.
links   Repositories, external clients. pacts + ORM / driver / SDK.
inits   DI container, middleware. Wires links into gates. Only layer that may import gates.
mills   Business logic, services. Depends on pacts + specs. No side-effect imports.
pacts   Protocols, DTOs, errors, enums, TypedDicts. Depends on nothing.
specs   Business invariants (pure constants, no IO). Only for mills.
edges   Settings, wsgi, manage.py. Outside GLIMPSE; optional (CLI projects skip it).
```

Import rules enforced by `importlinter` (`pyproject.toml` →
`[tool.importlinter]`). No exceptions without explicit approval.

**Composition is per-port.** `inits` composes the object graph everywhere; how
it reaches gates differs. Web: the framework dispatches to gates, so `inits`
never imports them — middleware builds `Services()` per request and attaches
it to the request (the framework's thread-safe seam). CLI: nothing dispatches,
so `inits` imports the gate classes, injects mills into their constructors,
and is named by dotted string in `pyproject.toml`
(`[project.scripts]` → `myproject.inits.cli:run`).

**edges is two-way isolated.** Nothing imports `edges`; `edges` imports
nothing first-party — it names project code only by dotted string
(`DJANGO_SETTINGS_MODULE`, `MIDDLEWARE`, `ROOT_URLCONF`). The root middleware
imports services, so it lives in `inits`, not `edges`.

**"Framework-free" means no side effects, not package names.** Forbidden in
`mills`: imports that do IO, touch global state, or own control flow (ORM,
HTTP machinery, settings access). Pure computation is fine wherever it comes
from — `django.utils.text.slugify` qualifies. Enforcement level (ban package /
review-guarded / ban effectful subtrees) is a per-project choice.

**No DDD tactical patterns.** GLIMPSE has no aggregates or value objects —
data moves as DTOs and write TypedDicts; invariants live in service code.
Subdomains/bounded contexts are a borrowed slicing heuristic, not doctrine —
slice by another axis if it fits the project better.

## File layout

**`pacts`, `specs`, `mills`, `inits` start as single modules.** The first three
are sliced by subdomain, and at the start of a project you do not yet know your
subdomains; `inits` splits by what it wires (`repositories.py`, `services.py`),
never by subdomain. Begin with `mills.py`; promote to `mills/` when it earns it
(see **Growing rules**).

**`links` and `gates` are packages from day one.** Their first axis is the port,
and the port is knowable before a line is written — you know you are building a
CLI, you know you are talking to a database. Skipping the axis means renaming
every import the day a second adapter appears.

```text
# Small project — axis-free layers stay flat
pacts.py
specs.py
mills.py
inits.py
gates/{port}/{adapter}.py                   # e.g. gates/cli/argparse.py
links/{port}/{adapter}.py                   # e.g. links/db/sqlite.py

# Grown project
pacts/{subdomain}.py                    # or pacts/{subdomain}/{context}.py
pacts/{port}.py                         # port machinery (e.g. pacts/db.py)
pacts/services.py                       # wiring contracts, mirrors inits
mills/{subdomain}.py                    # or mills/{subdomain}/{context}.py
specs/{subdomain}.py
inits/repositories.py                   # inits splits by what it wires, never by subdomain
inits/services.py
gates/{port}/{adapter}/{subdomain}.py   # or .../{subdomain}/{context}/...
links/{port}/{adapter}/{kind}.py            # while small (models.py, repositories.py)
links/{port}/{adapter}/{kind}/{module}.py   # when {kind} crosses threshold
links/{port}/{adapter}/__init__.py          # facade — re-exports the public surface
```

Split a file at ~1000 lines or when two unrelated concerns cause merge friction.
Never create nested folders before files exist to fill them.

**`__init__.py` re-export policy.** Default: keep `__init__.py` empty and import
each symbol from the module that defines it (`from pkg.foo.bar import Bar`, not
`from pkg.foo import Bar`). A facade `__init__.py` that re-exports a public
surface is allowed only for: a framework or public-API package whose inner
layout is implementation detail (the `links` adapter facade), relief from
line-length pressure, or a pre-existing legacy facade. It is not the default.

## Slicing vocabulary

- **Port** — delivery mechanism named after the domain concept: `cli`, `web`,
  `db`, `payment_api`, `email`
- **Adapter** — specific technology implementing a port: `postgres`, `sqlite`,
  `argparse`, `stripe`, `sendgrid`. One port can have multiple adapters.
- **Subdomain** — broad business area (`auth`, `billing`, `content`)
- **Bounded context** — responsibility boundary with its own ubiquitous
  language. Two contexts can share `User` and mean different things.
- **Entity** — persistence-level concept: the unit a DTO + repository wraps.
  Conceptual, not a file-layout axis: `links` slices by **kind** (per-adapter —
  e.g. `models` / `repositories` for a `db` adapter), not by entity.

Subdomain contains bounded contexts. Bounded context depends on entities.

## Slicing rules

**pacts, mills, specs — by subdomain, then bounded context. inits — by what
it wires.**

```text
pacts/{subdomain}.py                    # flat while subdomain is small
pacts/{subdomain}/{bounded_context}.py  # split when subdomain grows fat
mills/{subdomain}.py
mills/{subdomain}/{bounded_context}.py
specs/{subdomain}.py
inits/repositories.py                   # never inits/{subdomain}.py
inits/services.py
```

Each pacts module holds all boundary contracts for that subdomain/context:
DTOs, write TypedDicts, repository protocols, errors. Split by domain concern,
not by technical kind — no `pacts/dtos.py`, `pacts/protocols.py`, or
`pacts/repos/` directories, and never a `pacts/core.py` or `common` bucket.

**pacts placement algorithm** — pacts mirrors the whole system; place each
contract by three questions, in order: (1) tied to a subdomain? →
`pacts/{subdomain}.py` (DTOs, write dicts, domain errors, repo protocols);
(2) tied to a port? → `pacts/{port}.py` (e.g. `pacts/db.py` for
`TransactionProtocol` — test: would it survive a total change of business
domain?); (3) about the wiring? → mirror the inits registry
(`pacts/services.py` for `ServicesProtocol`).

**Protocols exist where a boundary needs them, not by policy.** Repository
protocols: essential — mills depend on them. Service protocols: optional —
needed for services exposed on the web context (pacts types the namespace) and
recommended for service-to-service dependencies. Gate classes: no protocols —
nothing outside inits refers to them.

**Errors are coarse and shared** (`NotFoundError`, not `ProposalNotFound`);
the gate catching one decides what it means for that screen, at the call-site
— no central error-to-status mapping. Adapter code translates store exceptions
into pacts errors (`IntegrityError` → `DatabaseConstraintError`), so no ORM
exception reaches a mill.

**Boundary vs core — where does it go?** Decide by what the code does. If it
*crosses a boundary* (data shapes moving between layers) it is a contract →
`pacts` (DTOs, protocols). If it *enforces business rules* (service logic,
invariants) it is core → `mills`. DTOs stay in `pacts` even though
they feel like domain objects: repo protocols in `pacts` return them, so moving
them to `mills` would make `pacts → mills → pacts` circular. A DTO is a data
contract for a port, not a domain object.

**Repo methods follow the needs.** Parameters express variation within a use
case; a different scope is a different method. Filtering an event's meetings
by facilitator or topic: parameters. Switching events or including
never-accepted meetings: a second use case → a second method. No generic
query objects through the protocol.

**links — `{port}/{adapter}/{kind}`. gates — `{port}/{adapter}/{subdomain}`.**

```text
# Smallest — the adapter is one module
links/db/sqlite.py
links/payment_api/stripe.py

# Small (default once the kinds separate)
links/{port}/{adapter}/
    __init__.py             # facade — public surface
    kind1.py
    kind2.py

# Promoted when a kind crosses ~1000 lines
links/{port}/{adapter}/
    __init__.py             # facade — unchanged public import path
    kind1/
        __init__.py
        part1.py
        part2.py
    kind2/
        __init__.py
        part1.py
        part2.py

gates/cli/argparse.py               # flat while there is one subdomain
gates/cli/argparse/{subdomain}.py   # or .../{subdomain}/{context}/...
gates/web/{adapter}/{subdomain}.py
```

The `kind` axis and the split philosophy are per-adapter — a `db` adapter is
not the universal template. For a `db` adapter, the kinds are typically
`models` (internal) and `repositories` (public, exposed through the facade
and consumed via the protocols in `pacts`); a `payment_api/stripe` adapter
may stay a single file, or split into transport / types / signer with no
internal-vs-public distinction. **Baseline across adapters: halve, don't
shard; arrange parts so they don't cause circular imports.** The public
face of any `links` adapter is whatever its facade re-exports — internal
modules stay internal. For a `db` adapter specifically, that means external
code does `from myproject.links.db.postgres import SessionRepository` and
never reaches `models`.

One port can have multiple adapters — usually **coexisting**, not
interchangeable: `payment_api/stripe` and `payment_api/paypal` are both wired
and both live, and a mill decides per operation which to call. Genuine
substitution (`db/postgres` vs `db/sqlite`) is the rarer case — one adapter
wired per deployment, chosen in `inits`. One technology can serve multiple
ports: a full-stack framework that ships both an ORM and a request layer
appears as `db/{framework}` and `web/{framework}` — two separate adapters that
share nothing but a name.

**Symmetry rule:** `pacts/` ↔ `mills/` must mirror each other — both sliced by
subdomain/context. If one splits a subdomain into contexts, the other must too.

## Growing rules

**Default: start as small as possible. Split only when size or friction makes
the case for itself.** Premature splitting creates churn, bloats the import
graph, and makes the layout look complete before the requirements actually
demand it.

Concrete thresholds — none is a hard line, all are "watch for this":

- **A layer becomes a package when it earns it.** `pacts`, `specs`, `mills`, and
  `inits` start as single modules. Promote `mills.py` → `mills/` on any one of:
  it crosses ~1000 lines, two unrelated concerns in it cause merge friction, or
  a second subdomain genuinely exists. Not before. `inits` promotes into
  `repositories.py` / `services.py` (+ `middleware.py`), never subdomain files.
  `links` and `gates` are packages from the start — their port axis is known up
  front.
- **~1000 lines per file** — split a file when it crosses this and the two
  halves are unrelated enough that they cause merge friction. A 1500-line file
  holding one tightly coupled service is fine; a 600-line file holding three
  independent services is not.
- **~12 public symbols per namespace level** — applies to repository
  registries, the services tree, pacts subdomain modules, and the inits
  namespaces. At 13+ leaves, introduce a sub-bucket grouped by subdomain or
  bounded context. With ≤12, stay flat.
- **Folder must contain at least 2 files before it exists.** Never create
  `inits/services/billing/invoicing/` for a single leaf. Never create
  `pacts/{subdomain}/{context}.py` while the subdomain has only one context.
  Reverse the speculative scaffold; flatten back when the leaf count drops.
- **Split links by kind first.** Default: one file per kind. When a kind
  crosses ~1000 lines, **promote it to a package** and split into submodules
  (`kind1/part1.py`, `kind1/part2.py`) — same pattern as growing `views.py`
  into `views/`. Do **not** create suffixed siblings (`kind1_a.py`). The
  baseline is **halve, don't shard, and arrange parts to avoid circular
  imports**; the right grouping is adapter-specific (e.g. `db` models often
  split by foreign-key dependency hierarchy — the entities that change
  together — repositories along the same lines; an external-API adapter may
  not need to split at all). The
  `links/{port}/{adapter}/__init__.py` facade keeps the public import path
  stable across the promotion. Framework technicality: if the ORM discovers
  model classes by importing the package (Django does), `models/__init__.py`
  must re-export them; `repositories/__init__.py` can stay empty since the
  facade lives at the parent.

When in doubt, keep it flat. The ~12 rule and the ~1000-line rule are escape
hatches, not invitations.

## Patterns

1. **Entry points return DTOs, never models.** Templates, serializers, and CLI
   output receive DTOs from pacts. ORM instances never leave `links`.
2. **Entry points call services, not repos.** `request.services.<name>.method(...)`
   is the data path out of a view — never import a repo or model in `gates`,
   never reach a repository directly. Services are exposed as a flat namespace
   wired in `inits/services.py`; CLI gates receive theirs at construction.
3. **Services take specific repo protocols + a `TransactionProtocol` via
   constructor** — not imports of concrete repos, not dependencies passed as
   method arguments. With an ambient ORM (Django), never a whole Unit of Work;
   with a session-based ORM (SQLAlchemy) the session already is one, and
   injecting it is idiomatic. ISP at the service boundary: declare the
   two-or-three protocols actually used.
4. **Mills have no side-effect imports.** Only protocols and DTOs from pacts,
   constants from specs, pure helpers from anywhere. No ORM, no HTTP, no CLI
   parser, no settings access.
5. **Writes use TypedDicts.** DTOs for reads, TypedDicts for writes — gates →
   mills as input, mills → links as what repo write methods accept
   (`create(data: CreateProposalDict) -> ProposalDTO`; a `CreateXDict` has no
   `id` — the store assigns it).
6. **Web requests typed via a gate-local typing-only subclass** of the
   framework request (`class RootRequest(HttpRequest): services:
   ServicesProtocol` in the web adapter) — never instantiated; middleware
   mutates the real request. Only `ServicesProtocol` comes from pacts. CLI
   gates have no context.
7. **Multi-repo writes use `transaction.atomic()` from `TransactionProtocol`.**
   Entry points never start transactions; that is a service concern. The
   protocol: `atomic()` and `savepoint()`, both returning a context manager;
   `savepoint()` rolls back only its block on constraint violation,
   re-raising as a pacts error with the outer transaction usable. The
   implementation is inits binding glue, not a links adapter.
8. New repo methods need matching Protocol in pacts.
9. **DTOs must be constructible from a store row or ORM instance** — with
   Pydantic, `model_config = ConfigDict(from_attributes=True)`.
10. New repositories exposed as `@cached_property` on `inits/repositories.py`
    (flat). New services exposed as `@cached_property` on `inits/services.py`
    (flat, zero-arg `Services()` builds its own dependencies — no DI inside
    the composition root). Lifetimes: `@cached_property` = per container
    (per request); `@functools.lru_cache` on a module-level inits factory =
    per process (pooled clients, connections). See **Growing rules** for when
    to bucket.
11. **Protocol implementations declare the protocol as a base class** — where
    a protocol exists — so the intent is explicit and the type checker
    verifies conformance. Exception: very generic structural protocols
    (`TransactionProtocol`, callbacks) with multiple unrelated duck-typed
    implementations.
12. **Gates validate format, mills validate meaning.** A gate checks input
    parses (an email, an int); a mill checks it makes sense ("email or
    username required", seat limits from specs). Parse vs semantics, not
    single-field vs cross-field. Permissions: trivial checks
    (`is_authenticated`) in gates; rule-bearing permission systems in mills.
13. **Django apps are markers, not structure.** An `AppConfig` sits at the
    lowest directory Django must discover (models, commands, templatetags),
    with a custom `label` (names all end in `.django` — default labels
    collide). Migrations live in `links/db/{framework}/migrations/`; admin
    (model-coupled by design) at `links/db/django/admin.py`; plain `Form`s
    only, never `ModelForm`. Framework-owned surfaces (`request.user`,
    `django_login`) are named exemptions — contain them in gates; mills see
    ids and DTOs.

## Dependency direction

**Cross-subdomain access is fine.** Repos cross subdomains freely — data access
is not behavior. An entry point in one subdomain reading another subdomain's
users is normal, not a boundary violation. The smell to watch is duplicated
*behavior* across subdomains; the fix is a shared lower-level mill function
that both call, not a rule against cross-subdomain repo reads.

**Service-to-service calls are fine** when reusing real orchestration. The
genuine smells are narrower: layering inversion (a low-level unit depending on a
high-level orchestrator), cycles, and anemic delegation (one service calling
another for a single trivial read it could do via a repo).

## Testing

The layer under test dictates the test type — not convenience, not what is
easiest for coverage:

- Pure-logic core (`mills`) → **unit** tests. No IO; the service gets
  `MagicMock`s for the repo protocols (and for data when only one field
  matters); assert how the mocks were called. `MagicMock` covers
  `TransactionProtocol` — it speaks the context-manager protocol.
- IO-bearing boundary layers (`links`, `gates`, adapters, templates) →
  **integration** tests against real infrastructure. Mock at the lowest level or
  not at all; assert side effects. A gate test is a full-request test via the
  framework's test client, asserting **all** fields of the response (context
  data, redirect URL, status), with strict templates that fail on unknown
  variables.

Tests live in a repo-root `tests/` split by type — `tests/unit/` (mills, plus
pure helpers from any layer; organised by convenience, not mirroring the
code) and `tests/integration/` (gates by port + subdomain, links by port +
adapter).

An uncovered line is covered by the test type that owns its layer — never raise
`links`/`gates` coverage with a mock-everything unit test of IO-bearing code
(views, commands, repositories, importers). Exception: a pure, IO-free helper
(no DB, HTTP, request/response, template render, or framework objects) may be
unit-tested wherever it lives.

## Drift red flags

- `links.py` or `gates.py` as a single file — both need the `{port}/{adapter}`
  axis from day one
- `pacts/`, `specs/`, `mills/`, or `inits/` promoted to a package before it
  earned it — one subdomain, well under ~1000 lines, no merge friction
- `pacts.py` flat while `mills/` is a package (or vice versa) — the symmetry
  rule covers promotion too
- Nested folders holding one or two small files (see **Growing rules** — folder
  needs ≥2 leaves)
- Folder created for a single file (e.g. `inits/services/billing/invoicing.py`
  with no sibling) — flatten until the bucket is justified
- Port axis inside `mills/` or `specs/` (e.g. `mills/web/...`)
- `specs` imported from `links`, `gates`, or `inits` — specs are only for mills
- `pacts/dtos.py`, `pacts/protocols.py`, or `pacts/repos/` instead of
  `pacts/{subdomain}.py`
- `pacts/core.py` — a `common/` bucket wearing a nicer name; use the
  subdomain / port / wiring axes
- `common/` or `shared/` folder in any layer
- `pacts/` sliced by entity while `mills/` sliced by context (or vice versa) —
  axes must match
- Model and repository in the same `links` file (collapses the
  internal-vs-public boundary)
- ORM model imported from outside `links/` (use the repo protocol from `pacts`
  instead)
- `links/{port}/{adapter}/__init__.py` re-exporting models, or omitting a public
  repo class (the facade is the public surface)
- Suffix-sibling links files (`repositories_billing.py`, `models_auth.py`) —
  promote to a `{kind}/` package with submodules instead
- Business rules in form validation — gates check format; meaning belongs in
  mills
- Gate reaching data without a service — create one in mills + protocol in
  pacts + leaf in `inits/services.py` before writing the view
