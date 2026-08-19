"""Ready-made metric templates for tools most projects already run.

This package is tingle's own use of a format anyone can publish: a module
holding `MetricTemplate` instances at a dotted import path. A config names
one with `base = "tingle.builtins.ruff.noqa_comment"`, and nothing in tingle
imports these modules -- they are reached by path, exactly as a third-party
pack is, so the catalogue is the format's first customer rather than a case
beside it.

One module per tool, and no module imports another: a pack stands alone,
because the config naming one is not asking for the rest.

Templates never state a range. Range names belong to the project that
defines them, so the entry using a template says where it applies. Of what
a template does carry, `group`, `description` and its params are the
entry's to override, and a list param can be extended rather than replaced
with `extra_`. `type` is not: a template that states one owns it, because
its params were written for that type.
"""
