---
name: Thindi
colors:
  surface: '#161311'
  surface-dim: '#161311'
  surface-bright: '#3d3836'
  surface-container-lowest: '#100e0c'
  surface-container-low: '#1e1b19'
  surface-container: '#221f1d'
  surface-container-high: '#2d2927'
  surface-container-highest: '#383431'
  on-surface: '#e9e1dd'
  on-surface-variant: '#e1bfb5'
  inverse-surface: '#e9e1dd'
  inverse-on-surface: '#34302d'
  outline: '#a88a81'
  outline-variant: '#59413a'
  surface-tint: '#ffb59d'
  primary: '#ffb59d'
  on-primary: '#5d1800'
  primary-container: '#f26430'
  on-primary-container: '#511400'
  inverse-primary: '#ac3500'
  secondary: '#f2be71'
  on-secondary: '#442b00'
  secondary-container: '#684400'
  on-secondary-container: '#e6b367'
  tertiary: '#85cfff'
  on-tertiary: '#00344c'
  tertiary-container: '#1a9ad4'
  on-tertiary-container: '#002d42'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdbd0'
  primary-fixed-dim: '#ffb59d'
  on-primary-fixed: '#390c00'
  on-primary-fixed-variant: '#832600'
  secondary-fixed: '#ffddb1'
  secondary-fixed-dim: '#f2be71'
  on-secondary-fixed: '#291800'
  on-secondary-fixed-variant: '#614000'
  tertiary-fixed: '#c7e7ff'
  tertiary-fixed-dim: '#85cfff'
  on-tertiary-fixed: '#001e2e'
  on-tertiary-fixed-variant: '#004c6c'
  background: '#161311'
  on-background: '#e9e1dd'
  surface-variant: '#383431'
typography:
  display-lg:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Playfair Display
    fontSize: 34px
    fontWeight: '600'
    lineHeight: 42px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Playfair Display
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  title-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system powers Thindi, a curated restaurant recommendation web app for Bangalore. It evokes the atmosphere of a warm night-kitchen and spice market: intimate, tactile, and grounded in culinary craft.

- **Target Audience:** Bangalore diners, food enthusiasts, and explorers looking for trusted, curated recommendations—from late-night darshinis and legacy filter-coffee spots to contemporary tasting rooms.
- **Emotional Response:** Warmth, appetite, and quiet confidence. The interface should feel like a well-worn, dimly lit menu or a chef's counter at dusk—inviting, unhurried, and free of generic SaaS clutter.
- **Design Style:** A blend of **Minimalism** and **Tactile / Editorial** craft. Deep espresso surfaces, crisp 1px warm borders, and subtle radial warmth create a focused stage where food photography, neighborhood tags, and editorial notes take center stage. No neon glows, no purple gradients, and no heavy drop shadows.

## Colors

The palette is anchored in deep espresso and roasted charcoal tones, punctuated by chili/saffron orange-red and muted gold.

- **Surfaces & Backgrounds:**
  - Base Canvas: `#14110F` (deep espresso)
  - Elevated Surface / Cards: `#1C1714`
  - Interactive / Hover Surface: `#241E1A`
  - Subtle Warm Radial Gradient: Use sparingly behind hero sections or featured cards (e.g., `radial-gradient(circle at 50% 0%, rgba(232, 93, 42, 0.08), transparent 65%)`).
- **Accents:**
  - Primary (`#E85D2A`): Chili/saffron orange-red for primary actions, active states, and key highlights.
  - Secondary (`#D4A359`): Muted gold for ratings, curated badges, neighborhood tags, and subtle editorial accents.
- **Text & Borders:**
  - Primary Text: `#F5EFE6` (warm off-white)
  - Secondary / Muted Text: `#A89B8C` (soft taupe)
  - Hairline Borders: `#332B25` (crisp 1px warm border)

## Typography

The type system pairs **Playfair Display** for editorial warmth and the Thindi brand mark with **Plus Jakarta Sans** for crisp, approachable UI controls and body copy.

- **Editorial & Brand:** Use `Playfair Display` for the Thindi wordmark, hero titles, and restaurant collection headers. On mobile viewports, `display-lg-mobile` scales down to 34px to preserve breathing room.
- **UI & Body:** Use `Plus Jakarta Sans` across all restaurant descriptions, neighborhood filters, metadata, and interactive controls.
- **Hierarchy:** Keep `label-sm` uppercase or semi-bold with slight tracking (`0.04em`) for cuisine tags, price tiers, and "Open Now" indicators.

