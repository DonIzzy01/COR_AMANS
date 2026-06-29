# COR AMANS — Design Specification
## For Claude Design / Figma / Any Design Tool

---

## 1. Brand Identity

**Name:** Cor Amans ("Loving Heart" — Latin)
**Domain:** Catholic marriage preparation for Nigerian parishes
**Tone:** Sacred, warm, trustworthy, professional — not cold or clinical
**Typography:**
- Headings: Playfair Display (serif) — conveys tradition and dignity
- Body/UI: Inter (sans-serif) — clean, readable, modern

**Colour System (exact hex values):**
| Token | Hex | Use |
|---|---|---|
| Forest | `#1B4332` | Primary actions, headings, sidebar |
| Green | `#2D6A4F` | Hover states, secondary buttons |
| Sage | `#40916C` | Accents, links, active states |
| Foam | `#DCFCE7` | Backgrounds, success tints |
| Gold | `#C9A84C` | Highlights, decorative accents |
| Frost | `#F0FAF5` | Page backgrounds |
| Charcoal | `#1C2B25` | Body text |
| Slate | `#4A6741` | Secondary text |
| Muted | `#7A8F7A` | Placeholders, hints |
| White | `#FFFFFF` | Cards, inputs |
| Error | `#CF222E` | Errors, destructive actions |
| Border | `#D1E8DA` | Subtle borders |

---

## 2. Design Principles Applied

1. **Jakob's Law** — All layouts use familiar patterns: top navigation, sidebar admin panel, card-based content, standard form placement. Users feel at home immediately.
2. **Fitts's Law** — Primary actions (Sign In, Register, Submit) are large, full-width buttons on mobile and right-aligned on desktop.
3. **Hick's Law** — Registration is split into 7 steps (not one overwhelming form). Each step has 4–6 fields only.
4. **Visual Hierarchy** — Page titles > section headings > body > captions. Three weights used: 700 (headings), 600 (labels/nav), 400 (body).
5. **Feedback loops** — Flash messages for every user action. Lockout countdown shown. Progress bars on formation modules.

---

## 3. Page-by-Page UI Specification

### 3.1 Landing Page (`/`)

