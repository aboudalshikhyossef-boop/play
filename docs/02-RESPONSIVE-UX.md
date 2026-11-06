# Responsive UX, Visual Design, and Accessibility

## 1. Non-negotiable quality goal
The interface must be clear, readable, touch-friendly, and correctly laid out on every supported device. A screen is not complete because it looks acceptable on a laptop. It must pass real-device checks, especially on iPhone 4S Safari 9.3.6.

No clipped controls, overlapping panels, hidden text, horizontal scrolling, tiny labels, or actions outside the usable viewport.

## 2. Target viewports
The smallest required layout target is 320 CSS pixels wide, matching the iPhone 4S logical viewport in portrait orientation.

Representative widths:
- 320 CSS px: mandatory legacy-phone baseline.
- 360 CSS px: compact Android.
- 375–390 CSS px: common modern phones.
- 414–430 CSS px: larger phones.
- Tablet and laptop widths: expanded layouts, not a separate application.

Support portrait and landscape. Portrait is the primary phone experience. Landscape must remain usable and must not crop essential controls. Do not confuse physical pixel resolution with CSS viewport width.

## 3. Viewport and page behavior
Use the viewport declaration with width=device-width and initial-scale=1. Do not disable user zoom. Avoid fixed page heights that cut off content. Prefer content-driven height and vertical scrolling when needed. Use min-height: 100vh as a fallback; do not depend on newer viewport units unsupported by older Safari.

The page must not scroll horizontally at 320 CSS px. Long names and text must wrap or truncate deliberately without widening the layout.

## 4. Touch targets and typography
- Target at least 44 by 44 CSS pixels for primary touch targets.
- Provide spacing between adjacent actions to reduce accidental taps.
- Body text should normally be at least 16 CSS px.
- Important labels, timers, coin balances, and action titles need clear hierarchy.
- Never communicate state using color alone; pair color with text, icon, or shape.
- Inputs must remain readable and usable without unwanted browser zoom.
- Avoid dense tables on phones; use stacked cards or concise rows.

## 5. Layout system
Use a mobile-first fluid layout.
- Use simple, well-tested layout primitives supported by the legacy browser.
- Do not rely on CSS Grid.
- If using Flexbox, include necessary legacy WebKit compatibility and verify on the actual iPhone.
- Avoid fragile absolute positioning for core content.
- Use breakpoints only when content needs a different arrangement.
- Use a consistent spacing scale and shared component styles.
- Keep important actions in predictable locations.
- Dialogs must fit small screens; content may scroll internally and close/confirm controls must remain reachable.
- Avoid overlays that obscure essential game state or the only way to continue.

## 6. Arabic and RTL
Arabic is the primary language. Set document language and direction correctly. Test Arabic, numerals, punctuation, mixed Arabic/Latin player names, and long text. Apply RTL intentionally. Ensure icons, arrows, progress indicators, and navigation make sense in RTL. Bundle suitable local fonts with Arabic fallbacks; do not require remote font services. Prevent line-height and glyph clipping.

## 7. Game-screen information hierarchy
On phones, show in this order:
1. Current round and remaining time.
2. Current task or decision.
3. Player's available actions.
4. Relevant personal balance and ability state.
5. Compact public standings and event feed.

Do not cram the full laptop dashboard onto a phone. Use clear sections and progressive disclosure. A player must identify the current task and next action immediately.

Secret choices must remain private on the player's own screen. Do not expose private selections in public shared areas before reveal.

## 8. Visual identity
Proposed direction:
- Dark charcoal/navy base.
- Electric violet primary accent.
- Fire red for danger and revenge.
- Gold for coins and rewards.
- Green for protection and success.
- High-contrast light text.
- Restrained motion and lightweight effects.

Use consistent states: default, pressed, disabled, selected, loading, success, warning, and error.

## 9. Motion and sound
Motion reinforces state changes and must not delay actions. Provide reduced-motion or effects-off preference. Never make animation the only way to understand a result. Sound is optional and user-controlled; start audio only after a user gesture where required. Every audio event also needs a visible equivalent. Keep assets local; no runtime CDN dependency.

## 10. Device verification matrix
Every major screen must be checked on iPhone 4S / iOS 9.3.6 / Safari, Android browsers, and Linux Mint laptop browser.

Test home/join, registration, four-player lobby, ready state, challenge, secret action, revenge, reveal, event overlays, match end, reconnect, and error states.

For each screen, record viewport size, orientation, screenshot, issue, and pass/fail result.

## 11. Definition of done for every screen
- No horizontal overflow at 320 CSS px.
- No clipped or overlapping content.
- All text is readable.
- Primary touch targets are comfortably tappable.
- Actions remain reachable when the on-screen keyboard is open.
- RTL and mixed-direction content render correctly.
- Portrait and landscape remain usable.
- Loading, error, disabled, and disconnected states are designed.
- The screen passes on actual iPhone Safari 9.3.6, not only an emulator.
