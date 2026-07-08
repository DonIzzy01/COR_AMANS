# Handoff: COR AMANS — "Sacred" Redesign (Direction 1a)

## Overview
This package is a **redesign of the COR AMANS marriage-formation web app** in a new visual direction called **"Sacred" (1a)**: a dark forest-green canvas, gold liturgical accents, an 8-petal floral emblem, and an editorial serif/serif-italic type system. It covers the public **landing page** plus the core couple-facing pages: **Sign In, Dashboard, Live Sessions, and Resources Library**.

The goal is to replace the current light "white-and-green floral" theme on these pages with the Sacred theme, keeping all existing functionality and content intact.

## About the Design Files
The `.html` files in this bundle are **design references created in HTML** — static prototypes that show the intended look, layout, and content. **They are not production code to copy directly.**

The COR AMANS app is a **Flask (Python) server-rendered application** using **Jinja2 templates** and plain CSS (`static/css/style.css`, `static/css/admin_minimal.css`). The task is to **recreate these designs inside that existing codebase** — updating the Jinja templates and CSS to match the Sacred theme, reusing the app's existing routes, template inheritance (`layout.html`), context variables, and form fields. Do **not** introduce a new framework or a client-side SPA; stay within the current Flask + Jinja + CSS stack.

Where the prototype shows sample data (couple names, dates, module titles), the real templates already have the corresponding Jinja variables — wire the new markup to those existing variables rather than hard-coding.

## Fidelity
**High-fidelity (hifi).** Colors, typography, spacing, radii, and shadows below are final and exact. Recreate the UI to match, using the codebase's existing template structure. Keep all current behavior (auth, session join links, resource filtering, progress calculations) — this is a re-skin, not a rebuild of logic.

---

## Design Tokens

### Colors
| Token | Hex | Use |
|---|---|---|
| `--forest-950` | `#091810` | Sidebars, footers, deepest surfaces |
| `--forest-900` | `#0E241A` | Primary page background (dark canvas) |
| `--forest-800` | `#12301f` | Gradient partner, raised panels |
| `--forest-700` | `#1B4332` | Brand green, banners, button bg (light contexts) |
| `--forest-600` | `#2D6A4F` | Gradient mid |
| `--forest-500` | `#40916C` | Gradient end, secondary icons |
| `--sage-300` | `#95D5B2` | Mint accents, muted labels on dark, icons |
| `--gold-500` | `#C9A84C` | Primary gold accent, emblem center |
| `--gold-300` | `#F0D080` | Bright gold — headings-on-dark accents, gradient top |
| `--cream-100` | `#F5F1E6` | Warm light band (landing "journey" section) |
| `--ink` | `#1C2B2E` | Text on light |
| `--paper` | `#F3F7F4` | Primary text on dark |

Gold button gradient: `linear-gradient(90deg, #C9A84C, #F0D080)`, text color `#2a2005`.
Green banner gradient: `linear-gradient(120deg, #12301f, #1B4332 55–60%, #2D6A4F)`.
Text-on-dark opacities: primary `#fff`/`#F3F7F4`; secondary `rgba(243,247,244,.65–.72)`; muted `rgba(243,247,244,.5)`.

### Typography
- **Display / headings:** `'Playfair Display', serif` — weights 500/600/700; italics used for emphasis words (e.g. *"holy marriage"*).
- **Body UI:** `'Inter', system-ui, sans-serif` — 400/500/600/700.
- **Quotes / verse / descriptive:** `'Lora', Georgia, serif`, often italic.
- Google Fonts: `Playfair+Display:ital,wght@0,500;0,600;0,700;1,500;1,600` · `Inter:wght@400;500;600;700` · `Lora:ital,wght@0,400;0,500;1,400;1,500`.
- Icons: Font Awesome 6.4.0.
- Uppercase micro-labels: 10–12px, weight 700, `letter-spacing:.12–.22em`, color `#95D5B2` or `#F0D080`.

### Radius & Shadow
- Cards/panels: `radius 18–24px`. Pills/buttons: `9999px`. Inputs: `12px`.
- Card border on dark: `1px solid rgba(201,168,76,.18–.35)` (gold, gets brighter for highlighted cards) or `rgba(255,255,255,.08)` (neutral).
- Elevation: `0 30px 80px rgba(14,36,26,.28)` for page-level; softer for cards.

### The brand mark (combined logo)
The logo is the **COR AMANS Sacred Heart emblem** (flaming heart, cross, wedding rings, crown of thorns, doves, lily & wheat) set inside a **gold-ringed white disc**, centred within an **8-petal sage flower**. This composite is provided as `assets/brand-mark.png` (640×640, transparent background) and is used wherever the logo appears — nav, sidebars, login panel, hero watermark, and CTA. Reproduce it as a single asset (or rebuild as SVG) — do NOT fall back to the plain flower-only mark. Source heart artwork: `static/images/COR AMANS.jpg`.

