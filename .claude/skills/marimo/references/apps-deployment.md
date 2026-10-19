# Apps, Scripts & Deployment

## Run as App

Transform any notebook into an interactive web app:

```bash
marimo run notebook.py
```

- Code is hidden
- Outputs are displayed
- UI elements remain interactive
- Reactive execution still works

### Options

```bash
# Custom host/port
marimo run notebook.py --host 0.0.0.0 --port 8080

# Include code in app view
marimo run notebook.py --include-code

# Watch for file changes
marimo run notebook.py --watch

# Require a token (marimo run serves without one by default)
marimo run notebook.py --token
```

### `marimo run` Is Not an Execution Test

`marimo run` checks the notebook before serving it (`--check`, the default; `--no-check` turns it off) and exits 1 with "The notebook has errors, fix them before running." when the check finds a breaking issue such as MB002 multiple-definitions. A notebook that passes the check is then served until the process is stopped. Headless, nothing reports cell errors in the terminal: on 0.25.0, `timeout 20 marimo run <notebook> --headless` on a notebook whose cell raises at runtime exited 124 (killed by `timeout`) without reporting the error. To check that every cell executes, use `marimo export html` (see Export > HTML below), which runs every cell and exits non-zero when any cell fails.

## App Layouts

### Vertical (Default)

Cell outputs stacked vertically, code hidden.

### Grid Layout

Drag-and-drop positioning:

1. In editor, click preview button (bottom-right)
2. Select "Grid" from layout dropdown
3. Drag outputs to arrange

Grid metadata saved in `layouts/` folder - include in version control.

### Slides Layout

Presentation mode:

1. In editor preview, select "Slides"
2. Each cell becomes a slide
3. Navigate with arrow keys

## Run as Script

marimo notebooks are valid Python:

```bash
python notebook.py
```

### CLI Arguments

Access command-line args:

```python
# In notebook
args = mo.cli_args()
input_file = args.get("input", "default.csv")

# Usage
python notebook.py -- --input data.csv --output results.json
```

`mo.cli_args()` turns `--key value` and `--key=value` pairs into a read-only mapping and converts numbers and `true`/`false`; a repeated key becomes a list, and `.get(key, default)` returns the default for a missing key. It does not declare arguments or generate help text, so marimo's documentation recommends `argparse` or `simple-parsing` for anything beyond a few flags. When the notebook runs as `python notebook.py`, the arguments are in `sys.argv` as in any script. Under `marimo edit`, `marimo run`, or `marimo export ...`, pass them after a `--` separator (for example `marimo export html notebook.py -o out.html -- --input data.csv`); `sys.argv` then holds the notebook filename followed by those arguments.

### Query Parameters (Web)

When running as app:

```python
params = mo.query_params()
# params["key"] from URL ?key=value
```

Set params:

```python
mo.query_params().set({"page": 2})  # call the accessor first; .set lives on the returned QueryParams object
```

## Export

### HTML (Static)

```bash
marimo export html notebook.py -o output.html

# Code is included by default; leave it out with --no-include-code
marimo export html notebook.py -o output.html --no-include-code

# Watch mode
marimo export html notebook.py -o output.html --watch
```

**It runs the notebook.** `marimo export html` executes every cell and embeds the outputs. If any cell fails, it still writes the HTML but exits 1 with `Error: Export was successful, but some cells failed to execute.` and prints each error (for example `MultipleDefinitionError: ...` or `MarimoExceptionRaisedError: ...`). That makes it the self-terminating way to check that a notebook executes. Without `-o` the HTML goes to stdout; `-f` overwrites an existing output file.

**It writes a session snapshot beside the notebook.** Every HTML export also saves the executed session to `__marimo__/session/<notebook>.py.json` in the notebook's own directory (marimo 0.25.0: `persist_session` defaults to `True` in `marimo/_export/requests.py`, applied in `marimo/_export/file.py`). There is no CLI flag to turn it off; the only relocation hook is Python's `sys.pycache_prefix`. A snapshot of a large notebook can be several megabytes (7.4 MB for one DAAF Stage 9 notebook). Expect this directory after any export and keep it out of commits; DAAF's `.gitignore` covers `__marimo__/`.

