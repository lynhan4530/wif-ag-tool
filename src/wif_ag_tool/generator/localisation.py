"""Emit PLATOONS.csv rows for combat-group and smart-group tokens.

Full-replacement model: every combat group / smart group in a replica'd deck is a
custom-generated group, so all tokens here are custom tokens.
"""
from __future__ import annotations

from wif_ag_tool import config
from wif_ag_tool.models import Assignment, WifUnit
from wif_ag_tool.generator.token_gen import make_unique_token
from wif_ag_tool.generator.group_generator import (
    sorted_smart_group_items,
    order_smart_groups,
)


def generate_platoons_rows(
    assignments: list[Assignment],
    units: dict[str, WifUnit],
    decks: dict | None = None,
    combat_groups: dict | None = None,
) -> str:
    """Return PLATOONS.csv content: semicolon-separated, double-quoted, no BOM.

    One row per SmartGroup Name, plus one per CombatGroup Name *only when the group does
    not reuse a vanilla combat group* (vanilla combat-group tokens already have loc rows in
    the mod's PLATOONS.csv, so re-emitting them would duplicate/clobber the vanilla name).
    Token generation mirrors ``build_export_blocks``/``group_generator`` so the same
    Assignment produces the same tokens.
    """
    by_deck: dict[str, list[Assignment]] = {}
    for a in assignments:
        by_deck.setdefault(a.deck_name, []).append(a)
    for lst in by_deck.values():
        lst.sort(key=lambda a: (a.order, a.seq))

    existing: set[str] = set()
    written_tokens: set[str] = set()
    rows: list[str] = ['"TOKEN";"REFTEXT"']

    for deck_name, deck_assignments in by_deck.items():
        groups_map: dict[str, list[Assignment]] = {}
        group_order: list[str] = []
        for a in deck_assignments:
            gname = a.group_name or "A"
            if gname not in groups_map:
                groups_map[gname] = []
                group_order.append(gname)
            groups_map[gname].append(a)

        cg_names_map = {}
        if decks is not None and combat_groups and deck_name in decks:
            from wif_ag_tool.generator.group_generator import resolve_all_cg_names
            cg_names_map = resolve_all_cg_names(deck_name, group_order, decks[deck_name].combat_group_list)

        for gname in group_order:
            group_assignments = groups_map[gname]

            # Mirror build_export_blocks: reuse the vanilla combat-group token when the
            # group maps to one. Add it to `existing` either way so the smart-group token
            # sequence stays identical to the generated combat-group blocks.
            vanilla_token = None
            if cg_names_map and combat_groups:
                cg_name = cg_names_map.get(gname)
                v = combat_groups.get(cg_name) if cg_name else None
                vanilla_token = v.token if v else None

            group_token = vanilla_token or make_unique_token(f"cg_{config.MOD_TAG}_{gname}", deck_name, existing)
            existing.add(group_token)
            # Only emit a row for mod-named groups; vanilla combat-group tokens keep their
            # existing loc row in the mod's PLATOONS.csv.
            if vanilla_token is None and group_token not in written_tokens:
                written_tokens.add(group_token)
                rows.append(f'"{group_token}";"{config.MOD_TAG} {gname}"')

            smart_group_items = sorted_smart_group_items(group_assignments)
            aligned_groups = order_smart_groups(smart_group_items, deck_name, gname, existing)

            for smart_token, sg_is_hq, sg_assignments in aligned_groups:
                if not sg_assignments:
                    continue

                sg_name = sg_assignments[0].sub_group

                if sg_name:
                    if sg_name == "HQ":
                        display_name = f"{config.MOD_TAG} — {gname} HQ"
                    elif sg_name == "SPT":
                        display_name = f"{config.MOD_TAG} — {gname} SUPPORT"
                    elif sg_name.isdigit():
                        display_name = f"{config.MOD_TAG} — {gname} PLATOON {sg_name}"
                    else:
                        # Custom platoon name
                        display_name = sg_name
                else:
                    a = sg_assignments[0]
                    unit = units.get(a.unit_id)
                    display_base = _display_name(unit, a.unit_id)
                    seq_label = f" ({a.seq + 1})" if a.seq else ""
                    xp = a.xp_levels[0] if a.xp_levels else 1
                    display_name = f"{config.MOD_TAG} {display_base}{seq_label} XP{xp}"

                if smart_token not in written_tokens:
                    written_tokens.add(smart_token)
                    rows.append(f'"{smart_token}";"{display_name}"')

    return "\n".join(rows) + "\n"


def _display_name(unit: WifUnit | None, unit_id: str) -> str:
    """Cleanest readable name we have for a unit."""
    if config.MOD_UNIT_PREFIX:
        return unit_id.removeprefix(config.MOD_UNIT_PREFIX).replace("_", " ")
    return unit_id.replace("_", " ")


