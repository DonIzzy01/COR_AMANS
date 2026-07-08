# Claude Code — Build Prompt

Copy everything in the box below and paste it into Claude Code, from the root of your COR_AMANS project (with this `design_handoff_sacred_redesign/` folder placed inside it).

---

```
You are implementing a visual redesign of my existing COR AMANS app — a Flask (Python) + Jinja2 + plain-CSS web app for Catholic marriage formation. This is a RE-SKIN, not a rewrite: keep every route, form, field name, CSRF token, context variable, and behavior exactly as it is. Only change templates and CSS.

SOURCE OF TRUTH
Read `design_handoff_sacred_redesign/README.md` first and follow it precisely — it has the exact color tokens, type system, per-screen layouts, the admin "Command Center" spec, and the "View Site" requirement. Open the `.html` files in that folder in a browser to see the intended result pixel-for-pixel:
- `Landing Redesign (1a).html`  → public landing page (build the 1a "Sacred" version)
- `Pages Redesign (1a).html`    → couple Dashboard, Sign In, Sessions, Resources
- `Admin Redesign.html`         → admin Dashboard (Command Center)
- `Admin Pages (Couples, Payments, Sessions, Resources).html` → the four admin sub-pages
- `assets/brand-mark.png`       → the logo (use everywhere the mark appears)

DESIGN LANGUAGE (summary — README is authoritative)
- Theme "Sacred": deep forest greens (#0E241A/#1B4332/#2D6A4F/#40916C), gold accents (#C9A84C/#F0D080), sage #95D5B2, warm parchment #F4F1E8 for admin, cream #F5F1E6 accents.
- Type: Playfair Display (headings), Inter (UI), Lora italic (quotes/verse). Font Awesome 6.4 for icons.
- The logo is the Sacred Heart emblem inside a gold-ringed disc centered in an 8-petal flower (brand-mark.png).

WHAT TO BUILD
1. Add Sacred design tokens as CSS variables (new `static/css/sacred.css`, included via `layout.html`).
2. Couple-facing: restyle `landing.html`, `login.html`, `dashboard.html`, `sessions.html`, `resources.html` to match the references.
3. Admin: create an `admin/admin_layout.html` implementing the Command Center shell — 252px deep-forest sidebar (grouped nav, count badges, admin profile footer), warm parchment canvas, sticky top bar. Then restyle the admin dashboard and the Couples, Payments, Sessions, and Resources pages to match 3a–3d. Put admin styles in a separate `static/css/admin.css`.
4. "View Site": add a "View Site" link in BOTH the admin sidebar (bottom) and the admin top bar, linking to `url_for('landing')` (the public site) with `target="_blank" rel="noopener"`. Navigation only — no new backend.
5. Replace the old raster logo with `brand-mark.png` everywhere.

RULES
- Do not add new dependencies, JS frameworks, or a build step. Stay in Flask + Jinja + CSS.
- Preserve all existing Jinja `{{ variables }}`, `{% for %}` loops, `{% if %}` guards, form actions, and CSRF tokens. The sample data in the references (couple names, ₦ amounts, sessions, resources, progress %) maps to my existing route context — wire the new markup to those variables, don't hard-code.
- Keep it responsive: sidebar collapses to a drawer under ~900px; multi-column grids drop to 1–2 columns; hero stacks.
- Work incrementally: do the landing page first, show me, then proceed page by page. After each page, tell me which template(s) and CSS you changed.

VERIFY
Run the app and walk both flows:
- Couple: register → login → dashboard → join session → resources
- Admin: login → dashboard → couples → payments → sessions → resources → click "View Site"
Confirm nothing in the existing logic broke.
```

---

## Tips
- Place the `design_handoff_sacred_redesign/` folder **inside** your project so Claude Code can read it with relative paths.
- If Claude Code asks about ambiguous data bindings, point it at the current template it's replacing — the variable names are already there.
- Ask it to go **one page at a time** so you can review before it moves on.
- If your admin templates have different filenames than assumed, tell Claude Code the real names — the spec maps by role, not exact filename.