### HTML-WASM (Interactive, Browser-Only)

Runs entirely in browser via WebAssembly:

```bash
marimo export html-wasm notebook.py -o output_dir/

# Edit mode (code editable)
marimo export html-wasm notebook.py -o output_dir/ --mode edit

# Run mode (read-only)
marimo export html-wasm notebook.py -o output_dir/ --mode run
```

Must be served over HTTP (not `file://`).

### Session Snapshot

```bash
# Run the notebook and write __marimo__/session/notebook.py.json next to it
marimo export session notebook.py

# Re-run even when the existing snapshot is up to date
marimo export session notebook.py --force-overwrite
```

`marimo export session` (new since 0.19.11) executes a notebook, or every notebook in a directory, and writes the same JSON snapshot that `export html` leaves behind. It skips a notebook whose snapshot is up to date ("skip: notebook.py (up-to-date, use --force-overwrite ...)"). When a cell fails it still writes the snapshot, then exits 1 with "Session export succeeded, but some cells failed to execute." With a directory it continues past a failing notebook by default (`--no-continue-on-error` stops at the first). It also accepts `--sandbox [uv|pixi]`, which does not belong in the DAAF container (see Docker with Sandbox below).

### Jupyter Notebook

```bash
marimo export ipynb notebook.py -o output.ipynb

# Include outputs
marimo export ipynb notebook.py -o output.ipynb --include-outputs
```

Cells are written in topological order by default (`--sort top-down` keeps file order). Both commands need the `nbformat` package, which the DAAF image does not include: on 0.25.0 the export exits 1 with "nbformat is required to convert marimo notebooks to ipynb" followed by a tip to `pip install nbformat`. Do not follow that tip, which is a runtime install; adding the package is a Dockerfile change and a rebuild. `marimo export pdf` needs `nbformat` and `nbconvert`, so it is unavailable in the image for the same reason.

### Flat Python Script

```bash
marimo export script notebook.py -o flat_script.py
```

Cells merged in topological order.

### Markdown

```bash
marimo export md notebook.py -o output.md
```

## Deployment Options

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY notebook.py .

EXPOSE 8080
CMD ["marimo", "run", "notebook.py", "--host", "0.0.0.0", "--port", "8080", "--headless"]
```

```bash
docker build -t my-marimo-app .
docker run -p 8080:8080 my-marimo-app
```

### Docker with Sandbox

```dockerfile
FROM ghcr.io/marimo-team/marimo:latest

COPY notebook.py /app/
WORKDIR /app

CMD ["marimo", "run", "notebook.py", "--sandbox", "--host", "0.0.0.0"]
```

> **Not inside DAAF:** `--sandbox` runs the notebook in a separate environment built by installing the notebook's PEP 723 inline dependencies from a package index. In 0.25.0, `marimo edit`, `marimo run`, and `marimo export session` take `--sandbox [uv|pixi]` (uv by default), while `marimo export html`, `ipynb`, and `pdf` take a plain `--sandbox` that uses `uv run --isolated`. It leaves the image untouched, but that environment is not the one the Dockerfile defines, so results produced in it cannot be reproduced from the DAAF image. On `marimo edit` and `marimo run` it also rewrites the notebook file, adding a PEP 723 block when there is none (see `quickstart.md` > Package Management). Inside the DAAF container, run notebooks against the image's pinned packages and add a package through the Dockerfile and a rebuild.

### HuggingFace Spaces

1. Create new Space with Docker SDK
2. Add `Dockerfile`:

```dockerfile
FROM ghcr.io/marimo-team/marimo:latest
COPY --chown=user notebook.py /app/
CMD ["marimo", "run", "/app/notebook.py", "--host", "0.0.0.0", "--port", "7860"]
```

### Behind a Proxy Without WebSockets

marimo streams kernel messages to the browser over a WebSocket (`/ws`). For a proxy or hosting service that does not support WebSockets, 0.25.0 has an experimental alternative: set `MARIMO_SERVER_TRANSPORT=sse` (the `server.transport` config key) to use server-sent events over HTTP. The terminal, the language server, and real-time collaboration still need WebSockets, and real-time collaboration is turned off under `sse` (`marimo/_config/config.py`).

### Railway / Render / Fly.io

Similar Docker-based deployment. Set:
- Build: `docker`
- Port: match your `--port` flag

### Cloudflare Pages (WASM)

```bash
marimo export html-wasm notebook.py -o dist/ --include-cloudflare
# Deploy dist/ to Cloudflare Pages
```

### GitHub Pages (WASM)

```bash
marimo export html-wasm notebook.py -o docs/
# Enable GitHub Pages from docs/ folder
```

## Authentication

### Token Auth

The defaults differ by command. `marimo edit` (and `marimo new` / `marimo tutorial`) requires a token by default; `marimo run` does not, so an app served with `marimo run` is open to anyone who can reach the port unless you ask for a token.

```bash
# marimo run: opt in to a generated token (derived from the notebook's code),
# printed in the console URL
marimo run notebook.py --token

