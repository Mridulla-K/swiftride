# Design System Document: The Kinetic Pulse

## 1. Overview & Creative North Star: "The Kinetic Pulse"
The design system for this ride-hailing experience is built on the concept of **"The Kinetic Pulse."** In a world of static, grid-bound apps, we represent motion, speed, and precision. We move beyond the "standard" dark mode by treating the UI not as a flat screen, but as a deep, luminous cockpit.

**Creative North Star: The Kinetic Pulse**
*   **Intentional Asymmetry:** We break the rigid central axis. Large headlines may hang off the left margin while action buttons float with generous breathing room on the right.
*   **Depth through Luminosity:** We don't use shadows to create depth; we use light. Backgrounds "glow" from beneath surfaces, and primary actions feel like self-illuminated glass.
*   **Editorial Authority:** By pairing the technical precision of *Manrope* with the expressive geometry of *Plus Jakarta Sans*, we create an interface that feels like a premium concierge service rather than a utility tool.

---

## 2. Colors: Depth over Decoration
Our palette is rooted in the depth of midnight, using `electric blue` as a functional beacon and `surge orange` as a high-energy alert.

### The "No-Line" Rule
**Traditional 1px borders are strictly prohibited for sectioning.** To separate a ride card from the background map or a profile section from a list, use background color shifts. 
*   *Example:* Place a `surface_container_low` card atop a `surface` background. The eye perceives the boundary through tonal contrast, creating a more "organic" and high-end feel.

### Surface Hierarchy & Nesting
Treat the UI as layered sheets of obsidian and frosted sapphire.
*   **Level 0 (Base):** `surface` (#10131c) – The foundation.
*   **Level 1 (Sections):** `surface_container_low` (#191b24) – Broad structural areas.
*   **Level 2 (Interactive Cards):** `surface_container` (#1d1f28) – Standard clickable elements.
*   **Level 3 (Prominence):** `surface_container_highest` (#32343e) – Active states or high-priority modals.

### The "Glass & Gradient" Rule
To elevate the experience, use **Glassmorphism** for floating map overlays (e.g., the "Confirm Ride" drawer). Use `surface_container` at 80% opacity with a `backdrop-blur` of 20px. 
*   **Signature Textures:** For the primary CTA, do not use a flat hex. Apply a subtle linear gradient from `primary` (#b3c5ff) to `primary_container` (#0066ff) at a 135° angle. This adds "soul" and mimics the sheen of a premium vehicle.

---

## 3. Typography: The Editorial Voice
We use typography to guide the eye through the "chaos" of a moving city.

*   **Display & Headlines (`Plus Jakarta Sans`):** Our "Expressive" tier. Use `display-md` for trip ETAs and `headline-sm` for destination titles. The geometric nature of Jakarta Sans communicates modernity and speed.
*   **Body & Labels (`Manrope`):** Our "Functional" tier. Manrope is highly legible at small sizes. Use `body-md` for driver details and `label-sm` for technical metadata (e.g., license plates).
*   **The Hierarchy Rule:** Never use more than three type scales on a single screen. Contrast `headline-lg` with `body-sm` to create a "Big/Small" editorial rhythm that looks custom-designed.

---

## 4. Elevation & Depth: Tonal Layering
We reject the heavy, muddy shadows of the early mobile era. Hierarchy is achieved through "Tonal Stacking."

*   **The Layering Principle:** To lift a "Vehicle Selection" card, place a `surface_container_low` object inside a `surface_container_lowest` container. The slight lift in brightness communicates elevation without a single shadow.
*   **Ambient Shadows:** If a floating element (like a "Recenter Map" button) requires a shadow, it must be `on_surface` color at 6% opacity, with a blur of `32px` and a Y-offset of `16px`. This mimics the soft, ambient light of a city at night.
*   **The Ghost Border Fallback:** For accessibility in high-glare environments, use a 1px border of `outline_variant` at **15% opacity**. It should be felt, not seen.

---

## 5. Components: Precision Primitives

### Buttons (The Kinetic Triggers)
*   **Primary:** Gradient of `primary` to `primary_container`. Corner radius: `full`. No border. High-contrast `on_primary_container` text.
*   **Secondary:** No background. `Ghost Border` (outline-variant @ 20%). Corner radius: `xl`.
*   **Tertiary:** Text-only. Use `primary` color. Reserved for "Cancel" or "Edit."

### Input Fields (The Destination HUD)
*   **The Frame:** Use `surface_container_high`. Avoid boxes; use a bottom-only 2px accent of `primary` when focused.
*   **Spacing:** Use `spacing.4` (1rem) for internal padding to ensure the UI feels "airy."

### Cards & Lists (The Streamlined Feed)
*   **Forbid Dividers:** Do not use lines to separate "UberX" from "UberXL." Use `spacing.3` (0.75rem) of vertical white space and a subtle background shift to `surface_container_low` on the selected item.
*   **The "Ride-Hailing HUD" Card:** Map-based cards should use `xl` (1.5rem) corner radius to feel like a modern smartphone's physical corners.

### Custom Component: The Surge Pulse (Accents)
*   **Pricing Chips:** When surge pricing is active, use `tertiary_container` (#ad5d00) with `on_tertiary_container` text. Apply a soft `tertiary` glow (10% opacity) around the chip to signal "heat" and urgency.

---

## 6. Do's and Don'ts

### Do:
*   **DO** asymmetry. Shift the "Arriving in 5 min" text to the far left and the driver's photo to the far right, leaving a wide "void" in the center for a clean look.
*   **DO** use the `full` roundedness scale for all action buttons to contrast with the `xl` roundedness of cards.
*   **DO** prioritize "Negative Space." If a screen feels cluttered, increase the spacing from `4` (1rem) to `6` (1.5rem).

### Don't:
*   **DON'T** use pure black (#000000). Always use `surface` (#10131c) to maintain the "Midnight Blue" premium aesthetic.
*   **DON'T** use 100% opaque borders. They create "visual noise" that makes the app look like a generic template.
*   **DON'T** use standard Material shadows. They are too "heavy" for this high-end, light-based system.
