# Design System Strategy: Kinetic Precision

## 1. Overview & Creative North Star
**The Creative North Star: "The Cockpit Intelligence"**

This design system moves away from the "friendly consumer app" aesthetic toward a high-performance, professional instrument. For a driver-facing interface, every millisecond of cognitive load matters. We aren't just building a list of rides; we are building a heads-up display (HUD). 

By utilizing **Organic Brutalism**, we combine the raw, dark atmosphere of satellite imagery with the razor-sharp precision of electric green accents. We break the "template" look through **intentional asymmetry**—where critical action zones (like 'Accept Trip') occupy more visual weight than passive data—and **tonal depth**, ensuring the map feels like the base reality and the UI feels like a sophisticated glass overlay.

---

## 2. Colors & Surface Philosophy
The palette is anchored in `#0e0e0e` to ensure maximum contrast with the satellite map and to preserve the driver's night vision.

### The "No-Line" Rule
**Standard 1px borders are strictly prohibited.** Sectioning must be achieved through background color shifts. To separate a trip detail from the main feed, place a `surface_container_high` card against a `surface_dim` background. This creates a professional, "molded" look rather than a "sketched" look.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. 
*   **Level 0 (Map/Base):** The satellite view.
*   **Level 1 (The Dashboard):** `surface_dim` (#0e0e0e) used for the main background.
*   **Level 2 (Primary Cards):** `surface_container` (#1a1a1a) for ride requests.
*   **Level 3 (Interactive Elements):** `surface_container_highest` (#262626) for inner nested details like fare breakdowns.

### The "Glass & Gradient" Rule
For floating action buttons (FABs) or map overlays, use **Glassmorphism**. Apply `surface_container_low` at 80% opacity with a `backdrop-blur` of 20px. 
*   **Signature Textures:** Use a subtle linear gradient on the `primary` (#8eff71) CTA, transitioning from `#8eff71` to `#2ff801` at a 135-degree angle. This provides a "liquid light" feel that feels premium and active.

---

## 3. Typography: The Editorial Scale
We use **Plus Jakarta Sans** for its geometric clarity and modern "tech" weight.

*   **Display (lg/md/sm):** Reserved for high-priority numbers (e.g., "$42.50"). These should use a tight letter-spacing (-0.02em) to feel authoritative.
*   **Headlines:** Used for destination names. The large scale ensures readability at arm's length in a car mount.
*   **Labels (md/sm):** Used for "Total Distance" or "ETA" markers. These must be in `on_surface_variant` (#adaaaa) to maintain hierarchy.
*   **Brand Identity:** The contrast between `display-lg` numbers and `label-sm` metadata creates an editorial "magazine" feel, emphasizing what the driver cares about most: earnings and time.

---

## 4. Elevation & Depth
In this system, depth is a function of light, not lines.

*   **The Layering Principle:** Avoid shadows on standard cards. Instead, stack `surface_container_low` on top of `surface`. The human eye perceives the color shift as a change in elevation.
*   **Ambient Shadows:** For critical floating elements (e.g., "New Request" pop-up), use an extra-diffused shadow: `0px 24px 48px rgba(0, 0, 0, 0.5)`. The shadow should feel like a soft glow of darkness.
*   **The "Ghost Border" Fallback:** If a container sits on a map and needs definition, use the `outline_variant` (#484847) at **15% opacity**. It should be felt, not seen.
*   **Glassmorphism:** Use `surface_tint` (#8eff71) at 5% opacity as a thin inner-stroke on glass cards to simulate the "edge" of a glass panel catching the light.

---

## 5. Components

### Buttons
*   **Primary:** High-visibility `primary` (#8eff71) background with `on_primary` (#0d6100) text. 12px rounded corners.
*   **Secondary:** `surface_container_highest` background with `primary` text. No border.
*   **Tertiary:** Ghost style. No background, `primary` text, underlined only during active states.

### Cards & Lists
*   **Forbid Dividers:** Do not use lines to separate list items. Use a `1.5` (0.375rem) spacing gap or alternate between `surface_container` and `surface_container_low`.
*   **Interaction:** On press, a card should shift from `surface_container` to `surface_bright` (#2c2c2c).

### Input Fields
*   **State:** Default state uses `surface_container_high`. On focus, the container remains the same, but a `primary` (#8eff71) 2px "Ghost Border" (20% opacity) appears.

### HUD-Specific Components
*   **Dynamic Distance Bar:** A horizontal bar using a gradient from `primary_dim` to `primary`. As the driver nears the destination, the bar fills. 
*   **Status Pill:** Floating pill-shaped chips using `secondary_container` with `on_secondary` text to denote "Online" or "Busy" status.

---

## 6. Do’s and Don’ts

### Do:
*   **Do** use `20` (5rem) or `24` (6rem) spacing at the bottom of the screen to ensure thumb-reachability for drivers.
*   **Do** use `primary` (#8eff71) sparingly. If everything is electric green, nothing is important. Use it only for the "Next Step."
*   **Do** leverage the `display-lg` type for earnings. It is the driver's primary motivation.

### Don't:
*   **Don't** use 100% white (#ffffff) for long-form body text. Use `on_surface_variant` (#adaaaa) to reduce eye strain during night shifts.
*   **Don't** use traditional "Material Design" shadows. They look muddy on satellite backgrounds. Stick to tonal layering.
*   **Don't** use sharp 90-degree corners. The `12px` (DEFAULT) roundedness is the signature of this system—it makes the tech feel ergonomic and modern.
