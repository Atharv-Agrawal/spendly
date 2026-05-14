# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Spendly** — a Flask-based personal expense tracker. Landing page and auth flows are complete; the expense management features are in progress.

## Commands

```bash
# Install dependencies (activate venv first)
pip install -r requirements.txt

# Run dev server (http://localhost:5001, debug mode on)
python app.py

# Run tests
pytest
```

## Architecture

**Stack:** Python/Flask backend, Jinja2 templates, vanilla JS/CSS frontend, SQLite database. No build step — all assets are served as static files.

**Entry point:** `app.py` — all Flask routes are defined here with decorators. Current routes cover landing, login/register, legal pages, and stub placeholders for logout, profile, and expense CRUD.

**Templates** use inheritance from `templates/base.html`, which provides the navbar, footer, and shared CSS/font loading. Page-specific templates extend `base.html` and fill `{% block content %}`.

**Database** module lives in `database/db.py` (SQLite). The module is partially stubbed — the connection and schema helpers exist but CRUD operations are not fully implemented.

**Static assets** are in `static/css/style.css` (design tokens via CSS variables, DM Serif Display + DM Sans fonts) and `static/js/main.js`. No JS bundler or preprocessor is used.

## Key conventions

- Flask `debug=True` and port `5001` are hardcoded in `app.py` — keep this for local dev.
- CSS uses CSS custom properties (`--color-*`, `--font-*`) defined at `:root` — add new design tokens there rather than inline values.
- Template partials for reusable UI snippets go in `templates/` with a descriptive name; include them via Jinja2 `{% include %}`.
