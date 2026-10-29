"""The synthetic world: members, stay records, ledger and posting queue (what the customer systems hold).

Background population first, then each scenario plants its own records. All IDs come from seeded pools so they are
unique and stable. Names are invented from small lists in this file; nothing comes from real records.
"""

import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from seed_data.generator.models import LedgerEntry, Member, PostingQueueItem, StayRecord
from seed_data.generator.rng import rng
from seed_data.generator.timeutil import iso, to_utc

CUSTOMER = "hg-demo"
PROPERTIES = {"beach-resort": ("Beach Resort", "BR"), "mountain-lodge": ("Mountain Lodge", "ML")}
WORLD_START = date(2025, 1, 1)
WORLD_END = date(2026, 10, 31)

FIRST_NAMES = [
    "Elena",
    "Marcus",
    "Priya",
    "Daniel",
    "Sofia",
    "James",
    "Aisha",
    "Thomas",
    "Mei",
    "Lucas",
    "Fatima",
    "Oliver",
    "Grace",
    "Mateo",
    "Hannah",
    "Kenji",
    "Olivia",
    "Samuel",
    "Amara",
    "Noah",
    "Isabel",
    "Ethan",
    "Leila",
    "Henry",
    "Chloe",
    "Arjun",
    "Zoe",
    "Diego",
    "Nora",
    "Felix",
    "Ana",
    "Victor",
    "Ruth",
    "Omar",
    "Clara",
    "Jonah",
    "Elizabeth",
    "Robert",
    "William",
    "Katherine",
    "Michael",
    "Jennifer",
    "Alexander",
    "Margaret",
]
LAST_NAMES = [
    "Marsh",
    "Okafor",
    "Lindqvist",
    "Hernandez",
    "Novak",
    "Patel",
    "Brennan",
    "Castillo",
    "Yamada",
    "Fischer",
    "Mensah",
    "Romano",
    "Kowalski",
    "Dubois",
    "Sato",
    "Abara",
    "Whitfield",
    "Moreau",
    "Haddad",
    "Larsen",
    "Quinn",
    "Ortega",
    "Nakamura",
    "Schulz",
    "Adeyemi",
    "Byrne",
    "Costa",
    "Ivanova",
    "Khan",
    "Laurent",
    "Mbeki",
    "Park",
]
NICKNAMES = {
    "Elizabeth": "Liz",
    "Robert": "Bob",
    "William": "Bill",
    "Katherine": "Kate",
    "Michael": "Mike",
    "Jennifer": "Jen",
    "Alexander": "Alex",
    "Margaret": "Peggy",
}
REGIONS = [
    ("US-South", 22),
    ("US-Northeast", 18),
    ("US-Midwest", 12),
    ("US-West", 12),
    ("Canada", 8),
    ("Mexico", 6),
    ("United Kingdom", 6),
    ("Germany", 5),
    ("Brazil", 4),
    ("France", 4),
    ("Spain", 3),
]
TIERS = [("Member", 10), ("Silver", 4), ("Gold", 3), ("Platinum", 1)]
CHANNELS = [("direct", 45), ("phone", 10), ("ota", 30), ("travel_agent", 15)]
SOURCE_FOR = {"direct": ["WEB", "APP", "FD"], "phone": ["CALL"], "ota": ["OTA-FEED"], "travel_agent": ["GDS-TA"]}
RATE_FOR = {"direct": ["BAR", "PKG", "ADV"], "phone": ["BAR", "PKG"], "ota": ["OTA-NET"], "travel_agent": ["TA-STD"]}


def weighted(r: random.Random, options: list[tuple[str, int]]) -> str:
    return r.choices([o for o, _ in options], weights=[w for _, w in options])[0]


class IdPool:
    """Unique random IDs of the form `<prefix><digits>`, drawn without replacement."""

    def __init__(self, r: random.Random, prefix: str, digits: int, low: int | None = None) -> None:
        self.r, self.prefix, self.digits = r, prefix, digits
        self.low = low if low is not None else 10 ** (digits - 1)
        self.used: set[str] = set()

    def take(self) -> str:
        for _ in range(10_000):
            candidate = f"{self.prefix}{self.r.randrange(self.low, 10**self.digits)}"
            if candidate not in self.used:
                self.used.add(candidate)
                return candidate
        raise RuntimeError(f"ID pool {self.prefix} exhausted")