### The floral emblem (fallback / decorative)
8 ellipses at 45° increments + a center circle. Petals `#95D5B2` (or `#F3F7F4` at low opacity for watermarks), center `#C9A84C`. Reusable snippet (scale via width/height):
```html
<svg viewBox="-60 -60 120 120" width="40" height="40"><g fill="#95D5B2">
  <ellipse cx="0" cy="-38" rx="13" ry="30"/>
  <!-- repeat with transform="rotate(45|90|135|180|225|270|315)" -->
</g><circle r="14" fill="#C9A84C"/></svg>
```

---

## Screens / Views

### 1. Landing Page (`templates/landing.html`)
- **Nav (h≈78px):** transparent over `#0E241A`, bottom border `rgba(255,255,255,.08)`. Left: emblem + "COR AMANS" / "Loving Heart" (uppercase sage). Right: text links (Formation, Sessions, Resources, About), a gold-outline "Sign In" pill, a gold-gradient "Register" pill.
- **Hero:** two columns (1.05fr / 0.95fr). Left: gold-outline eyebrow pill "✝ Sacrament of Matrimony"; `h1` 66px Playfair with italic gold "*holy marriage*"; Lora sub-paragraph; two CTAs (gold-gradient "Begin Your Journey", ghost "Watch Overview"). Right: couple photo (`aspect-ratio 4/4.4`, radius 26px, gold hairline border) with a bottom gradient scrim and an overlaid Matthew 19:6 verse. Faint floral watermark top-right at 5% opacity.
- **Stat strip:** 4 columns, Playfair 38px `#F0D080` numbers (6 / Live / 100% / 148) with muted labels, separated from hero by a top hairline.
- **Journey (on cream `#F5F1E6`):** centered heading; 4 columns with 70px dark circular icon badges (`#0E241A`, icon `#F0D080`; last one inverts to `#C9A84C` bg) and chevron separators. Steps: Register, Enroll, Form, Receive.
- **CCC doctrine (dark):** centered heading; 4 cards, each with FA icon `#F0D080`, Playfair title, muted body, italic Lora citation (`CCC 1601`, `1638`, `1643`, `1655`).
- **CTA:** centered emblem, Playfair 44px heading, Lora italic Hebrews 13:4 verse, gold-gradient "Register as a Couple" pill; background `linear-gradient(180deg,#0E241A,#12301f)`.
- **Footer:** `#091810`, wordmark + copyright left, link row right.

### 2. Couple Sign In (`templates/login.html`)
- Split 46% / 54%. **Left:** full-bleed couple photo under a `160deg` forest scrim; emblem + wordmark top, Matthew 19:6 verse bottom (Playfair italic + gold caption). **Right (`#0E241A`):** Playfair "Welcome back" + Lora subtitle; a sage flash box (registration-complete message); two fields — **Registration Number** and **Password** (label `#F0D080`, field = `rgba(255,255,255,.04)` bg, `1px solid rgba(201,168,76,.3)`, radius 12px, white text; password shows eye-slash icon); gold-gradient full-width "Sign In" pill; footer link to register.
- **Keep** the existing form action, field names, CSRF token, and flash-message loop from the current `login.html`.

### 3. Couple Dashboard (`templates/dashboard.html`)
- **Sidebar (264px, `#091810`):** emblem+wordmark; a gold-tinted couple chip (avatar = gold-gradient circle with heart, name + reg number); nav groups "Formation" (Dashboard active = `rgba(201,168,76,.12)` bg / `#F0D080` text; Live Sessions, Resources, Modules) and "Account" (Profile, Password); Sign Out in muted red at the bottom.
- **Main (`#0E241A`, padding 34px):**
  - **Welcome banner:** green gradient, gold hairline border, floral watermark; "Welcome back" eyebrow (`#F0D080`), Playfair 36px couple name, Lora italic reg-number + wedding date.
  - **Two cards:** (a) **Progress** — 88px SVG ring, track `rgba(255,255,255,.1)`, arc `#C9A84C`, center "62%" in `#F0D080`; label + two gold chips. (b) **Milestones** — three rows with gold check circles (done) / gold-outline dot (in progress).
  - **Upcoming Sessions:** 3 cards. The live one uses the gold-tinted highlight card (`linear-gradient(135deg,rgba(201,168,76,.16),rgba(201,168,76,.05))`, border `rgba(201,168,76,.35)`) with a red "LIVE NOW" pill and a gold-gradient "Join Session" button; the others are neutral cards with sage "Upcoming" pills.
  - **Formation Modules:** rows with a status circle (gold check = complete, gold-outline number = in progress), title, gold-gradient progress bar on a `rgba(255,255,255,.1)` track, percentage in `#F0D080`.
