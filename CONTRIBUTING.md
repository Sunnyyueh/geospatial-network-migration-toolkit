# Contributing

Contributions should preserve the portable core, optional proprietary adapter
boundary, deterministic evidence, and staging-first safety model.

## Development Setup

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Change Flow

1. Open an issue or describe the behavior and safety boundary in the pull
   request.
2. Add a failing test that demonstrates the required behavior.
3. Implement the smallest coherent production change.
4. Add stable error codes and remediation for operational failures.
5. Run the complete quality gate from the README.
6. Update CLI, architecture, or operator documentation when behavior changes.

Commits should describe one meaningful change. Do not split changes solely to
inflate history, commit generated runtime outputs, or claim unsupported ArcPy
or Utility Network behavior.

## Design Rules

- Core domain and application modules cannot import ArcPy.
- Untrusted filters are parsed into the AST and never evaluated as Python.
- SQL values remain separate from SQL text.
- Filesystem paths must stay below an explicit managed root.
- A run ID cannot overwrite an existing run directory.
- Reports and manifests must be deterministic for identical inputs.
- Samples must use synthetic, public, or approved non-confidential data.