## Layout & Spacing

This design system uses a **12-column fluid grid** with a maximum content container width of `1200px` centered on desktop viewports.

- **Desktop (≥ 1024px):** 12 columns with `1rem` (`16px`) gutters and `2rem` (`32px`) outer margins. Restaurant discovery grids typically span 4 columns per card (3 cards per row), while editorial features span 6 or 12 columns.
- **Tablet (640px – 1023px):** 8 columns with `1rem` gutters and `1.5rem` (`24px`) outer margins. Cards reflow to 2 per row.
- **Mobile (< 640px):** 4 columns with `1rem` gutters and `1rem` (`16px`) outer margins. Cards stack in a single column with `space-md` vertical gaps.
- **Rhythm:** Use `space-sm` (`0.5rem`) for tight metadata clusters (e.g., rating + neighborhood), `space-md` (`1rem`) for card internal padding, and `space-xl` (`2rem`) between major page sections.

## Elevation & Depth

Hierarchy is established through **tonal layers** and **low-contrast 1px warm borders** rather than heavy drop shadows.

- **Surface Stacking:** Step up from the `#14110F` base canvas to `#1C1714` for cards and panels, and `#241E1A` for hovered states, dropdowns, and active drawers.
- **Crisp Borders:** Every elevated container, input, and card is framed by a `1px solid #332B25` border to maintain sharp definition in low-light environments.
- **Subtle Warmth:** For featured hero cards or active modals, apply a faint ambient shadow (`0 12px 32px rgba(0, 0, 0, 0.45)`) paired with a subtle top-edge warm highlight (`rgba(245, 239, 230, 0.04)`). Avoid neon glows or colored outer shadows.

## Shapes

This design system uses a **Soft (`1`)** roundedness scale—clean and structured, with just enough warmth to feel approachable without losing editorial precision.

- **Standard Controls & Inputs:** `0.25rem` (`4px`) to `0.5rem` (`8px`) radius for buttons, search bars, and filter chips.
- **Cards & Containers:** `0.5rem` (`8px`) for restaurant cards and `0.75rem` (`12px`) for featured editorial banners or modals.
- **Badges & Pills:** Full pill (`9999px`) is reserved strictly for small status indicators (e.g., "Open Now", "Must Try") and compact filter chips.

## Components

- **Buttons:**
  - *Primary:* Solid `#E85D2A` background, `#F5EFE6` text, `0.5rem` radius, `Plus Jakarta Sans` `label-lg`. Hover shifts to a slightly deeper burnt chili (`#D14E1F`).
  - *Secondary:* Transparent or `#1C1714` background with `1px solid #332B25` border and `#F5EFE6` text. Hover transitions background to `#241E1A`.
  - *Ghost:* `#A89B8C` text, transitioning to `#F5EFE6` on hover.
- **Chips (Cuisine & Neighborhood Filters):**
  - Default state: `#1C1714` fill, `1px solid #332B25` border, `#A89B8C` text, `9999px` radius.
  - Active state: `rgba(232, 93, 42, 0.14)` fill, `1px solid #E85D2A` border, `#F5EFE6` text.
- **Cards (Restaurant & Dish Recommendations):**
  - `#1C1714` surface, `1px solid #332B25` border, `0.5rem` radius.
  - Top 16:10 image container with subtle bottom gradient scrim for legibility if overlaid.
  - Card body uses `space-md` padding: restaurant name in `title-md` (`#F5EFE6`), neighborhood and price tier in `body-sm` (`#A89B8C`), and a muted gold (`#D4A359`) rating or "Thindi Pick" badge.
- **Input Fields (Search & Filter):**
  - `#14110F` or `#1C1714` fill, `1px solid #332B25` border, `0.5rem` radius, `#F5EFE6` text, `#A89B8C` placeholder. Focus state highlights the border in `#E85D2A` without an outer neon ring.
- **Lists & Checkboxes / Radio Buttons:**
  - Lists use `1px solid #332B25` hairline dividers between items with `space-md` vertical padding.
  - Checkboxes and radio buttons use `#1C1714` fill with `#332B25` borders; checked states fill with `#E85D2A` and crisp `#F5EFE6` indicators.