- Wire ring %, module list, and session list to the existing dashboard context variables.

### 4. Live Sessions (`templates/sessions.html`)
- Green gradient page header with FA video icon + Lora subtitle.
- **"Upcoming & Live"** section (dot bullet `#C9A84C`): 2-column cards; live = gold-highlight card with red LIVE pill + gold-gradient Join button; upcoming = neutral card with a lock note "Room opens 15 minutes before start."
- **"Recordings"** section (dot bullet `#95D5B2`): stacked rows, each with an icon tile, title, meta line, and a gold-outline "Watch" pill (or muted "Completed").

### 5. Resources Library (`templates/resources.html`)
- Green gradient header with FA folder icon.
- **Filter pills:** active = gold gradient; others = `rgba(255,255,255,.05)` with `rgba(255,255,255,.1)` border. (All, Videos, Documents, Doctrine, Liturgy, Prayer.)
- **3-column card grid.** Video cards: 16/9 thumb = `linear-gradient(135deg,#12301f,#2D6A4F|#40916C)` with a gold duration pill + large gold play icon. PDF cards: 120px gradient header with a gold `file-pdf` icon + a file-size meta line. Each card: sage uppercase category, white Playfair title (featured items get a gold star), muted description.

---

## Interactions & Behavior
- **Hover:** nav/links lighten (`#C9A84C → #F0D080`); buttons lift (translateY(-1px)) with a slightly stronger shadow; cards raise elevation subtly. Match the current app's existing hover conventions where they exist.
- **Nav / flows (unchanged):** Register → registration wizard; Sign In → dashboard; sidebar items → their routes; "Join Session" → the session's `join_url`; resource cards → open/download.
- **Filtering (Resources):** keep the current client-side/server-side category filter; only the pill styling changes.
- **Progress ring / bars:** compute `stroke-dasharray`/width from the same percentage the app already calculates (`arc = pct/100 * circumference`, circumference = `2πr`).
- **Forms:** preserve existing validation, field names, CSRF, and flash messages.
- **Responsive:** below ~900px, dashboard sidebar collapses to a top bar / drawer; multi-column grids drop to 1–2 columns; hero stacks to a single column (photo below copy). Landing was designed at 1280px; member pages at 1200–1320px.

## State Management
No new client state beyond what exists. This is server-rendered — data comes from existing Flask route context (couple, modules, sessions, resources, progress). Preserve all of it.

## Assets
- **Brand mark:** `assets/brand-mark.png` (in this bundle) — the Sacred Heart emblem inside a gold-ringed disc at the centre of the sage flower. This is THE logo; use it everywhere the mark appears. Built from the parish's `static/images/COR AMANS.jpg`.
- **Couple photo:** `static/images/couple_1.jpg` (existing) — used in the landing hero and the login left panel.
- **Fonts:** Google Fonts (Playfair Display, Inter, Lora). **Icons:** Font Awesome 6.4.0 CDN (already used by the app).

