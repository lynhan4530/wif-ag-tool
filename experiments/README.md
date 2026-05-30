# experiments/

Throwaway, reversible probes for answering questions the NDF compiler can't —
i.e. "does the *running game* accept this?" Nothing here imports or modifies the
`wif_ag_tool` source, and nothing here is wired into the package or the test suite.

## `ag_minimal_deck_test.py` — does AG accept a stripped-down deck?

**Question it answers:** before we rewrite the export to a "replica fully defines the
deck" model (where you balance by *deleting* combat groups), we need to know whether
WARNO Army General tolerates a drastically reduced deck at runtime, or whether the
campaign assumes a minimum structure (an HQ, a minimum pack count, …).

**How it stays safe:** it trims one deck's `DeckCombatGroupList` to the first N combat
groups and **leaves `DeckPackList` untouched**, so every `(start_index, count)` tuple
still points at valid slots — no re-indexing, no pawn-click out-of-bounds risk. The
only variable under test is "fewer combat groups." It backs up `StrategicDecks.ndf`
before writing and can fully restore it.

It edits the mod's already-built `StrategicDecks.ndf` directly and **does not run the
tool's export pipeline**, so it is unaffected by any in-progress code changes.

### Steps

```powershell
# point this at your mod's Decks folder
$decks = "G:\...\Mods\<YourMod>\GameData\Generated\Gameplay\Decks"

# 1. find a deck with several combat groups
py experiments/ag_minimal_deck_test.py --decks-dir $decks --list --nation US

# 2. preview the trim (no files touched)
py experiments/ag_minimal_deck_test.py --decks-dir $decks --deck Descriptor_Deck_pion_US_11ACR_4 --keep 1

# 3. apply (backs up StrategicDecks.ndf first)
py experiments/ag_minimal_deck_test.py --decks-dir $decks --deck Descriptor_Deck_pion_US_11ACR_4 --keep 1 --apply

# 4. build + test in-game
#    - run GenerateMod.bat in the mod folder (let it finish; ignore the PAUSE)
#    - launch the AG campaign, open the trimmed deck
#    - click the pawn / recruit, then start and resolve a battle

# 5. undo when done
py experiments/ag_minimal_deck_test.py --decks-dir $decks --restore
```

### Reading the result

- **Deck opens, recruits, battles fine** → deleting combat groups is structurally safe.
  Full-replacement export is viable; proceed with the rewrite.
- **Crash / unusable deck / empty recruitment** → AG needs more structure than we
  assumed. Note exactly what broke (deck won't open? recruit crashes? battle won't
  start?) — that tells us the real constraint to guard for in the export (e.g. "always
  keep an HQ combat group", "minimum N packs").
