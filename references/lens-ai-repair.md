# Lens AI Reflection Repair

Use AI only when the lens contains unwanted reflections, dust, scratches, or small defects that cannot be removed cleanly with deterministic editing.

## Boundary Rules

1. Create a separate mask for each lens.
2. Inset the mask 4-8 pixels from the visible lens edge at full resolution.
3. Feather the mask 2-4 pixels.
4. Exclude the frame, bridge, hinges, nose pads, logos, printed text, and temple parts visible through the lens.
5. Keep the source image and the non-generative white-background retouch as references.

## Edit Instruction

Use this instruction with the available image-editing model:

```text
Repair only the masked lens interior. Remove the unwanted reflection, dust, scratch, or blemish while continuing the surrounding lens gradient naturally. Preserve the exact lens tint, transparency, optical density, highlight direction, frame geometry, lens outline, logo, text, and every unmasked pixel. Do not redraw or reshape the glasses. Do not add new reflections.
```

## Composite and QA

Composite only the repaired patch through the feathered lens mask onto the approved white-background retouch.

Reject the patch if it changes lens colour, removes a real temple visible through the lens, blurs the lens edge, alters the bridge or frame thickness, changes a logo, or makes the two lenses unnaturally identical.
