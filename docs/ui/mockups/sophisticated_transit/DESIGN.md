---
name: Sophisticated Transit
colors:
  surface: '#f8f9fa'
  surface-dim: '#d9dadb'
  surface-bright: '#f8f9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f5'
  surface-container: '#edeeef'
  surface-container-high: '#e7e8e9'
  surface-container-highest: '#e1e3e4'
  on-surface: '#191c1d'
  on-surface-variant: '#40484b'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f2'
  outline: '#70787c'
  outline-variant: '#c0c8cb'
  surface-tint: '#306576'
  primary: '#003441'
  on-primary: '#ffffff'
  primary-container: '#0f4c5c'
  on-primary-container: '#87bbce'
  inverse-primary: '#9acee1'
  secondary: '#a04100'
  on-secondary: '#ffffff'
  secondary-container: '#fd7729'
  on-secondary-container: '#5e2300'
  tertiary: '#660010'
  on-tertiary: '#ffffff'
  tertiary-container: '#90001b'
  on-tertiary-container: '#ff9694'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b6ebfe'
  primary-fixed-dim: '#9acee1'
  on-primary-fixed: '#001f28'
  on-primary-fixed-variant: '#114d5d'
  secondary-fixed: '#ffdbcc'
  secondary-fixed-dim: '#ffb693'
  on-secondary-fixed: '#351000'
  on-secondary-fixed-variant: '#7a3000'
  tertiary-fixed: '#ffdad8'
  tertiary-fixed-dim: '#ffb3b0'
  on-tertiary-fixed: '#410007'
  on-tertiary-fixed-variant: '#92001b'
  background: '#f8f9fa'
  on-background: '#191c1d'
  surface-variant: '#e1e3e4'
typography:
  display-lg:
    fontFamily: Montserrat
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Montserrat
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Montserrat
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Montserrat
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Montserrat
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Montserrat
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Montserrat
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Montserrat
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
---

## Brand & Style

The design system is built on the narrative of "Sophisticated Transit"—a blend of logistical precision and culinary warmth. It targets an audience that values reliability and premium service over the chaotic energy of typical discount-driven food apps. The personality is authoritative yet welcoming, aiming to evoke a sense of calm efficiency.

The design style is **Corporate / Modern** with a focus on high-end editorial clarity. It utilizes generous whitespace, structured layouts, and a deliberate lack of aggressive gradients or "loud" UI patterns found in competitors. The interface prioritizes high-legibility surfaces and purposeful accent hits to guide the user through a seamless ordering and tracking experience.

## Colors

The palette departs from the standard "red and yellow" of the food industry to establish a unique identity centered on trust and heat.

- **Primary (Midnight Teal):** Used for navigation, headers, and primary branding elements. It represents the "Wheels"—the logistical backbone of the service.
- **Secondary (Sunset Amber):** Reserved exclusively for high-priority actions, status indicators of warmth, and "freshness" callouts.
- **Tertiary (Vineyard Red):** A deep muted red used sparingly for error states or specific premium categories.
- **Surface & Background:** A dual-tone grey system. The Background (#EDF2F4) provides a cool foundation, while the Surface (#F8F9FA) creates distinct content areas for high legibility.

## Typography

This design system utilizes **Montserrat** across all levels to maintain a cohesive, geometric, and modern feel. 

- **Display & Headlines:** Use tighter letter-spacing and bold weights to convey authority. On mobile, large display sizes must scale down to maintain a balanced vertical rhythm.
- **Body Text:** Use Regular (400) weight for maximum readability against the light surfaces. Line heights are kept generous to prevent information density from feeling overwhelming.
- **Labels:** Use Medium or Semi-Bold weights with slight tracking (letter-spacing) for uppercase metadata or button text, ensuring clarity even at small scales.

## Layout & Spacing

The layout philosophy follows a **Fluid Grid** model based on an 8px square baseline. 

- **Desktop:** A 12-column grid with 24px gutters. Content is usually contained within a max-width of 1280px to maintain the premium, curated feel.
- **Mobile:** A 4-column grid with 16px margins.
- **Spacing Logic:** Vertical rhythm is strictly enforced in multiples of 8. Use `md` (24px) for most component spacing and `lg` (40px) for section headers.

## Elevation & Depth

To maintain the "Sophisticated Transit" look, depth is achieved through **Tonal Layers** and **Low-contrast outlines** rather than heavy shadows.

- **Level 0:** Background (#EDF2F4).
- **Level 1:** Surface cards (#F8F9FA) with a 1px border of #D1D9DB (a slightly darker tint of the background).
- **Level 2:** Floating elements (e.g., active Cart or Navigation Bar) use an ambient, extra-diffused shadow: `0px 4px 20px rgba(15, 76, 92, 0.08)`. The shadow is tinted with the Primary color to maintain brand harmony.
- **Interactions:** Hover states should involve a subtle shift in background color or a 2px elevation lift rather than a color change to the primary accent.

## Shapes

The design system uses a **Rounded** shape language to soften the "Transit" theme and make the food experience feel more inviting.

- **Standard Elements:** 8px (0.5rem) radius for buttons, input fields, and small cards.
- **Large Containers:** 16px (1rem) radius for main content sections or featured banners.
- **Interactive Indicators:** Elements like notification badges or active status dots should remain fully circular (pill-shaped).

## Components

- **Buttons:** Primary buttons use the Midnight Teal background with white text. Secondary/Action buttons use Sunset Amber. Buttons have a fixed height of 48px for a substantial, "premium" touch target.
- **Input Fields:** Use the #F8F9FA surface with a subtle 1px border. On focus, the border thickens to 2px using the Midnight Teal color.
- **Cards:** Cards are the primary vehicle for food items. They feature a 1px stroke and no shadow by default, gaining the ambient shadow only on hover or interaction.
- **Chips:** Used for filtering (e.g., "Vegan", "Fast Delivery"). These use a light tint of the Primary color with dark teal text.
- **Lists:** High-density lists (like order history) use 16px vertical padding between items with a subtle hairline separator.
- **Status Indicators:** "In Transit" uses Midnight Teal; "Preparing" uses Sunset Amber. This links the action color directly to the brand's core values of heat and movement.
- **Tracking Map:** Should be styled with a custom "Silver/Cool" map theme to match the #EDF2F4 background, with the route highlighted in Sunset Amber.