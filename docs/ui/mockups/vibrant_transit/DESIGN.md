---
name: Vibrant Transit
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f3'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#5b403f'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f1f1f1'
  outline: '#8f6f6e'
  outline-variant: '#e4bebc'
  surface-tint: '#bb162c'
  primary: '#b7122a'
  on-primary: '#ffffff'
  primary-container: '#db313f'
  on-primary-container: '#fffbff'
  inverse-primary: '#ffb3b1'
  secondary: '#5f5e5e'
  on-secondary: '#ffffff'
  secondary-container: '#e4e2e1'
  on-secondary-container: '#656464'
  tertiary: '#805200'
  on-tertiary: '#ffffff'
  tertiary-container: '#a06900'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdad8'
  primary-fixed-dim: '#ffb3b1'
  on-primary-fixed: '#410007'
  on-primary-fixed-variant: '#92001c'
  secondary-fixed: '#e4e2e1'
  secondary-fixed-dim: '#c8c6c6'
  on-secondary-fixed: '#1b1c1c'
  on-secondary-fixed-variant: '#474747'
  tertiary-fixed: '#ffddb4'
  tertiary-fixed-dim: '#ffb954'
  on-tertiary-fixed: '#291800'
  on-tertiary-fixed-variant: '#633f00'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
typography:
  headline-xl:
    fontFamily: Montserrat
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Montserrat
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-lg-mobile:
    fontFamily: Montserrat
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  container-margin: 20px
  gutter: 16px
  touch-target-min: 48px
  card-padding: 16px
---

## Brand & Style

The design system is engineered for the high-velocity, high-stress environment of long-distance travel. It centers on a **Modern Corporate** aesthetic with a **High-Contrast** edge, ensuring that the interface remains legible and actionable even in suboptimal lighting or during a bumpy bus ride. 

The brand personality is energetic, dependable, and appetizing. It balances the urgency of transit—where timing is everything—with the comfort of a warm meal. Visuals are crisp and unrefined, using significant whitespace to reduce cognitive load, while bold color blocks drive users toward primary conversion points like "Order Now" and "Track Delivery."

## Colors

The palette is dominated by **Hunger Red**, a high-chroma hue designed to stimulate appetite and command immediate attention. 

- **Primary (Hunger Red):** Used for primary action buttons, price points, and critical status updates.
- **Secondary (Road Grey):** Provides high-contrast grounding for headers and body text, ensuring maximum readability.
- **Success (Arrival Green):** Specifically reserved for "Delivered" statuses and positive feedback loops.
- **Dark Mode Strategy:** Transitions from Pure White (#FFFFFF) surfaces to a "Night Road" palette using #121212 as the base and #1E1E1E for elevated cards, maintaining the vibrancy of the Primary Red without causing eye strain.

## Typography

This design system utilizes a dual-font strategy. **Montserrat** provides a bold, geometric presence for headlines, creating a sense of urgency and modernity. **Inter** is used for all functional text and body copy due to its exceptional legibility at small sizes and high x-height, which is critical for mobile interfaces.

Typography scales are slightly enlarged compared to standard web apps to account for the physical movement of the user. Headlines use a tight letter-spacing to feel impactful, while labels use slightly increased spacing for clarity.

## Layout & Spacing

The layout follows a **Fluid Grid** model optimized for mobile-first consumption. A standard 4-column grid is used for mobile, expanding to 8 columns for tablets. 

The spacing rhythm is built on an **8px base unit**. Significant "Safe Zones" are maintained around touch targets to prevent accidental taps during travel.
- **Margins:** A generous 20px side margin keeps content away from screen edges.
- **Vertical Rhythm:** Elements are grouped using 8px (tight), 16px (standard), and 32px (section break) increments.

## Elevation & Depth

Hierarchy is established through **Ambient Shadows** and **Tonal Layers**. 
- **Surface Level 0:** The main background (#FFFFFF).
- **Surface Level 1 (Cards):** Uses a very soft, diffused shadow (0px 4px 20px rgba(0,0,0,0.06)) to lift food items and restaurant listings off the page.
- **Surface Level 2 (Floating Actions):** Higher elevation with a more pronounced shadow to indicate primary utility (e.g., "View Cart" button).
- **Interactive States:** On press, cards should visually "sink" by reducing shadow spread, providing tactile feedback to the user.

## Shapes

The design system employs a **Rounded** (Level 2) shape language. This creates a friendly and approachable feel while remaining efficient.
- **Standard Radius:** 0.5rem (8px) for input fields and small buttons.
- **Large Radius:** 1rem (16px) for item cards and modal sheets, as requested.
- **Pill Shapes:** Used exclusively for status badges and filter chips to differentiate them from actionable buttons.

## Components

### Buttons
- **Primary:** Hunger Red background, white text, bold weight. Minimum height of 56px for high-stress accessibility.
- **Secondary:** Transparent background with a 2px Road Grey border.

### Status Badges
- **Cooking:** Amber/Tertiary tint.
- **On the way:** Primary Red tint.
- **Bus approaching:** Arrival Green tint. 
- *Styling:* Small, semi-transparent background with high-contrast text.

### Progress Steppers
- Use a thick 4px line to connect nodes. Completed stages use Arrival Green; active stages pulse in Hunger Red.

### Cards
- Food cards feature a full-bleed image at the top with a 16px corner radius. Content below includes a bold price and a prominent "Add" button that extends to the card's edge for easy tapping.

### Inputs & Search
- Search bars use a subtle #F4F4F4 background with a 16px radius to look "pill-like" and inviting. Inner icons are tinted Road Grey at 60% opacity.