"""Map raw `UnitRole` strings from UniteDescriptor.ndf to canonical UI buckets.

Eugen and WIF use a mix of English, French, abbreviations, and HQ-prefixed
variants for `UnitRole`:

    AA, AT, appui, armor, engineer, howitzer, hq_helo, hq_inf, hq_tank,
    hq_veh, ifv, infantry, mlrs, mortar, reco, sead, supply, transport,
    transport1..5, uav

The UI filter dropdown only shows a small set of canonical buckets. Without
normalisation, picking "plane" matches zero raw values (the raw values are
`sead` and `uav`), picking "artillery" misses `howitzer`/`mlrs`/`mortar`,
"helicopter" misses `hq_helo`, "recon" misses `reco`, and so on.

This module is the single source of truth for that mapping so the Flask API
filter and the SPA's badge/icon code agree.
"""

from __future__ import annotations

# Canonical buckets shown in the UI dropdown.
# "command" overlaps with armor/infantry/helicopter/ifv: an `hq_tank` unit is
# both armor AND command. The UI surfaces command as a separate filter so the
# user can list all leader/HQ units regardless of subtype.
CANONICAL_BUCKETS = (
    "armor", "ifv", "helicopter", "plane", "infantry",
    "artillery", "aa", "recon", "supply", "engineer", "command",
)


def normalize_role(raw: str | None, is_plane: bool = False, is_helo: bool = False) -> str:
    """Return the *primary* canonical bucket for a raw `UnitRole` value.

    A unit may belong to multiple buckets (e.g. ``hq_tank`` is both ``armor``
    and ``command``). This returns the bucket that best describes the unit's
    combat role; use :func:`bucket_matches` to test multi-bucket membership.
    """
    if is_plane:
        return "plane"
    if is_helo:
        return "helicopter"
    if not raw:
        return "unknown"
    r = raw.strip().lower()
    if not r:
        return "unknown"

    # Order matters: more specific HQ + helicopter patterns before generic ones.
    if "helo" in r or "heli" in r:
        return "helicopter"
    if r == "hq_tank" or r == "armor" or "tank" in r:
        return "armor"
    if r in {"howitzer", "mlrs", "mortar"} or r.startswith("art"):
        return "artillery"
    if r == "aa" or r.startswith("sam") or "spaag" in r or "missile" in r or "manpads" in r:
        return "aa"
    if r in {"plane", "jet", "fighter", "bomber", "aircraft", "sead", "uav"}:
        return "plane"
    if r == "reco" or "recon" in r:
        return "recon"
    if r == "ifv" or r.startswith("transport") or r in {"apc", "carrier", "hq_veh"}:
        return "ifv"
    if "engineer" in r or "sapper" in r:
        return "engineer"
    # Infantry catches plain "infantry", "hq_inf", "AT" (anti-tank teams),
    # and the common foot-team patterns. Keep this LATE so vehicle/HQ
    # patterns above win first.
    if (r == "infantry" or r == "at" or r.startswith("hq_inf")
            or "rifles" in r or "chasseur" in r or "commando" in r
            or "scout" in r or r.startswith("inf")):
        return "infantry"
    if r == "supply" or r == "appui" or "truck" in r or "ammo" in r:
        return "supply"
    return "unknown"


def bucket_matches(raw: str | None, target: str, is_plane: bool = False, is_helo: bool = False) -> bool:
    """True if `raw` belongs to the `target` bucket.

    ``target`` is one of :data:`CANONICAL_BUCKETS` or ``"all"`` / empty string.

    Handles multi-bucket membership: ``hq_tank`` matches both ``armor`` and
    ``command``; an unspecified or ``"all"`` target matches everything.
    """
    if not target or target == "all":
        return True
    if target == "command":
        if not raw:
            return False
        r = raw.strip().lower()
        # Any HQ-prefixed role is command. Vanilla/WIF use hq_inf, hq_tank,
        # hq_helo, hq_veh — and just in case Eugen adds a new variant, we
        # match the prefix rather than enumerating.
        return r.startswith("hq_") or r == "hq"
    return normalize_role(raw, is_plane=is_plane, is_helo=is_helo) == target


__all__ = ["CANONICAL_BUCKETS", "normalize_role", "bucket_matches"]
