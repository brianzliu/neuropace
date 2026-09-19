# Reflow workspace design exploration

This second pass is implemented on `design/playful-learning-themes`. It replaces the first
Fieldnotes/Studio/Afterhours palettes with three selectable material directions. It changes
presentation, not EEG logic or the planned multimodal pipeline.

## What the interface should help someone do

Start listening, save a moment without feeling judged, and return to a specific explanation.
The audience includes college students and adults. Personality comes from objects you want to
touch, not school mascots, streak pressure, grades, or an AI chatbot. The learner's request for
help is the central interaction, so the physical button is the recognizable object.

## Exploration

| Direction considered | Useful idea | Decision |
| --- | --- | --- |
| Pocket audio recorder | Tactile buttons and legible state indicators | Build as Pocket Studio |
| Loose-leaf desk | Layered notes, folded edges, colored tabs | Build as Paper Playground |
| Orbital instrument | Floating ring and translucent shell | Build as Orbit |
| Clay garden | Soft sculptural shapes, organic progression | Keep soft shapes; skip growth rewards that imply measured progress |
| Arcade cabinet | Satisfying physical presses | Borrow press depth; skip scores and distracting flashing |
| Museum audio guide | Quiet reading surface, obvious playback | Keep in the live-session design |
| Chemistry workbench | Interesting equipment | Too clinical for a general learning audience |
| Sticker scrapbook | Personal expression | Too busy around transcripts; retain only paper layering |
| Isometric campus | Rich explorable 3D world | Navigation overhead unrelated to saving a moment |
| AI-generated scroll film | Memorable narrative and atmosphere | Better suited to a separate landing page |
| Animated companion | Character and encouragement | Risks infantilizing adults and competing with a lecture |
| Glass dashboard | Depth and transparency | Restrict glass to Orbit's object and setup panel, not body text |

## Implemented directions

### Pocket Studio, recommended

A small listening instrument on a cool blue desk. Soft blue plastic, an apricot switch, and a
single yellow note give the device a recognizable silhouette. Rounded sans-serif type keeps it
casual without looking like a children's app. Strong button edges communicate what can be pressed.

Tokens: desk `#eef2f8`, white `#ffffff`, ink `#20334f`, blue `#2957b3`, plastic `#739def`,
apricot `#ffb786`. Avenir Next with Trebuchet/system fallbacks. Setup is the main left column;
session history is a quieter right column.

### Paper Playground

A looser composition with an angled raspberry device, a larger lilac note, a yellow switch,
and a taped setup sheet. Palatino gives the reading space a bookish quality without classroom
symbols. Folded and stacked edges replace the plastic panel treatment.

Tokens: desk `#f8f2eb`, paper `#fffdfa`, ink `#51323b`, raspberry `#a33359`, shell `#eaa2b4`,
yellow `#f4d565`. Palatino for display, the existing system sans-serif for controls.

### Orbit

A midnight workspace with a large foreshortened ring behind a frosted device. Lavender controls
and blue paper create depth without glowing body copy. The main panel uses a subtle translucent
material and the section markers become circular.

Tokens: desk `#161d38`, panel `#222c49`, ink `#f2f0ff`, lavender `#bcb0ff`, shell `#818ace`,
blue `#304c67`. The same sans-serif stack as Pocket Studio.

## Composition

All variants keep the same task order so switching designs does not move core controls.
The differences are in materials, object arrangement, typography, and geometry.

```text
Reflow                                      Appearance / Home

Session introduction                 Interactive physical button
Jump to setup                        Explicit preview disclosure

Start a session                      Recent sessions
Profile / lecture / mode             Notes / review / replay
Expandable device settings           Helpful empty state
Start session
```

Text stays left aligned except the object tutorial and empty state. Small-screen layouts stack
these regions. The theme chooser includes miniature material previews, selected state, and
plain-language descriptions. The selection persists locally across routes.

## Interaction and restraint

- The 3D switch is a local tutorial with a depressed state and a short explanation. It never
  generates a hardware event, creates a session, or pretends to capture lesson content.
- Primary action buttons have a shallow physical edge and press displacement.
- CSS perspective, gradients, and inset shadows create depth without a WebGL dependency.
- Motion follows interaction. No endless spinning, auto-playing video, or scroll hijacking.
- Reduced-motion settings remove transitions; keyboard users get focus outlines and a native
  button. Decorative objects are hidden from assistive technology.
- Live and replay views retain their existing layout and smaller header. Palette tokens carry
  across routes; the 3D tutorial stays on the home page.
- Existing simulation labels and offline fallbacks stay visible. Camera/whiteboard capture is
  still planned work, so the UI does not advertise it as a working feature.

## Review and limits

The frontend production build and TypeScript check pass. Browser review should cover every
appearance, the practice button, settings disclosure, theme persistence, and small widths.
This pass does not implement new session features or change the frozen backend contracts.

## Final steering applied

Pocket Studio now uses white `#fcfcf8`, butter yellow `#f4d76a`, charcoal `#3e3d32`, and lilac
paper. Display type is Chalkboard SE with Comic Sans/Trebuchet fallbacks, at regular weight.
The home page is a working review dashboard rather than the large device introduction.
The 3D device tutorial lives in the separate Session studio. Paper Playground and Orbit remain
selectable. The dashboard uses a smaller stacked-note sculpture so concepts retain priority.

Desktop browser review covered the earlier Pocket/Paper setup screens and the final white/yellow
dashboard. Physical camera/microphone capture, model output quality, UNO Q hardware, and real
mobile-device rendering still need verification. Unit tests validate software behavior, not
those hardware or perceptual claims.