## Files (design references in this bundle)
- `Landing Redesign (1a).html` — the chosen landing direction (also contains 1b for comparison; build **1a**).
- `Pages Redesign (1a).html` — Dashboard (2a), Sign In (2b), Sessions (2c), Resources (2d) in the Sacred theme.
- `Admin Redesign.html` — the admin **Dashboard** "Formation Command Center."
- `Admin Pages (Couples, Payments, Sessions, Resources).html` — the four admin sub-pages (3a–3d) in the same command-center style, each with a **"View Site"** link back to the public site.
- `Registration & Admin Login (1a).html` — the 7-step registration wizard (4a, with a vertical stepper) and the admin sign-in (4b, Command Center branding) in the Sacred theme.
- `assets/brand-mark.png` — the combined logo (Sacred Heart in a gold-ringed disc at the flower's center).
- Open these in a browser to see the exact intended result.

### Registration wizard (`register.html`) & Admin login (`admin/admin_login.html`)
- **Register (4a):** dark forest left rail with the brand mark, "Begin Your Sacred Journey" heading, a **vertical 7-step stepper** (active step = gold-gradient circle; pending = sage outline), and a 1 Corinthians 13 verse footer. Right side (`#0E241A`): step header with gold heart tile, grouped fields (Identity / Contact) with `#F0D080` labels and `rgba(255,255,255,.04)` inputs, and a gold-gradient "Continue" pill. Keep all 7 real steps, every field name, validation, and the existing wizard navigation.
- **Admin login (4b):** split panel — left forest-gradient brand side ("Formation Command Center", "Restricted Access" pill, "access is logged" note); right `#0E241A` form with a shield tile, error flash (attempts remaining), email + password fields (gold labels, icon-prefixed), and a gold-gradient "Sign in to Console" button. Preserve the existing admin auth form, field names, CSRF, and lockout logic.

## Admin console (Command Center) — design spec
The admin area gets its own bespoke look, distinct from the couple app but sharing the Sacred palette + logo. **Do redesign the admin templates** (this supersedes the earlier "keep admin as-is" note).

- **Shell:** fixed 252px **deep-forest sidebar** (`#0C2016`) with a gold hairline right edge; brand-mark + "COR AMANS / Admin Console" header; nav grouped **Overview / Management / System**; active item = gold-tinted pill (`linear-gradient(90deg,rgba(201,168,76,.18),rgba(201,168,76,.02))`, text `#F0D080`) with a 3px gold left bar; count badges on Couples (148) and Payments (36); an admin-profile footer (gold-gradient avatar, name, role, sign-out).
- **Canvas:** warm **parchment** (`#F4F1E8`), NOT gray. Sticky 72px top bar (translucent parchment) with a Playfair page title + context subline on the left, and on the right: search field, **"View Site"** button (outlined gold, `#FBF6E9` bg), and a primary green action button.
- **Cards:** white, `1px solid #EBE5D5`, radius 18–20px, soft shadow `0 1px 3px rgba(27,67,50,.05)`. KPI cards carry a 3px gradient top-accent hairline; the marquee metric (Revenue) is a **forest-gradient card** with a gold watermark icon.
- **Tables:** header row `#FAF8F1`, uppercase 11px muted labels; rows separated by `#F4F0E6`; avatar-initial chips; status pills — green `#E3F5E9/#2F855A` (Enrolled/Paid/Published), gold `#FBF0DA/#B8871F` (Awaiting/Pending/Hidden), stone `#EDE7D8/#1B4332` (Completed), red `#fde8e8/#b91c1c` (Live). Row actions are muted FA icons (view/edit/more). Include a footer pager.
- **Charts:** built with divs/SVG in brand colors — grouped bars (forest `#1B4332` + gold `#C9A84C`, current period highlighted) and a gold **completion gauge** ring.
- **Dashboard (Command Center) layout:** KPI bento row → charts row (Enrollment&Revenue bars + Formation-Health gauge) → bottom row (Recent Registrations table + right rail: live-session monitor card, quick-actions grid, activity feed).
- **Sub-pages:** **Couples** (filter tabs, searchable table with progress bars + status + pager), **Payments** (3 summary cards incl. forest revenue card + transactions table), **Live Sessions** (4 stat tiles + sessions table with Live/Upcoming/Completed + recording status), **Resources** (4 stat tiles + resources table with type/category/status + publish-toggle/edit/delete actions).

## "View Site" / access the public website
Admins must be able to jump to the live public site from the console:
- Put a **"View Site"** entry at the bottom of the sidebar nav (dashed outline, sage text, external-link icon) **and** a "View Site" button in the top bar.
- Both link to the public landing route (Flask `url_for('landing')` / `/`), opening in a **new tab** (`target="_blank" rel="noopener"`). This is navigation only — no new backend.

## Implementation notes for Claude Code
1. Add the Sacred tokens as CSS variables in `static/css/style.css` (or a new `sacred.css` included via `layout.html`), then restyle `landing.html`, `login.html`, `register.html` (7-step wizard, see 4a), `dashboard.html`, `sessions.html`, `resources.html`.
2. **Admin:** restyle `admin/admin_login.html` (Sacred split-panel, see 4b); create/replace an `admin/admin_layout.html` implementing the Command Center shell (sidebar + parchment canvas + top bar with View Site), then restyle `admin_dashboard.html`, `admin_couples.html` (or equivalent), `admin_payments.html`, `admin_sessions.html`, `admin_resources.html` to match 3a–3d. A dedicated `admin.css` is fine; keep it separate from the couple styles.
3. Replace the raster logo with the `brand-mark.png` asset (or an SVG rebuild) everywhere the mark appears.
4. Wire **View Site** links to `url_for('landing')` with `target="_blank"`.
5. Verify every Jinja variable/loop in the current templates is preserved in the new markup before deleting the old markup — the sample data shown (couples, ₦ amounts, sessions, resources) maps to existing route context.
6. Test the full flow: register → login → couple dashboard → join session → resources; and admin login → dashboard → couples → payments → sessions → resources → View Site.
