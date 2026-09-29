# fusion-export

A Fusion (macOS) add-in. Fusion's cloud is not the source of truth for a design, so on every document save this add-in exports the design's .f3d into the project's git repo at `cad/<part>.f3d`. It never commits or pushes.

## Development

```
uv sync
uv run pytest
```
