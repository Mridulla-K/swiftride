# Design System Document: Tactical Intelligence

## 1. Overview & Creative North Star: "The Kinetic Ledger"
The objective of this design system is to transcend the "standard dashboard" by merging the brutalist utility of a Bloomberg Terminal with the sophisticated aesthetics of high-end aerospace interfaces. 

**The Creative North Star: The Kinetic Ledger.**
This system is not a static display; it is a living, breathing record of real-time movement. It rejects the "fluff" of modern consumer web design in favor of **Information Authority**. We achieve a premium feel not through whitespace, but through **intentional density**, sophisticated tonal layering, and an editorial approach to data hierarchy. We break the "template" look by using asymmetric data clusters, overlapping status modules, and a high-contrast typographic scale that makes even the smallest label feel like a mission-critical coordinate.

---

## 2. Colors & Surface Philosophy
The palette is rooted in the "Deep Night" spectrum, using cold slate tones to provide a stable foundation for the high-energy Teal accents.

### Surface Hierarchy & The "No-Line" Rule
To achieve a high-end feel, **1px solid borders for sectioning are strictly prohibited.** 
*   **The Rule:** Boundaries must be defined solely through background color shifts.
*   **Implementation:** Place a `surface_container_high` module directly onto a `surface` background. The eye should perceive the edge through the shift from `#0e131e` to `#252a36`, not a structural line.

### Nested Layering
Treat the UI as a physical stack of light-absorbing materials.
*   **Base:** `surface` (#0e131e) for the global background.
*   **Primary Containers:** `surface_container_low` (#171b27) for main content areas.
*   **Actionable Modules:** `surface_container_highest` (#303541) for interactive panels or high-focus data points.

### The "Glass & Gradient" Rule
Main CTAs and critical status indicators should utilize the **Signature Texture**: A subtle linear gradient from `primary` (#57f1db) to `primary_container` (#2dd4bf). For floating command palettes, use **Glassmorphism**: Apply `surface_variant` at 60% opacity with a `20px` backdrop blur to allow the data-grid to bleed through the background.

---

## 3. Typography: Technical Authority
We use a dual-font strategy to balance editorial elegance with technical precision.

*   **Display & Headlines (`Space Grotesk`):** Used for high-level metrics and section headers. Its wide, geometric architecture provides an "Aerospace" feel.
*   **Body & Data (`Inter`):** Used for all data-rich environments. The tight tracking and high x-height ensure legibility at the `label-sm` (0.6875rem) level, critical for high-density operations.

**Typography as Brand:** 
Use `display-sm` (2.25rem) for primary KPIs, paired immediately with a `label-sm` (all caps, 0.1rem letter spacing) description. This high-contrast pairing (large value vs. tiny label) creates an authoritative, "instrument panel" aesthetic.

---

## 4. Elevation & Depth
In this system, elevation is an optical illusion created by light, not shadows.

*   **The Layering Principle:** Stacking `surface_container_lowest` cards on a `surface_container_low` section creates a natural "recessed" or "raised" effect. Avoid shadows for static elements.
*   **Ambient Shadows:** Use only for floating modals or context menus. 
    *   *Spec:* `0px 12px 32px rgba(0, 0, 0, 0.4)`. The shadow color must be a darkened tint of the surface, never a generic grey.
*   **The Ghost Border Fallback:** If accessibility requires a container edge, use `outline_variant` (#3c4a46) at **15% opacity**. It should be felt, not seen.

---

## 5. Components: Precision Primitives

### Buttons & Interaction
*   **Primary:** High-vibrancy `primary` (#57f1db) background with `on_primary` (#003731) text. Sharp corners (`rounded-sm`: 0.125rem) to maintain a "tactical" feel.
*   **Secondary:** `surface_container_highest` background with a `ghost border` of the primary teal.
*   **States:** Hover states should not just lighten; they should "glow." Use a subtle outer bloom (3px spread) of the `primary` color.

### Data Modules (Cards)
*   **Constraint:** **No Dividers.** Separate content groups using the **Spacing Scale** (e.g., a `2.5` (0.5rem) gap) or a subtle shift to `surface_container_low`.
*   **Density:** Use `condensed` vertical padding. A standard data row should not exceed `32px` in height.

### Real-Time Indicators
*   **Status Beacons:** Small 4px circles.
    *   *Normal:* `primary_container`
    *   *Warning:* `tertiary_container` (#ffac5a)
    *   *Critical:* `error` (#ffb4ab) with a "breathing" opacity animation (100% to 40%).

### Input Fields
*   **Style:** Underline-only or subtle `surface_container_highest` fills. 
*   **Focus:** Transition the "Ghost Border" to 100% opacity `primary` teal. Use `JetBrains Mono` (if available) for numeric inputs to ensure digit alignment.

### Tactical Additions: "The Data Ribbon"
A unique component for this system: A horizontally scrolling marquee of `label-sm` data points at the very top or bottom of the screen, mimicking a terminal ticker. Use `secondary_fixed_dim` for the text to keep it non-distracting.

---

## 6. Do’s and Don’ts

### Do:
*   **Embrace the Grid:** Use the `spacing-1` (0.2rem) and `spacing-2` (0.4rem) values for ultra-tight data clusters.
*   **Monospace Numbers:** Ensure all tabular data uses monospaced numerals to prevent "jumping" layouts during real-time updates.
*   **Intentional Asymmetry:** If a dashboard has five modules, make one larger or uniquely shaped to break the "bootstrap" grid feel.

### Don’t:
*   **Don't use pure white (#FFFFFF):** It shatters the dark-room immersion. Use `on_surface` (#dee2f2) for maximum brightness.
*   **Don't use large corner radii:** Anything over `8px` (`lg`) will make the system look "soft" and consumer-grade. Stick to `0.125rem` to `0.25rem`.
*   **Don't use standard shadows:** High-density dashboards become "muddy" with shadows. Use tonal shifting first.

---

## 7. Motion & Haptics
*   **Transitions:** All state changes (hover, toggle) must be instantaneous or use a "mechanical" timing (150ms Linear). Avoid "bouncy" or "organic" easing.
*   **Data Updates:** When a value changes, flash the background of the cell briefly (200ms) with a 10% opacity `primary` teal before returning to the base surface color. This alerts the user to real-time movement without a modal interruption.
