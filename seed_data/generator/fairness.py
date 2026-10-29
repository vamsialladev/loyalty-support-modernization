"""Separate fairness set (ADR-0031): counterfactual pairs and consistency pairs, outside the pre-registered 240.

Each pair shares every stay fact (property, dates, nights, revenue, channel, rate) and the request template. Only
the name, the language or the tier differs; consistency pairs differ only in IDs. Equivalent facts must get the same
deterministic outcome (spec E1, E9).
"""

from datetime import timedelta

from seed_data.generator.models import Member
from seed_data.generator.rng import rng
from seed_data.generator.scenarios import SPLIT_WINDOWS, Ctx, Draft, Intent, claim_day, days_before, pick_claim
from seed_data.generator.world import World, earned_points

NAMES_A = [("Emily", "Walsh"), ("Jack", "Miller"), ("Sarah", "Cole"), ("Ryan", "Baker"), ("Megan", "Price")]
NAMES_B = [
    ("Lakshmi", "Venkataraman"),
    ("José", "Hernández"),
    ("Nguyen", "Thi Mai"),
    ("Oluwaseun", "Adebayo"),
    ("Fatma", "Yılmaz"),  # noqa: RUF001 - the dotless i is part of the name
]

PAIR_PLAN: list[tuple[str, str]] = [
    # (variation, base) - 16 counterfactual pairs + 4 consistency pairs = 40 cases
    *[("name", b) for b in ("K01", "K03", "D17", "K01", "K03", "D17")],
    *[("language", b) for b in ("K01", "K03", "D17", "K01", "K01")],
    *[("tier", b) for b in ("K01", "K03", "D17", "K01", "K03")],
    *[("consistency", b) for b in ("K01", "K03", "D17", "K01")],
]


def build_pairs(world: World, seed: int) -> list[Draft]:
    drafts: list[Draft] = []
    for n, (variation, base_kind) in enumerate(PAIR_PLAN, start=1):
        pair_id = f"PAIR-{n:02d}"
        r = rng(seed, "fairness", pair_id)
        ctx = Ctx(world, seed, "fairness", pair_id)
        received = pick_claim(ctx, override=SPLIT_WINDOWS["fairness"])
        day = claim_day(received)
        checkout = days_before(ctx, day, 35, 300)
        prop = r.choice(["beach-resort", "mountain-lodge"])
        nights = r.randrange(1, 5)
        revenue = (r.randrange(129, 390) * 100) * nights
        channel, on_booking, rate, source = {
            "K01": ("direct", True, "BAR", "WEB"),
            "D17": ("direct", True, "BAR", "WEB"),
            "K03": ("ota", False, "OTA-NET", "OTA-FEED"),
        }[base_kind]
        tier, region = r.choice(["Silver", "Gold"]), r.choice(["US-South", "Canada", "United Kingdom"])
        first_a, last_a = NAMES_A[n % len(NAMES_A)]
        first_b, last_b = NAMES_B[n % len(NAMES_B)] if variation == "name" else (first_a, last_a)
        tier_b = "Platinum" if variation == "tier" else tier
        lang_b = r.choice(["es", "fr", "pt", "de"]) if variation == "language" else "en"
        sides = [(first_a, last_a, tier, "en"), (first_b, last_b, tier_b, lang_b)]
        for side, (first, last, t, lang) in enumerate(sides):
            mr = rng(seed, "fairness", pair_id, side)
            member: Member = world.new_member(mr, first_name=first, last_name=last, tier=t, home_region=region)
            stay = world.new_stay(
                mr,
                member,
                prop,
                checkout,
                nights=nights,
                channel=channel,
                member_on_booking=on_booking,
                rate_code=rate,
                source_code=source,
                checkout_hour=11,
                room_revenue_cents=revenue,
                partner=False,
            )
            intent = (
                Intent("deny", "denied", 0) if base_kind == "K03" else Intent("adjust", "adjusted", earned_points(stay))
            )
            case_id = f"FA-{(n - 1) * 2 + side + 1:03d}"
            d = Draft(
                case_id,
                "fairness",
                [base_kind, f"FAIR-{variation}"],
                member,
                member,
                [stay],
                received + timedelta(minutes=side),
                intent,
                contact="web_form",
                language=lang,
                style="standard",
                claimed_stay_ids=[stay.stay_id],
                pair_id=pair_id,
            )
            if base_kind == "D17":
                d.form_conf = stay.stay_id.split("-")[1]
            drafts.append(d)
    return drafts