**Layout:** Full-screen hero → features grid → testimonials → CTA
**Hero:**
- Full-viewport green gradient background (#1B4332 → #2D6A4F)
- Centred logo (circular, 120px) with gold ring border
- H1: "Cor Amans" in Playfair Display 64px white
- Subtitle: "Catholic Marriage Formation" in Inter 20px, opacity 0.85
- Two CTAs side-by-side: [Register as a Couple] (gold fill) [Sign In] (white outline)
- Decorative: floral SVG petal overlay at top-left and bottom-right corners (white, 8% opacity)

**Features grid (3 columns, icon + heading + text):**
- Church icon — "Rooted in Catholic Doctrine"
- Video icon — "Live Weekly Formation Classes"
- Certificate icon — "Certificate of Completion"

**Footer:** Forest green background, logo, links, © Parish name

---

### 3.2 Registration (`/register`) — 7-Step Wizard

**Layout:** Two-column split
- LEFT (40%): Fixed brand panel — forest green, logo, step tracker (vertical stepper), motivational quote from CCC
- RIGHT (60%): Scrollable form card, white background

**Step tracker (left panel):**
- 7 circles with step numbers, connected by a vertical line
- Active step: filled forest green circle, bold label
- Completed step: checkmark icon, dimmed label
- Future step: empty circle, lighter label

**Each step card (right panel):**
- Step number + title at top ("Step 1 of 7 — Personal Information")
- Progress bar (thin, forest green, 0–100% based on step)
- Form fields with floating labels
- [Back] ghost button left + [Continue] primary button right
- On final step: [Complete Registration] gold primary button

**Steps:**
1. Bride personal info (name, DOB, nationality, state of origin, phone)
2. Groom personal info (same fields)
3. Contact & address (shared address, emails, wedding date)
4. Religious background (baptism, confirmation, previous marriage, parish)
5. Medical & health (blood group, genotype, medical history — all optional with privacy note)
6. Documents (upload certificates — optional)
7. Review & submit (summary of all entries, T&C checkbox)

---

### 3.3 Login (`/login`)

**Layout:** Two-column split (same structure as registration)
- LEFT (40%): Brand panel — forest green, logo, feature bullets, decorative florals
- RIGHT (60%): Centred login card

**Login card:**
- Logo (small, mobile only)
- "Welcome back" H2, subtitle
- Form fields:
  - Registration Number (text input, monospace, uppercase, placeholder "CA-2026-0001")
  - Hint below: "Check your confirmation email"
  - Password (input with show/hide toggle)
- [Sign In] button — full width, forest green, white text
- Footer: "Don't have an account? Register as a couple"
- Back link: "← Back to home"

**Flash messages:** Colour-coded banner above form (red=error, green=success, amber=warning)

---

### 3.4 Admin Login (`/admin/login`)

**Layout:** Single column, centred card on dark background
**Background:** `#161b22` (near-black)
**Card:** `#21262d`, border `#30363d`, 340px max-width

**Elements (top to bottom):**
- Shield icon in green-tinted rounded square (44px)
- "Admin Access" in Playfair Display 20px white
- "COR AMANS · Parish Formation System" — muted 12px
- Inline flash message row (red/green/amber)
- Email input (dark bg, green focus ring)
- Password input (dark bg, show/hide toggle)
- [→ Sign in] button — full width, GitHub-green `#238636`
- "Not an admin? Couple login →" link — muted
- "🔒 All access is logged" — very small, subtle grey

---

### 3.5 Couple Dashboard (`/dashboard`)

**Layout:** Sidebar + main content
**Sidebar (left, 260px, forest green):**
- Logo at top
- Nav links: Dashboard, Formation Modules, Resources, Live Sessions, Profile
- At bottom: couple name, sign out button

**Main content:**
- **Topbar:** "Good morning, [Name]" + notification bell
- **Progress ring** (SVG, 120px): overall % complete, forest green stroke
- **Live sessions card:** Next session date, host name, [Join] button (active 15 min before)
- **Formation modules grid (2×3):** Each card shows module name, description, progress bar (green fill), % label, [Continue] button
- **Featured resources row:** Horizontal scroll — YouTube thumbnail cards with title + duration badge
- **Recent recordings:** List of past sessions with [Watch Recording] links

---

### 3.6 Resources (`/resources`)

**Layout:** Filter bar + responsive grid

**Filter bar (horizontal):**
- Category chips: All | Videos | Documents | Doctrine | Pastoral | Liturgy | Prayer
- Module filter pills (6 modules)
- Active filter: forest green fill + white text

**Resource cards (grid, 3 columns → 2 → 1):**
- **Video card:** YouTube thumbnail (auto-fetched), play icon overlay, title, duration badge (forest green), module tag
- **PDF card:** Green gradient background with document icon, title, file size, [View] + [Download] buttons

---

### 3.7 Sessions (`/sessions`)

**Two sections:**

**Upcoming Sessions:**
- Calendar-style cards — date circle (large, forest green), title, host, platform badge (Zoom/Meet)
- [Join Session] button — disabled until 15 min before (grey with tooltip), active = green

**Past Recordings:**
- List layout — smaller cards
- Thumbnail | title | date | duration | [Watch Recording] button

---

### 3.8 Admin Dashboard (`/admin`)

**Layout:** Slim dark sidebar + light content area

**Sidebar (220px, `#161b22`):**
- Logo + "Admin" badge
- Nav groups: Overview | Management | System
- Links: Dashboard, Couples, Payments, Sessions, Resources, Courses, Analytics, Admins, Audit Log, View Site
- Footer: truncated email, [Sign Out] button (red border)

**Content area (white/light grey):**
- Topbar: page title + hamburger (mobile)
- **Stat row (4 cards):** Total Couples | Paid | Revenue (₦) | Awaiting Payment
- **Charts row (2 cols):** Revenue bar chart (last 6 months) | Registrations line chart
- **Recent registrations table:** Couple name | Ref | Email | Status badge | Date

---

### 3.9 Admin Resources (`/admin/resources`)

**Header:** "Resources" title + [+ Add Resource] button (right)
**Stats row (4 cards):** Total | Videos | Documents | Featured
**Table:**
| Title | Type | Category | Module | Published | Added | Actions |
- Type: green "Video" badge or amber "PDF" badge
- Published toggle: AJAX switch (on/off)
- Actions: Edit (pencil icon) | Delete (trash icon, red, confirm dialog)

---

### 3.10 Admin Sessions (`/admin/sessions`)

**Header:** "Live Sessions" + [+ Schedule Session] button
**Stats row:** Total | Upcoming | Completed | Recordings Posted
**Table:**
| Title | Date & Time | Host | Platform | Status | Recording | Actions |
- Status badges: upcoming (blue) | live (green pulse) | completed (grey) | cancelled (red)
- Actions: Edit | Cancel (AJAX) | Delete

---

## 4. User Flows

### Flow A — New Couple Registration

```
Landing Page
    ↓ [Register as a Couple]
Register Step 1 (Bride info)
    ↓ [Continue]
Register Step 2 (Groom info)
    ↓ [Continue]
Register Step 3 (Contact)
    ↓ [Continue]
Register Step 4 (Religious)
    ↓ [Continue]
Register Step 5 (Medical)
    ↓ [Continue]
Register Step 6 (Documents)
    ↓ [Continue]
Register Step 7 (Review)
    ↓ [Complete Registration]
Email sent with registration number (e.g. CA-2026-0042)
    ↓
Payment Page → Pay ₦50,000 via Paystack
    ↓ (Paystack webhook confirms)
Dashboard (full access unlocked)
```

### Flow B — Returning Couple Login

```
Landing Page → [Sign In]
    ↓
Login Page
    Enter registration number + password
    ↓ (valid credentials)
Dashboard
    ↓
[Formation Modules] → individual module → video/PDF resources
[Live Sessions] → join active session OR watch recording
[Resources] → browse and filter library
[Profile] → edit details, change password
```

### Flow C — Admin Login & Daily Operations

```
/admin/login (separate from couple login)
    Enter email + password
    ↓
Admin Dashboard (stats + charts)
    ↓ sidebar nav
Couples → view all registrations, search, toggle payment status
Payments → revenue overview, payment history
Sessions → schedule new session → edit → add recording URL after
Resources → upload PDF or paste YouTube/Vimeo URL → set module + category
Admins → create/remove admin accounts
Audit Log → read-only log of all admin actions
```

### Flow D — Admin Scheduling a Live Session

```
Admin Dashboard → [Sessions] → [+ Schedule Session]
    ↓
Fill form:
  - Title, topic, description
  - Host name & role
  - Date/time (WAT)
  - Platform (Zoom/Meet/Teams)
  - Meeting URL, ID, password
  - Formation module
    ↓ [Save Session]
Session appears in couple dashboard "Upcoming Sessions"
    ↓ (after session)
Admin → Sessions → Edit → Paste YouTube recording URL
Recording appears in couple dashboard "Past Recordings"
```

---

## 5. Component Library

### Buttons
| Variant | Background | Text | Use |
|---|---|---|---|
| Primary | `#1B4332` | White | Main CTA |
| Secondary | White | `#1B4332` | Secondary action |
| Ghost | Transparent | `#1B4332` | Tertiary, cancel |
| Danger | `#CF222E` | White | Delete, destructive |
| Gold | `#C9A84C` | White | Special CTA (register) |

All buttons: 6px border-radius, Inter 600, 12.5px, gap between icon + label

### Badges
| Type | Background | Text |
|---|---|---|
| Success | `#DCFCE7` | `#166534` |
| Error/Danger | `#FEE2E2` | `#CF222E` |
| Warning | `#FEF3C7` | `#92400E` |
| Info | `#DBEAFE` | `#0550AE` |
| Neutral | `#F3F4F6` | `#656D76` |

### Form Inputs
- Height: 40px (desktop), 44px (mobile — touch target)
- Border: 1px `#D1E8DA`, radius 8px
- Focus ring: `#40916C` with 3px offset glow
- Error state: red border, red hint text below
- Labels: 12px, 600 weight, `#1C2B25`
- Hints: 11px, `#7A8F7A`

### Cards
- Background: white
- Border: 1px `#D1E8DA`
- Border-radius: 12px
- Shadow: `0 1px 3px rgba(0,0,0,.06)`
- Padding: 20px (desktop), 16px (mobile)

---

## 6. Responsive Breakpoints

| Name | Width | Layout change |
|---|---|---|
| Mobile | < 480px | Single column, stacked everything |
| Tablet | 480–768px | 2-column grids, sidebar hidden |
| Desktop | 768–1200px | Full layout, sidebar visible |
| Wide | > 1200px | Max-width 1200px content, centred |

---

## 7. Accessibility

- All interactive elements have `aria-label` where icon-only
- Colour contrast: all text passes WCAG AA (4.5:1 minimum)
- Focus styles visible on all inputs and buttons (no `outline: none` without replacement)
- Form errors announced via `aria-live="polite"`
- Images have `alt` attributes; decorative SVGs have `aria-hidden="true"`

---

## 8. Animation Principles

- Page enter: `opacity 0 → 1` + `translateY(12px) → 0`, duration 300ms, ease-out
- Staggered cards: 60ms delay per card (`.delay-1`, `.delay-2`, etc.)
- Button hover: background colour transition 150ms
- Flash messages: slide in from right 250ms, auto-dismiss 5s
- No animations if `prefers-reduced-motion: reduce` is set

---

## 9. Iconography

Library: Font Awesome 6.4 (CDN)
Style: Regular / Solid only (consistent weight)
Key icons used:
- `fa-church` — Catholic theme
- `fa-heart` — Couples
- `fa-shield-halved` — Admin / Security
- `fa-video` — Sessions
- `fa-folder-open` — Resources
- `fa-book-open` — Courses / Modules
- `fa-clipboard-list` — Audit log
- `fa-naira-sign` — Payments (₦)
- `fa-right-to-bracket` — Sign in
- `fa-chart-line` / `fa-chart-bar` — Analytics

---

*This spec represents the production state of COR AMANS as of June 2026.*
*Feed this document to Claude Design, Figma AI, or v0 to generate matching mockups.*