def _get_localized_fallback_name(primary: str, is_hq: bool, count: int, cg_name: str, deck_name: str) -> str:
    """Generate localized platoon names when translation is missing from PLATOONS.csv."""
    deck_lower = deck_name.lower()
    cg_lower = cg_name.lower()

    is_german = any(x in deck_lower for x in ["_rfa_", "_rda_", "_ddr_", "_ger_"])
    is_french = "_fr_" in deck_lower
    is_russian = any(x in deck_lower for x in ["_sov_", "_rus_"])

    is_artillery = any(x in cg_lower for x in ["art", "artillerie", "bty", "bataillon_artillerie"])

    if is_german:
        if is_hq:
            return "STAB"
        else:
            if is_artillery:
                return f"{count}. BATTERIE"
            elif primary == "RECON":
                return f"{count}. AUFKLÄRUNGSZUG"
            elif primary == "TANK":
                return f"{count}. PANZERZUG"
            elif primary == "ENGINEER":
                return f"{count}. PIONIERZUG"
            elif primary == "AA":
                return f"{count}. FLUGABWEHRZUG"
            elif primary == "LOGISTICS":
                return "NACHSCHUBGRUPPE" if count == 1 else f"NACHSCHUBGRUPPE {count}"
            elif primary == "RIFLE":
                return f"{count}. INFANTERIEZUG"
            elif primary == "SUPPORT":
                return "UNTERSTÜTZUNGSGRUPPE" if count == 1 else f"UNTERSTÜTZUNGSGRUPPE {count}"
            elif primary == "HELI":
                return f"{count}. HUBSCHRAUBERZUG"
            else:
                return f"{count}. ZUG"

    elif is_french:
        def _fr_ord(n: int) -> str:
            return "1ère" if n == 1 else f"{n}e"

        if is_hq:
            return "PELOTON DE COMMANDEMENT" if is_artillery else "QG"
        else:
            if is_artillery:
                return f"{_fr_ord(count)} BATTERIE"
            elif primary == "RECON":
                return f"{_fr_ord(count)} PELOTON RECON"
            elif primary == "TANK":
                return f"{_fr_ord(count)} PELOTON DE CHARS"
            elif primary == "ENGINEER":
                return f"{_fr_ord(count)} SECTION DU GENIE"
            elif primary == "AA":
                return f"{_fr_ord(count)} SECTION SOL-AIR"
            elif primary == "LOGISTICS":
                return "GROUPE LOGISTIQUE" if count == 1 else f"GROUPE LOGISTIQUE {count}"
            elif primary == "RIFLE":
                return f"{_fr_ord(count)} SECTION D'INFANTERIE"
            elif primary == "SUPPORT":
                return "GROUPE D'APPUI" if count == 1 else f"GROUPE D'APPUI {count}"
            elif primary == "HELI":
                return f"{_fr_ord(count)} ESCADRILLE D'HELICOPTERES"
            else:
                return f"{_fr_ord(count)} SECTION"

    elif is_russian:
        if is_hq:
            return "SHTAB"
        else:
            if is_artillery:
                return f"{count}-YA BATAREYA"
            elif primary == "RECON":
                return f"{count}-Y VZVOD RAZVEDKI"
            elif primary == "TANK":
                return f"{count}-Y TANKOVYY VZVOD"
            elif primary == "ENGINEER":
                return f"{count}-Y SAPERNYY VZVOD"
            elif primary == "AA":
                return f"{count}-Y ZENITNYY VZVOD"
            elif primary == "LOGISTICS":
                return "VZVOD OBESPECHENIYA" if count == 1 else f"VZVOD OBESPECHENIYA {count}"
            elif primary == "RIFLE":
                return f"{count}-Y MOTOSTRELKOVYY VZVOD"
            elif primary == "SUPPORT":
                return "GRUPPA PODDERZHKI" if count == 1 else f"GRUPPA PODDERZHKI {count}"
            elif primary == "HELI":
                return f"{count}-Y VZVOD VERTOLETOV"
            else:
                return f"{count}-Y VZVOD"

    else:
        # Default English
        def _ordinal(n: int) -> str:
            if 11 <= (n % 100) <= 13:
                return f"{n}TH"
            return f"{n}" + {1: 'ST', 2: 'ND', 3: 'RD'}.get(n % 10, 'TH')

        is_cavalry = any(x in cg_lower or x in deck_lower for x in ["acr", "cav", "cavalry"])

        if is_hq:
            if is_cavalry:
                return "TROOP HQ"
            elif is_artillery:
                return "BATTERY HQ"
            else:
                return "COMPANY HQ"
        else:
            if is_cavalry:
                if primary == "ENGINEER":
                    return f"{count}/58ENG"
                elif primary == "AA":
                    return "AIR DEFENSE PLATO"
                elif primary == "LOGISTICS":
                    return "LOGISTICS GROUP" if count == 1 else f"LOGISTICS GROUP {count}"
                elif primary == "RECON":
                    return "RECON GROUP" if count == 1 else f"RECON GROUP {count}"
                elif primary == "SUPPORT":
                    return "SUPPORT GROUP" if count == 1 else f"SUPPORT GROUP {count}"
                elif primary == "TANK":
                    return f"{_ordinal(count)} TANK PLATOON"
                elif primary == "RIFLE":
                    return f"{_ordinal(count)} RIFLE PLATOON"
                elif primary == "HELI":
                    return f"{_ordinal(count)} HELI PLATOON"
                else:
                    return f"{_ordinal(count)} PLATOON"
            else:
                if primary == "RECON":
                    return f"{_ordinal(count)} RECON PLATOON"
                elif primary == "TANK":
                    return f"{_ordinal(count)} TANK PLATOON"
                elif primary == "ENGINEER":
                    return f"{_ordinal(count)} ENGINEER PLATOON"
                elif primary == "AA":
                    return f"{_ordinal(count)} AIR DEFENSE PLATOON"
                elif primary == "LOGISTICS":
                    return f"{_ordinal(count)} SUPPLY PLATOON"
                elif primary == "RIFLE":
                    return f"{_ordinal(count)} RIFLE PLATOON"
                elif primary == "SUPPORT":
                    return "SUPPORT GROUP" if count == 1 else f"SUPPORT GROUP {count}"
                elif primary == "HELI":
                    return f"{_ordinal(count)} HELI PLATOON"
                else:
                    return f"{_ordinal(count)} PLATOON"