# Custom token
marimo run notebook.py --token-password mysecret

# marimo edit: disable the default token (trusted local setups only)
marimo edit notebook.py --no-token
```

DAAF's notebook browser (`scripts/launch_marimo.sh`) runs `marimo edit --no-token`; what keeps it private is that `docker-compose.yml` publishes the port on the host's `127.0.0.1` only.

### Custom Auth

Use ASGI middleware for OAuth, SSO, etc.

## Programmatic Execution

### Run from Python

A notebook file defines a module-level `app` object. Import it and call `app.run()`, which returns the cell outputs and a mapping of the notebook's definitions. `marimo.App` takes only keyword configuration (such as `width="medium"`), not a file path, so `App("notebook.py")` raises a `TypeError`.

```python
# my_notebook.py must be importable: next to the calling script, or on sys.path
from my_notebook import app

outputs, defs = app.run()

# Supply values in place of running the cell that defines them
# (give every name that cell defines)
outputs, defs = app.run(defs={"batch_size": 64, "learning_rate": 0.001})
```

To serve a notebook file from another web app, use `create_asgi_app()` (next section).

### Embed in Other Apps

```python
# FastAPI example
from fastapi import FastAPI
from marimo import create_asgi_app

app = FastAPI()
marimo_app = create_asgi_app().with_app(path="", root="notebook.py").build()
app.mount("/marimo", marimo_app)
```

## Sharing

### molab (Cloud)

Free cloud notebooks at https://molab.marimo.io:

1. Create notebook on molab
2. Share link directly

### GitHub

GitHub shows a marimo notebook as a plain Python file: unlike a Jupyter notebook, its outputs cannot be previewed on GitHub. To share a preview, replace `github.com` in the notebook's GitHub URL with `molab.marimo.io/github`, or commit an `ipynb` export with outputs (`marimo export ipynb ... --include-outputs`, see Export above). That export needs `nbformat`, which the DAAF image does not include (adding it is a Dockerfile change and a rebuild).

### Embedding

Embed WASM notebooks in other sites:

```html
<iframe src="https://your-wasm-export.com" width="100%" height="600"></iframe>
```

## Best Practices

1. **Check before deploying:** `marimo check notebook.py` for structure, then `marimo export html notebook.py -o check.html -f` to confirm every cell executes (a served `marimo run` does not report cell errors; see Run as App)
2. **Pin dependencies** in requirements.txt or inline
3. **Use `--sandbox`** for reproducible environments outside DAAF only: inside the container it builds an environment the Dockerfile does not define (see the note under Docker with Sandbox)
4. **Include layouts/** folder in version control
5. **Set appropriate auth** for public deployments
6. **Use WASM export** for static hosting (no server needed)

## Summary

| Goal | Command |
|------|---------|
| Interactive app | `marimo run notebook.py` |
| Execute as script | `python notebook.py` |
| Lint without running | `marimo check notebook.py` |
| Static HTML (runs every cell) | `marimo export html ...` |
| Session snapshot (JSON) | `marimo export session ...` |
| Browser-only (WASM) | `marimo export html-wasm ...` |
| Convert to Jupyter | `marimo export ipynb ...` (needs `nbformat`, not in the DAAF image) |
| Docker deploy | Use official image |
| Serverless | WASM + static hosting |