@dataclass
class World:
    seed: int
    stay_digits: int = 4
    members: list[Member] = field(default_factory=list)
    stays: list[StayRecord] = field(default_factory=list)
    ledger: list[LedgerEntry] = field(default_factory=list)
    queue: list[PostingQueueItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.member_ids = IdPool(rng(self.seed, "ids", "member"), "GR-", 5)
        self.stay_ids = {
            p: IdPool(rng(self.seed, "ids", p), f"{prefix}-", self.stay_digits) for p, (_, prefix) in PROPERTIES.items()
        }
        self.partner_ids = IdPool(rng(self.seed, "ids", "partner"), "TRV-", 8)
        self._entry_seq = 0
        self._record_seq = 0
        self._queue_seq = 0
        self._emails: set[str] = set()

    # ----- IDs -----
    def next_entry_id(self) -> str:
        self._entry_seq += 1
        return f"L-{self._entry_seq:07d}"

    def next_record_id(self) -> str:
        self._record_seq += 1
        return f"R-{self._record_seq:07d}"

    def next_queue_id(self) -> str:
        self._queue_seq += 1
        return f"Q-{self._queue_seq:06d}"

    # ----- records -----
    def new_member(self, r: random.Random, **overrides: object) -> Member:
        first = str(overrides.pop("first_name", r.choice(FIRST_NAMES)))
        last = str(overrides.pop("last_name", r.choice(LAST_NAMES)))
        number = str(overrides.pop("member_number", self.member_ids.take()))
        email = str(overrides.pop("email", self._unique_email(r, first, last)))
        values: dict[str, object] = {
            "member_number": number,
            "customer_id": CUSTOMER,
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": f"+1 {r.randrange(201, 989)} 555 {r.randrange(100, 199):04d}",
            "date_of_birth": date(r.randrange(1950, 2003), r.randrange(1, 13), r.randrange(1, 29)).isoformat(),
            "tier": weighted(r, TIERS),
            "home_region": weighted(r, REGIONS),
            "enrolled_on": (date(2018, 1, 1) + timedelta(days=r.randrange(0, 2400))).isoformat(),
            "status": "active",
            "merged_into": None,
        }
        values.update(overrides)
        member = Member.model_validate(values)
        self.members.append(member)
        return member

    def _unique_email(self, r: random.Random, first: str, last: str) -> str:
        domain = r.choice(["example.com", "mail.test"])
        base = f"{first}.{last}".lower()
        email, n = f"{base}@{domain}", 2
        while email in self._emails:
            email, n = f"{base}{n}@{domain}", n + 1
        self._emails.add(email)
        return email

    def new_stay(
        self,
        r: random.Random,
        member: Member | None,
        prop: str,
        checkout: date,
        *,
        nights: int | None = None,
        channel: str | None = "direct",
        member_on_booking: bool = True,
        status: str = "checked_out",
        checkout_hour: int | None = None,
        rate_code: str | None = None,
        source_code: str | None = None,
        stay_id: str | None = None,
        room_revenue_cents: int | None = None,
        guest_name: str | None = None,
        partner: bool | None = None,
    ) -> StayRecord:
        nights = nights or r.randrange(1, 6)
        nightly = r.randrange(129, 390) * 100 + r.choice([0, 0, 99])
        ch = channel
        if source_code is None:
            source_code = r.choice(SOURCE_FOR[ch]) if ch else "LEGACY-IMPORT"
        if rate_code is None:
            rate_code = r.choice(RATE_FOR[ch]) if ch else "BAR"
        hour = checkout_hour if checkout_hour is not None else r.choice([9, 10, 10, 11, 11, 11, 12, 13])
        minute = r.choice([0, 5, 12, 20, 30, 41, 55]) if hour < 20 else r.choice([5, 25, 40])
        has_partner = partner if partner is not None else ch == "ota"
        revenue = room_revenue_cents if room_revenue_cents is not None else nightly * nights
        record = StayRecord(
            record_id=self.next_record_id(),
            stay_id=stay_id or self.stay_ids[prop].take(),
            customer_id=CUSTOMER,
            property=prop,  # type: ignore[arg-type]
            member_number=member.member_number if member and member_on_booking else None,
            member_on_booking=bool(member and member_on_booking),
            arrival_date=(checkout - timedelta(days=nights)).isoformat(),
            nights=nights,
            checkout_at_utc=iso(to_utc(checkout, hour, minute)),
            status=status,  # type: ignore[arg-type]
            channel=ch,  # type: ignore[arg-type]
            source_code=source_code,
            rate_code=rate_code,
            partner_confirmation=self.partner_ids.take() if has_partner else None,
            room_revenue_cents=revenue,
            taxes_cents=round(revenue * 0.12),
            fees_cents=r.choice([0, 0, 2500, 3500]) * nights,
            guest_name=guest_name or (f"{member.first_name} {member.last_name}" if member else "Walk-in guest"),
        )
        self.stays.append(record)
        return record

    def post(
        self,
        member_number: str,
        stay_id: str | None,
        points: int,
        at: datetime,
        kind: str = "posting",
        reverses: str | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            entry_id=self.next_entry_id(),
            member_number=member_number,
            stay_id=stay_id,
            kind=kind,  # type: ignore[arg-type]
            points=points,
            posted_at_utc=iso(at),
            reverses_entry_id=reverses,
        )
        self.ledger.append(entry)
        return entry

    def queue_posting(
        self, member_number: str, stay_id: str, points: int, queued: datetime, lands: datetime
    ) -> PostingQueueItem:
        entry = self.post(member_number, stay_id, points, lands)
        item = PostingQueueItem(
            item_id=self.next_queue_id(),
            member_number=member_number,
            stay_id=stay_id,
            points=points,
            queued_at_utc=iso(queued),
            expected_post_at_utc=iso(lands),
            posts_entry_id=entry.entry_id,
        )
        self.queue.append(item)
        return item


def earned_points(stay: StayRecord) -> int:
    """Guest Rewards: 10 points per US dollar of room revenue, rounded down (integer cents avoid float error)."""
    return stay.room_revenue_cents // 10


def checkout_dt(stay: StayRecord) -> datetime:
    return parse_ts(stay.checkout_at_utc)


def parse_ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def build_background(world: World, scale: float) -> None:
    """Background members and stays: context the arms search through. Postings follow the policy in force."""
    r = rng(world.seed, "world", "background")
    n_members = max(50, round(3000 * scale))
    span = (WORLD_END - WORLD_START).days
    for _ in range(n_members):
        member = world.new_member(r)
        for _ in range(r.choice([1, 1, 2, 2, 3, 4])):
            prop = r.choice(list(PROPERTIES))
            checkout = WORLD_START + timedelta(days=r.randrange(5, span))
            channel = weighted(r, CHANNELS)
            on_booking = channel != "ota" or r.random() < 0.6
            corp = channel == "travel_agent" and r.random() < 0.1
            stay = world.new_stay(
                r,
                member,
                prop,
                checkout,
                channel=channel,
                member_on_booking=on_booking,
                rate_code=f"CORP{r.randrange(1, 13):02d}" if corp else None,
            )
            if _background_eligible(stay, checkout, corp):
                lag = timedelta(days=r.randrange(1, 8), hours=r.randrange(0, 20))
                world.post(member.member_number, stay.stay_id, earned_points(stay), checkout_dt(stay) + lag)


def _background_eligible(stay: StayRecord, checkout: date, corp: bool) -> bool:
    v2 = checkout >= date(2026, 7, 1)
    if stay.channel in ("direct", "phone"):
        return stay.member_number is not None
    if stay.channel == "ota":
        return v2 and stay.member_on_booking
    return v2 and corp
