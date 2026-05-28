# Postmortem — Army General Pawn-Click Crash (Resolved 2026-05-28)

> **Status: RESOLVED.** Verified in-game on `Descriptor_Deck_pion_US_11ACR_1` —
> TROOP HQ + all platoons render with correct ×count badges (Bradleys ×6,
> Abrams ×4, Humvees ×2), Combat Battalion at 100%. This file is kept as
> historical context; the live invariants now live in
> [NDF_REFERENCE.md §4](NDF_REFERENCE.md) and [CLAUDE.md](CLAUDE.md).

## 1. Symptom

Clicking the campaign pawn (`US_11ACR_1`) in WARNO's Army General mode crashed
the game during pawn composition UI build — a hard null/out-of-bounds in the
engine's `DeckPackList` walk.

## 2. Root cause — two bugs, not one

WARNO ships **two distinct schemas** for "how many recruitable copies of this
pack":

- **Skirmish / MP** (`DeckPacks.ndf`): `DeckPackDescriptor` carries `Number = N`,
  referenced once in the deck.
- **Army General campaign** (`StrategicPacks.ndf`): no `Number` field. Count is
  encoded by **duplicating the `~/Descriptor_StrategicPack_*` ref N times
  consecutively** in `DeckPackList`. The `(start_index, count)` tuple in
  `TDeckSmartGroupDescriptor.PackIndexUnitNumberList` reads exactly `count`
  consecutive slots starting at `start_index`.

This generator was emitting **one** pack ref per assignment but stamping
`(start, count)` tuples with `count = a.count` (e.g. `count=6` for a 6-Bradley
platoon). The engine read `count` slots from `DeckPackList`, found only one
matching entry plus `count - 1` slots from adjacent groups; at the end of the
deck (HQ resolution) the read went out of bounds → crash.

After fixing pack duplication, a **second bug** surfaced (this one not in the
original handoff): the per-XP-level offset inside a single SmartGroup also
needed to scale by `count`, otherwise two-XP assignments produced overlapping
windows like `(s, 6) (s+1, 6)` instead of `(s, 6) (s+6, 6)`.

## 3. Fix (committed)

| File | Change |
|------|--------|
| `src/wif_ag_tool/pipeline.py` | Wrap pack-ref append in `for _ in range(a.count):` so each ref gets duplicated `count` times in `DeckPackList`. |
| `src/wif_ag_tool/web/api.py` | Mirror the same change in the direct-export endpoint. |
| `src/wif_ag_tool/generator/group_generator.py` | `curr += len(xp_levels) * count` (inter-assignment cursor) **and** `start_idx + offset * count` (per-XP offset). |
| `src/wif_ag_tool/pipeline.py` | New `_assert_pack_index_invariant()` raises if `sum(SmartGroup counts) != DeckPackList growth` per deck — defense-in-depth so this bug class can never silently recur. |

## 4. Regression coverage

Live tests (run `pytest tests/ -v`):
- `tests/test_generator.py::test_gen_combat_group_count_emits_consecutive_run_tuple`
- `tests/test_generator.py::test_gen_combat_group_multi_xp_count_offsets_by_count`
- `tests/test_generator.py::test_grouped_smart_group_count_accumulates_across_assignments`
- `tests/test_integration.py::test_export_from_replicas_count_duplicates_pack_refs`
- `tests/test_integration.py::test_pack_index_invariant_raises_on_mismatch`

## 5. Lessons (for next agent)

1. **`pytest` green ≠ feature works.** The previous handoff would have passed
   tests but still crashed in-game. The only real success signal for NDF-generation
   changes is **📥 Export Mod → ⚡ Build Mod → click the pawn in WARNO**. Don't
   sign off until the user reports the pawn-click test passes.
2. **Trust the vanilla files over any prior handoff.** Reading
   `G:\Warno_mod\vanilla_recon\GameData\Generated\Gameplay\Decks\StrategicCombatGroups.ndf`
   makes the `(start_index, count)` semantics unambiguous — the tuple sums match
   the deck pack list slot counts exactly. Always cross-reference vanilla NDFs
   before accepting a diagnosis.
3. **Eugen has two pack schemas.** `DeckPacks.ndf` (MP) and `StrategicPacks.ndf`
   (AG) look almost identical at a glance but encode count differently. Don't
   assume features from one carry over.
