# UX Notes

## Responsive breakpoints
- **Phone (default, <640px):** single-column layout, touch-first buttons, tables rendered as stacked cards.
- **Tablet (>=640px):** denser spacing, wider stat grid, header actions aligned horizontally.
- **Desktop (>=768px):** two-column dashboard layout, data shown in semantic tables with sticky hierarchy.

## Component rules
- **Card** is the base section shell with optional title/actions.
- **Stat** is for single KPI values (label + prominent numeric value).
- **Badge** encodes compact semantic status (neutral/success/danger).
- **Button** has variants (`primary`, `secondary`, `danger`) and keeps focus-visible styles for accessibility.
- **DataTable** keeps one API for both desktop and mobile:
  - desktop: `<table>` for scanability,
  - mobile: cards using the same column definitions.

## Interaction/accessibility notes
- Keyboard focus indicators use visible outline.
- Inputs have explicit labels and numeric keypad hints (`inputMode="decimal"`).
- Color is not the only cue for state: badges include text labels.
