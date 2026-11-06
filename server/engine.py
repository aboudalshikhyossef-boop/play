"""Authoritative match engine for CHAOS FAMILY BATTLE.

All actions, balances, deadlines, and reveals are resolved on the host.
Clients submit intents only. The engine persists every state transition in SQLite.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
import uuid
from contextlib import closing
from typing import Any, Dict, List, Optional

from .challenges import (
    CHALLENGE_REWARD,
    CHALLENGE_SECONDS,
    DUEL_WIN_REWARD,
    challenge_fingerprint,
    generate_challenge,
    ROUND_CHALLENGES,
)
from .store import GameStore, InvalidInput, NotFound, RoomNotOpen, StoreError, _normalize_code

MIN_PLAYERS = 3
MAX_PLAYERS = 4
TOTAL_ROUNDS = 8
ACTION_SECONDS = 60
REVENGE_SECONDS = 15
RESULT_SECONDS = 10
INITIAL_COINS = 10
MAX_STEAL = 2
GUARD_COST = 1
MAX_WAGER = 3
REVENGE_CHARGES = 2
REVENGE_AMOUNT = 1
EVENT_SECONDS = 20
INTERACTIVE_EVENT_IDS = frozenset((
    "black_box", "bomb", "secret_auction", "court",
))

# Round one deliberately uses the base rules as a gentle tutorial. Every later
# round receives one server-selected event, persisted so all devices see the
# same rule and reconnecting players cannot get a different card.
ROUND_EVENTS = {
    "opening": {
        "id": "opening",
        "title": "الجولة الأولى — تعرّف على اللعبة",
        "description": "هذه جولة بالقواعد الأساسية: سرقة حتى عملتين، حماية تكلف عملة، ورهان 50/50.",
        "effect": "تعلّم الحركات أولًا؛ بطاقات الفوضى تبدأ من الجولة الثانية.",
    },
    "market_rush": {
        "id": "market_rush",
        "title": "سوق السرقة المفتوح",
        "description": "كل سرقة ناجحة تستطيع نقل حتى 3 عملات بدل عملتين من رصيد اللاعب المستهدف.",
        "effect": "اختر هدفك بعناية؛ الحماية ما زالت توقف السرقة بالكامل.",
    },
    "free_guard": {
        "id": "free_guard",
        "title": "درع مجاني للجميع",
        "description": "الحماية لا تكلف أي عملة في هذه الجولة، حتى لو كان رصيدك صفرًا.",
        "effect": "تستطيع حماية نفسك دون دفع؛ لكنك لا تربح عملات لمجرد الحماية.",
    },
    "bounty": {
        "id": "bounty",
        "title": "مكافأة على الجرأة",
        "description": "كل سرقة ناجحة تمنح السارق عملة إضافية من بنك اللعبة فوق العملات التي نقلها.",
        "effect": "السرقة الناجحة تعطي السارق مكافأة +1، ولا تُخصم هذه المكافأة من الضحية.",
    },
    "double_revenge": {
        "id": "double_revenge",
        "title": "ردّ الصاع مضاعفًا",
        "description": "من تعرّض لسرقة ناجحة يستطيع استرداد حتى عملتين من السارق بدل عملة واحدة.",
        "effect": "تستهلك ضربة الانتقام فرصة واحدة فقط من فرصك المحدودة.",
    },
    "high_stakes": {
        "id": "high_stakes",
        "title": "رهان عالي المخاطرة",
        "description": "احتمال الفوز يبقى 50/50؛ عند الفوز تربح صافي ضعفي مبلغ الرهان، وعند الخسارة تفقد المبلغ نفسه.",
        "effect": "راهن بقدر ما تتحمل خسارته؛ أقصى رهان ما زال 3 عملات.",
    },
    "black_box": {
        "id": "black_box",
        "title": "الصندوق الأسود",
        "description": "اختر صندوقًا واحدًا من ثلاثة دون معرفة محتواه. قد تحصل على عملتين، أو حماية مجانية، أو تخسر عملة واحدة.",
        "effect": "كل لاعب يختار سرًا؛ تكشف محتويات الصناديق للجميع بعد انتهاء الاختيارات.",
    },
    "bomb": {
        "id": "bomb",
        "title": "القنبلة المتنقلة",
        "description": "تبدأ القنبلة مع لاعب محدد. اختر الاحتفاظ بها أو تمريرها إلى لاعب آخر. تستمر حتى يحتفظ بها شخص؛ حاملها الأخير يخسر حتى عملتين.",
        "effect": "قرارات التمرير سرية ومتزامنة. إذا عادت القنبلة إلى لاعب مرّ عليها سابقًا تنفجر عند آخر حامل.",
    },
    "temporary_king": {
        "id": "temporary_king",
        "title": "الملك المؤقت",
        "description": "يتوّج الخادم صاحب أقل رصيد. يحصل الملك على عملة مجانية، وحماية مجانية، ويمكنه محاولة سرقة حتى 3 عملات في هذه الجولة.",
        "effect": "اللقب لجولة واحدة فقط، ويتغير اختيار الملك حسب الأرصدة مع تدوير كسر التعادل.",
    },
    "secret_auction": {
        "id": "secret_auction",
        "title": "المزاد السري",
        "description": "قدّم عرضًا سريًا من صفر إلى 3 عملات. أعلى عرض يفوز بحماية مجانية لهذه الجولة ويدفع عرضه إلى بنك اللعبة.",
        "effect": "عند التعادل يُحسم الفوز بأولوية مقعد تتغير كل جولة. إذا كانت كل العروض صفرًا فلا فائز.",
    },
    "court": {
        "id": "court",
        "title": "المحكمة",
        "description": "صوّت سرًا على لاعب آخر أو امتنع. إذا حصل لاعب على أغلبية مطلقة من أصوات جميع اللاعبين، يدفع عملة واحدة إلى بنك اللعبة.",
        "effect": "لا يمكنك التصويت لنفسك. التعادل أو غياب الأغلبية يعني إسقاط القضية.",
    },
}


class MatchNotFound(NotFound):
    code = "match_not_found"


class MatchNotReady(StoreError):
    status = 409
    code = "match_not_ready"


class MatchNotActive(StoreError):
    status = 409
    code = "match_not_active"


class ActionLocked(StoreError):
    status = 409
    code = "action_locked"


class MatchEngine:
    """Transactional match state machine backed by the shared GameStore database."""

    def __init__(self, store: GameStore) -> None:
        self.store = store
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        return self.store._connect()

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS matches (
                    id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                    status TEXT NOT NULL CHECK (status IN ('active', 'finished')),
                    phase TEXT NOT NULL CHECK (phase IN ('actions', 'revenge', 'result', 'finished')),
                    round_no INTEGER NOT NULL,
                    total_rounds INTEGER NOT NULL,
                    deadline_at INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_match_per_room
                ON matches(room_id) WHERE status = 'active';

                CREATE INDEX IF NOT EXISTS idx_matches_room_created
                ON matches(room_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS match_players (
                    match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                    player_id TEXT NOT NULL,
                    seat INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    color TEXT NOT NULL,
                    avatar TEXT NOT NULL,
                    coins INTEGER NOT NULL DEFAULT 10 CHECK (coins >= 0),
                    revenge_charges INTEGER NOT NULL DEFAULT 2 CHECK (revenge_charges >= 0),
                    coins_stolen INTEGER NOT NULL DEFAULT 0,
                    successful_guards INTEGER NOT NULL DEFAULT 0,
                    revenge_used INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (match_id, player_id),
                    UNIQUE (match_id, seat)
                );

                CREATE TABLE IF NOT EXISTS match_rounds (
                    match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                    round_no INTEGER NOT NULL,
                    public_result_json TEXT,
                    event_json TEXT,
                    challenge_json TEXT,
                    challenge_result_json TEXT,
                    created_at INTEGER NOT NULL,
                    settled_at INTEGER,
                    PRIMARY KEY (match_id, round_no)
                );

                CREATE TABLE IF NOT EXISTS round_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL,
                    round_no INTEGER NOT NULL,
                    player_id TEXT NOT NULL,
                    action_type TEXT NOT NULL CHECK (action_type IN ('steal', 'guard', 'wager', 'pass')),
                    target_player_id TEXT,
                    amount INTEGER NOT NULL DEFAULT 0,
                    request_id TEXT NOT NULL,
                    submitted_at INTEGER NOT NULL,
                    outcome_json TEXT,
                    UNIQUE (match_id, round_no, player_id),
                    UNIQUE (match_id, player_id, request_id),
                    FOREIGN KEY (match_id, player_id) REFERENCES match_players(match_id, player_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS revenge_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL,
                    round_no INTEGER NOT NULL,
                    player_id TEXT NOT NULL,
                    target_player_id TEXT,
                    action_type TEXT NOT NULL CHECK (action_type IN ('counterstrike', 'pass')),
                    request_id TEXT NOT NULL,
                    submitted_at INTEGER NOT NULL,
                    outcome_json TEXT,
                    UNIQUE (match_id, round_no, player_id),
                    UNIQUE (match_id, player_id, request_id),
                    FOREIGN KEY (match_id, player_id) REFERENCES match_players(match_id, player_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS challenge_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL,
                    round_no INTEGER NOT NULL,
                    player_id TEXT NOT NULL,
                    answer_index INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    submitted_at INTEGER NOT NULL,
                    UNIQUE (match_id, round_no, player_id),
                    UNIQUE (match_id, player_id, request_id),
                    FOREIGN KEY (match_id, player_id) REFERENCES match_players(match_id, player_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS event_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL,
                    round_no INTEGER NOT NULL,
                    player_id TEXT NOT NULL,
                    choice_type TEXT NOT NULL CHECK (
                        choice_type IN ('box', 'skip', 'keep', 'pass', 'bid', 'vote', 'abstain')
                    ),
                    target_player_id TEXT,
                    amount INTEGER NOT NULL DEFAULT 0,
                    choice_value INTEGER,
                    request_id TEXT NOT NULL,
                    submitted_at INTEGER NOT NULL,
                    UNIQUE (match_id, round_no, player_id),
                    UNIQUE (match_id, player_id, request_id),
                    FOREIGN KEY (match_id, player_id) REFERENCES match_players(match_id, player_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS challenge_history (
                    fingerprint TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    family TEXT NOT NULL,
                    options_json TEXT NOT NULL,
                    used_at INTEGER NOT NULL,
                    match_id TEXT,
                    round_no INTEGER
                );

                CREATE INDEX IF NOT EXISTS idx_challenge_history_used_at
                ON challenge_history(used_at);

                CREATE TABLE IF NOT EXISTS coin_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                    round_no INTEGER NOT NULL,
                    player_id TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    source_player_id TEXT,
                    created_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_coin_ledger_match_round
                ON coin_ledger(match_id, round_no, id);
                """
            )
            round_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(match_rounds)").fetchall()
            }
            if "event_json" not in round_columns:
                db.execute("ALTER TABLE match_rounds ADD COLUMN event_json TEXT")
            if "challenge_json" not in round_columns:
                db.execute("ALTER TABLE match_rounds ADD COLUMN challenge_json TEXT")
            if "challenge_result_json" not in round_columns:
                db.execute("ALTER TABLE match_rounds ADD COLUMN challenge_result_json TEXT")
            if "event_result_json" not in round_columns:
                db.execute("ALTER TABLE match_rounds ADD COLUMN event_result_json TEXT")

            # Backfill old fixed-deck questions so upgrading an existing game
            # database does not make previously played prompts eligible again.
            legacy_rows = db.execute(
                "SELECT match_id, round_no, challenge_json, created_at "
                "FROM match_rounds WHERE challenge_json IS NOT NULL"
            ).fetchall()
            for legacy_row in legacy_rows:
                legacy = self._json_load(legacy_row["challenge_json"], None)
                if not isinstance(legacy, dict) or not isinstance(legacy.get("prompt"), str):
                    continue
                options = legacy.get("options")
                if not isinstance(options, list):
                    options = []
                else:
                    options = [option for option in options if isinstance(option, str)]
                family = legacy.get("family") if isinstance(legacy.get("family"), str) else "قديم"
                db.execute(
                    "INSERT OR IGNORE INTO challenge_history "
                    "(fingerprint, prompt, family, options_json, used_at, match_id, round_no) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        challenge_fingerprint(legacy["prompt"], options),
                        legacy["prompt"],
                        family,
                        json.dumps(options, ensure_ascii=False),
                        legacy_row["created_at"],
                        legacy_row["match_id"],
                        legacy_row["round_no"],
                    ),
                )

    @staticmethod
    def _json_load(value: Optional[str], fallback: Any) -> Any:
        if not value:
            return fallback
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _round_event(db: sqlite3.Connection, match_id: str, round_no: int) -> Dict[str, str]:
        row = db.execute(
            "SELECT event_json FROM match_rounds WHERE match_id = ? AND round_no = ?",
            (match_id, round_no),
        ).fetchone()
        event = MatchEngine._json_load(row["event_json"] if row else None, None)
        if not isinstance(event, dict) or event.get("id") not in ROUND_EVENTS:
            return dict(ROUND_EVENTS["opening"])
        return event

    @staticmethod
    def _round_challenge(db: sqlite3.Connection, match_id: str, round_no: int) -> Dict[str, Any]:
        row = db.execute(
            "SELECT challenge_json FROM match_rounds WHERE match_id = ? AND round_no = ?",
            (match_id, round_no),
        ).fetchone()
        challenge = MatchEngine._json_load(row["challenge_json"] if row else None, None)
        valid = (
            isinstance(challenge, dict)
            and isinstance(challenge.get("id"), str)
            and isinstance(challenge.get("prompt"), str)
            and isinstance(challenge.get("family"), str)
            and isinstance(challenge.get("title"), str)
            and isinstance(challenge.get("options"), list)
            and len(challenge["options"]) >= 3
            and all(isinstance(option, str) for option in challenge["options"])
            and len(set(challenge["options"])) == len(challenge["options"])
            and isinstance(challenge.get("correct_index"), int)
            and not isinstance(challenge.get("correct_index"), bool)
            and 0 <= challenge["correct_index"] < len(challenge["options"])
            and isinstance(challenge.get("explanation"), str)
            and challenge.get("mode", "quiz") in ("quiz", "bluff", "prediction", "duel")
        )
        if not valid:
            raise StoreError("تعذر تحميل سؤال الجولة المحفوظ. لم يتم استبداله بسؤال قديم.")

        if challenge.get("mode", "quiz") == "duel":
            pairs = challenge.get("duel_pairs")
            assigned = [
                row["player_id"] for row in db.execute(
                    "SELECT player_id FROM match_players WHERE match_id = ? ORDER BY seat",
                    (match_id,),
                ).fetchall()
            ]
            valid_pairs = (
                isinstance(pairs, list)
                and len(pairs) == 2
                and all(
                    isinstance(pair, list)
                    and len(pair) == 2
                    and all(isinstance(player_id, str) for player_id in pair)
                    for pair in pairs
                )
            )
            paired = [player_id for pair in pairs for player_id in pair] if valid_pairs else []
            if (
                len(assigned) != 4
                or not valid_pairs
                or len(set(paired)) != 4
                or set(paired) != set(assigned)
            ):
                raise StoreError("ترتيب المواجهة الثنائية غير صالح.")
        return challenge

    def _claim_unique_challenge(
        self, db: sqlite3.Connection, match_id: str, round_no: int
    ) -> Dict[str, Any]:
        # BEGIN IMMEDIATE around every caller serializes claims from simultaneous
        # match starts. The UNIQUE fingerprint remains the final race-condition
        # guard and history intentionally has no FK to matches, so rematches and
        # even deletion of old match records cannot erase played-question history.
        player_rows = db.execute(
            "SELECT player_id FROM match_players WHERE match_id = ? ORDER BY seat",
            (match_id,),
        ).fetchall()
        player_count = len(player_rows)

        for _attempt in range(256):
            challenge = generate_challenge(player_count=player_count)
            if challenge.get("mode") == "duel":
                pairings = (
                    ((0, 1), (2, 3)),
                    ((0, 2), (1, 3)),
                    ((0, 3), (1, 2)),
                )
                selected_pairs = pairings[(round_no - 1) % len(pairings)]
                challenge["duel_pairs"] = [
                    [player_rows[first]["player_id"], player_rows[second]["player_id"]]
                    for first, second in selected_pairs
                ]
            fingerprint = challenge_fingerprint(
                challenge["prompt"], challenge["options"]
            )
            inserted = db.execute(
                "INSERT OR IGNORE INTO challenge_history "
                "(fingerprint, prompt, family, options_json, used_at, match_id, round_no) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    fingerprint,
                    challenge["prompt"],
                    challenge["family"],
                    json.dumps(challenge["options"], ensure_ascii=False),
                    int(time.time()),
                    match_id,
                    round_no,
                ),
            )
            if inserted.rowcount == 1:
                return challenge
        raise StoreError(
            "لم أتمكن من العثور على سؤال جديد غير مستخدم. أوقفنا بدء الجولة بدل تكرار سؤال سابق."
        )

    @staticmethod
    def _next_round_event(previous_id: str) -> Dict[str, str]:
        choices = [
            event for event_id, event in ROUND_EVENTS.items()
            if event_id not in ("opening", previous_id)
        ]
        return dict(secrets.choice(choices))

    @staticmethod
    def _event_requires_input(event_id: str) -> bool:
        return event_id in INTERACTIVE_EVENT_IDS

    def _prepare_round_event(
        self, db: sqlite3.Connection, match_id: str, round_no: int, previous_id: str
    ) -> Dict[str, Any]:
        event = self._next_round_event(previous_id)
        players = db.execute(
            "SELECT player_id, seat, display_name, coins FROM match_players "
            "WHERE match_id = ? ORDER BY seat",
            (match_id,),
        ).fetchall()
        player_count = len(players)
        if event["id"] == "black_box":
            contents = ["bonus", "shield", "trap"]
            secrets.SystemRandom().shuffle(contents)
            event["box_contents"] = contents
        elif event["id"] == "bomb":
            start_index = (round_no - 2) % player_count
            event["bomb_holder_id"] = players[start_index]["player_id"]
        elif event["id"] == "temporary_king":
            tie_start = (round_no - 2) % player_count
            king = min(
                players,
                key=lambda row: (
                    row["coins"],
                    (row["seat"] - 1 - tie_start) % player_count,
                ),
            )
            event["king_player_id"] = king["player_id"]
        return event

    @staticmethod
    def _public_round_event(
        event: Dict[str, Any], players: Sequence[sqlite3.Row]
    ) -> Dict[str, Any]:
        public = {
            key: event[key]
            for key in ("id", "title", "description", "effect")
            if key in event
        }
        player_map = {row["player_id"]: row["display_name"] for row in players}
        if event.get("id") == "bomb":
            public["bomb_starter_name"] = player_map.get(event.get("bomb_holder_id"))
        if event.get("id") == "temporary_king":
            public["king_name"] = player_map.get(event.get("king_player_id"))
        return public

    @staticmethod
    def _public_event_result(
        result: Optional[Dict[str, Any]], players: Sequence[sqlite3.Row]
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(result, dict):
            return None
        player_map = {row["player_id"]: row["display_name"] for row in players}
        public = {
            key: value for key, value in result.items()
            if key not in ("shield_player_ids", "winner_id", "target_player_id")
        }
        if isinstance(result.get("entries"), list):
            public["entries"] = [
                {
                    key: value
                    for key, value in entry.items()
                    if key not in ("player_id", "target_player_id")
                }
                for entry in result["entries"]
            ]
        if isinstance(result.get("shield_player_ids"), list):
            public["shield_names"] = [
                player_map[player_id]
                for player_id in result["shield_player_ids"]
                if player_id in player_map
            ]
        return public

    @staticmethod
    def _new_request_id(value: Any) -> str:
        if not isinstance(value, str):
            raise InvalidInput("معرّف الطلب غير صالح.")
        request_id = value.strip()
        if not 8 <= len(request_id) <= 80:
            raise InvalidInput("معرّف الطلب يجب أن يكون بين 8 و80 حرفًا.")
        if not all(ch.isalnum() or ch in "-_." for ch in request_id):
            raise InvalidInput("معرّف الطلب يحتوي على رموز غير مسموحة.")
        return request_id

    @staticmethod
    def _room_match(db: sqlite3.Connection, invite_code: str, active_only: bool = False) -> sqlite3.Row:
        code = _normalize_code(invite_code)
        condition = "AND m.status = 'active'" if active_only else ""
        row = db.execute(
            "SELECT m.*, r.invite_code FROM matches m "
            "JOIN rooms r ON r.id = m.room_id "
            "WHERE r.invite_code = ? %s ORDER BY m.created_at DESC, m.rowid DESC LIMIT 1" % condition,
            (code,),
        ).fetchone()
        if row is None:
            raise MatchNotFound("لا توجد مباراة لهذه الغرفة حتى الآن.")
        return row

    @staticmethod
    def _authorize(db: sqlite3.Connection, match_id: str, player_id: str) -> sqlite3.Row:
        player = db.execute(
            "SELECT * FROM match_players WHERE match_id = ? AND player_id = ?",
            (match_id, player_id),
        ).fetchone()
        if player is None:
            raise MatchNotActive("هذا اللاعب ليس ضمن هذه المباراة.")
        return player

    def start_match(self, invite_code: str, player_id: str) -> Dict[str, Any]:
        code = _normalize_code(invite_code)
        now = int(time.time())
        match_id = uuid.uuid4().hex

        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            room = db.execute("SELECT id FROM rooms WHERE invite_code = ?", (code,)).fetchone()
            if room is None:
                raise NotFound("الغرفة غير موجودة.")

            existing = db.execute(
                "SELECT id FROM matches WHERE room_id = ? AND status = 'active'",
                (room["id"],),
            ).fetchone()
            if existing is not None:
                self._authorize(db, existing["id"], player_id)
                db.commit()
                return self.get_state(code, player_id)

            roster = db.execute(
                "SELECT id, seat, display_name, color, avatar, ready, last_seen "
                "FROM players WHERE room_id = ? ORDER BY seat",
                (room["id"],),
            ).fetchall()
            count = len(roster)
            if count < MIN_PLAYERS or count > MAX_PLAYERS:
                raise MatchNotReady("تحتاج المباراة إلى ثلاثة أو أربعة لاعبين.")
            if any(not row["ready"] or now - row["last_seen"] > 25 for row in roster):
                raise MatchNotReady("يجب أن يكون جميع اللاعبين متصلين ومستعدين قبل البدء.")
            if not any(row["id"] == player_id for row in roster):
                raise MatchNotActive("يجب أن تكون لاعبًا في هذه الغرفة لبدء المباراة.")

            db.execute(
                "INSERT INTO matches "
                "(id, room_id, status, phase, round_no, total_rounds, deadline_at, revision, created_at, updated_at) "
                "VALUES (?, ?, 'active', 'actions', 1, ?, ?, 1, ?, ?)",
                (match_id, room["id"], TOTAL_ROUNDS, now + CHALLENGE_SECONDS, now, now),
            )
            for row in roster:
                db.execute(
                    "INSERT INTO match_players "
                    "(match_id, player_id, seat, display_name, color, avatar, coins, revenge_charges) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        match_id, row["id"], row["seat"], row["display_name"],
                        row["color"], row["avatar"], INITIAL_COINS, REVENGE_CHARGES,
                    ),
                )
            first_challenge = self._claim_unique_challenge(db, match_id, 1)
            db.execute(
                "INSERT INTO match_rounds "
                "(match_id, round_no, created_at, event_json, challenge_json) "
                "VALUES (?, 1, ?, ?, ?)",
                (
                    match_id, now,
                    json.dumps(ROUND_EVENTS["opening"], ensure_ascii=False),
                    json.dumps(first_challenge, ensure_ascii=False),
                ),
            )
            db.commit()

        return self.get_state(code, player_id)

    def _append_ledger(
        self,
        db: sqlite3.Connection,
        match_id: str,
        round_no: int,
        player_id: str,
        delta: int,
        reason: str,
        source_player_id: Optional[str] = None,
        now: Optional[int] = None,
    ) -> None:
        if not delta:
            return
        db.execute(
            "INSERT INTO coin_ledger "
            "(match_id, round_no, player_id, delta, reason, source_player_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (match_id, round_no, player_id, delta, reason, source_player_id, now or int(time.time())),
        )

    def _resolve_automatic_event(
        self, db: sqlite3.Connection, match: sqlite3.Row, now: int
    ) -> Optional[Dict[str, Any]]:
        event = self._round_event(db, match["id"], match["round_no"])
        if event["id"] != "temporary_king":
            return None

        king_id = event.get("king_player_id")
        king = db.execute(
            "SELECT player_id, display_name FROM match_players "
            "WHERE match_id = ? AND player_id = ?",
            (match["id"], king_id),
        ).fetchone()
        if king is None:
            raise StoreError("تعذر تحديد الملك المؤقت لهذه الجولة.")
        db.execute(
            "UPDATE match_players SET coins = coins + 1 "
            "WHERE match_id = ? AND player_id = ?",
            (match["id"], king_id),
        )
        self._append_ledger(
            db, match["id"], match["round_no"], king_id, 1,
            "king_crown_bonus", now=now,
        )
        return {
            "event_id": "temporary_king",
            "king_name": king["display_name"],
            "bonus": 1,
            "description": (
                "%s أصبح الملك المؤقت وربح عملة التاج. حمايته مجانية "
                "ويمكنه سرقة حتى 3 عملات في هذه الجولة."
            ) % king["display_name"],
        }

    def _resolve_challenge(self, db: sqlite3.Connection, match: sqlite3.Row, now: int) -> None:
        match_id = match["id"]
        round_no = match["round_no"]
        challenge = self._round_challenge(db, match_id, round_no)
        players = db.execute(
            "SELECT mp.player_id, mp.display_name, mp.seat, ca.answer_index "
            "FROM match_players mp LEFT JOIN challenge_answers ca "
            "ON ca.match_id = mp.match_id AND ca.round_no = ? AND ca.player_id = mp.player_id "
            "WHERE mp.match_id = ? ORDER BY mp.seat",
            (round_no, match_id),
        ).fetchall()

        mode = challenge.get("mode", "quiz")
        answer_by_id = {}
        for player in players:
            answer_index = player["answer_index"]
            answered = answer_index is not None
            answer_by_id[player["player_id"]] = {
                "player_id": player["player_id"],
                "player_name": player["display_name"],
                "answered": bool(answered),
                "answer_index": answer_index,
                "answer_text": challenge["options"][answer_index] if answered else None,
                "correct": bool(answered and answer_index == challenge["correct_index"]),
                "reward": 0,
            }

        duel_results = []
        if mode == "duel":
            if len(challenge.get("duel_pairs", [])) != 2:
                raise StoreError("بيانات المواجهة الثنائية غير مكتملة.")
            for pair in challenge["duel_pairs"]:
                if len(pair) != 2 or pair[0] not in answer_by_id or pair[1] not in answer_by_id:
                    raise StoreError("ترتيب لاعبي المواجهة غير صالح.")
                first = answer_by_id[pair[0]]
                second = answer_by_id[pair[1]]
                if first["correct"] and not second["correct"]:
                    first["reward"] = DUEL_WIN_REWARD
                    duel_results.append({
                        "outcome": "first_won",
                        "winner_name": first["player_name"],
                        "opponent_name": second["player_name"],
                        "reward": DUEL_WIN_REWARD,
                    })
                elif second["correct"] and not first["correct"]:
                    second["reward"] = DUEL_WIN_REWARD
                    duel_results.append({
                        "outcome": "second_won",
                        "winner_name": second["player_name"],
                        "opponent_name": first["player_name"],
                        "reward": DUEL_WIN_REWARD,
                    })
                elif first["correct"] and second["correct"]:
                    first["reward"] = CHALLENGE_REWARD
                    second["reward"] = CHALLENGE_REWARD
                    duel_results.append({
                        "outcome": "both_correct",
                        "winner_name": None,
                        "opponent_name": None,
                        "reward": CHALLENGE_REWARD,
                    })
                else:
                    duel_results.append({
                        "outcome": "no_correct_answer",
                        "winner_name": None,
                        "opponent_name": None,
                        "reward": 0,
                    })
        else:
            for answer in answer_by_id.values():
                if answer["correct"]:
                    answer["reward"] = CHALLENGE_REWARD

        answers = list(answer_by_id.values())
        for answer in answers:
            reward = answer["reward"]
            if reward:
                db.execute(
                    "UPDATE match_players SET coins = coins + ? WHERE match_id = ? AND player_id = ?",
                    (reward, match_id, answer["player_id"]),
                )
                reason = "duel_reward" if mode == "duel" else "challenge_reward"
                self._append_ledger(
                    db, match_id, round_no, answer["player_id"], reward,
                    reason, now=now,
                )

        result = {
            "challenge_id": challenge["id"],
            "mode": mode,
            "mode_label": challenge.get("mode_label", "تحدّي معلومات"),
            "title": challenge["title"],
            "prompt": challenge["prompt"],
            "correct_index": challenge["correct_index"],
            "correct_answer": challenge["options"][challenge["correct_index"]],
            "explanation": challenge["explanation"],
            "reward": CHALLENGE_REWARD,
            "answers": answers,
            "duel_results": duel_results,
        }
        db.execute(
            "UPDATE match_rounds SET challenge_result_json = ? "
            "WHERE match_id = ? AND round_no = ?",
            (json.dumps(result, ensure_ascii=False), match_id, round_no),
        )
        automatic_event_result = self._resolve_automatic_event(db, match, now)
        if automatic_event_result is not None:
            db.execute(
                "UPDATE match_rounds SET event_result_json = ? "
                "WHERE match_id = ? AND round_no = ?",
                (json.dumps(automatic_event_result, ensure_ascii=False), match_id, round_no),
            )
        event = self._round_event(db, match_id, round_no)
        next_window = EVENT_SECONDS if self._event_requires_input(event["id"]) else ACTION_SECONDS
        db.execute(
            "UPDATE matches SET deadline_at = ?, revision = revision + 1, updated_at = ? "
            "WHERE id = ?",
            (now + next_window, now, match_id),
        )

    def submit_challenge(
        self,
        invite_code: str,
        player_id: str,
        request_id: Any,
        answer_index: Any,
    ) -> Dict[str, Any]:
        code = _normalize_code(invite_code)
        request_id = self._new_request_id(request_id)
        if isinstance(answer_index, bool) or not isinstance(answer_index, int):
            raise InvalidInput("اختر إجابة من الخيارات المعروضة.")
        now = int(time.time())

        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            match = self._room_match(db, code, active_only=True)
            self._authorize(db, match["id"], player_id)
            previous_request = db.execute(
                "SELECT * FROM challenge_answers WHERE match_id = ? AND player_id = ? AND request_id = ?",
                (match["id"], player_id, request_id),
            ).fetchone()
            if previous_request is not None:
                if previous_request["answer_index"] == answer_index:
                    db.commit()
                    return self.get_state(code, player_id)
                raise ActionLocked("معرّف هذا الطلب استُخدم لإجابة مختلفة.")

            self._advance_expired(db, match, now)
            match = db.execute("SELECT * FROM matches WHERE id = ?", (match["id"],)).fetchone()
            round_row = db.execute(
                "SELECT challenge_json, challenge_result_json FROM match_rounds "
                "WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()
            challenge = self._round_challenge(db, match["id"], match["round_no"])

            existing = db.execute(
                "SELECT * FROM challenge_answers WHERE match_id = ? AND round_no = ? AND player_id = ?",
                (match["id"], match["round_no"], player_id),
            ).fetchone()
            if existing is not None:
                same = (
                    existing["request_id"] == request_id
                    and existing["answer_index"] == answer_index
                )
                if same:
                    db.commit()
                    return self.get_state(code, player_id)
                raise ActionLocked("تم قفل إجابتك لهذا التحدي.")

            if round_row["challenge_result_json"]:
                raise MatchNotActive("انتهى وقت التحدي وتم كشف الإجابات.")
            if match["phase"] != "actions":
                raise MatchNotActive("مرحلة التحدي غير مفتوحة الآن.")
            if not 0 <= answer_index < len(challenge["options"]):
                raise InvalidInput("الإجابة المختارة غير موجودة ضمن الخيارات.")

            db.execute(
                "INSERT INTO challenge_answers "
                "(match_id, round_no, player_id, answer_index, request_id, submitted_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (match["id"], match["round_no"], player_id, answer_index, request_id, now),
            )
            submitted = db.execute(
                "SELECT COUNT(*) AS count FROM challenge_answers WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()["count"]
            total = db.execute(
                "SELECT COUNT(*) AS count FROM match_players WHERE match_id = ?",
                (match["id"],),
            ).fetchone()["count"]
            if submitted >= total:
                self._resolve_challenge(db, match, now)
            else:
                db.execute(
                    "UPDATE matches SET revision = revision + 1, updated_at = ? WHERE id = ?",
                    (now, match["id"]),
                )
            db.commit()

        return self.get_state(code, player_id)

    def _insert_timeout_event_choices(
        self, db: sqlite3.Connection, match: sqlite3.Row, now: int, event_id: str
    ) -> None:
        defaults = {
            "black_box": ("skip", None, 0, None),
            "bomb": ("keep", None, 0, None),
            "secret_auction": ("bid", None, 0, None),
            "court": ("abstain", None, 0, None),
        }
        choice_type, target_id, amount, choice_value = defaults[event_id]
        db.execute(
            "INSERT OR IGNORE INTO event_actions "
            "(match_id, round_no, player_id, choice_type, target_player_id, amount, "
            "choice_value, request_id, submitted_at) "
            "SELECT ?, ?, mp.player_id, ?, ?, ?, ?, 'event-timeout-' || mp.player_id, ? "
            "FROM match_players mp WHERE mp.match_id = ? "
            "AND NOT EXISTS (SELECT 1 FROM event_actions ea "
            "WHERE ea.match_id = mp.match_id AND ea.round_no = ? "
            "AND ea.player_id = mp.player_id)",
            (
                match["id"], match["round_no"], choice_type, target_id, amount,
                choice_value, now, match["id"], match["round_no"],
            ),
        )

    def _resolve_event_choices(
        self, db: sqlite3.Connection, match: sqlite3.Row, now: int
    ) -> None:
        match_id = match["id"]
        round_no = match["round_no"]
        event = self._round_event(db, match_id, round_no)
        event_id = event["id"]
        if not self._event_requires_input(event_id):
            raise MatchNotActive("لا يحتاج هذا الحدث إلى قرار إضافي.")

        self._insert_timeout_event_choices(db, match, now, event_id)
        players = db.execute(
            "SELECT * FROM match_players WHERE match_id = ? ORDER BY seat",
            (match_id,),
        ).fetchall()
        player_map = {row["player_id"]: dict(row) for row in players}
        actions = db.execute(
            "SELECT ea.*, mp.display_name, mp.seat "
            "FROM event_actions ea JOIN match_players mp "
            "ON mp.match_id = ea.match_id AND mp.player_id = ea.player_id "
            "WHERE ea.match_id = ? AND ea.round_no = ? ORDER BY mp.seat",
            (match_id, round_no),
        ).fetchall()

        event_result: Dict[str, Any] = {"event_id": event_id}
        if event_id == "black_box":
            contents = event.get("box_contents")
            if not isinstance(contents, list) or len(contents) != 3 or set(contents) != {
                "bonus", "shield", "trap"
            }:
                raise StoreError("محتويات الصندوق الأسود غير صالحة.")
            entries = []
            shields = []
            for action in actions:
                outcome = "لم يختر صندوقًا"
                delta = 0
                if action["choice_type"] == "box":
                    index = action["choice_value"]
                    if isinstance(index, int) and 0 <= index < len(contents):
                        outcome = contents[index]
                        if outcome == "bonus":
                            delta = 2
                        elif outcome == "trap":
                            delta = -min(1, player_map[action["player_id"]]["coins"])
                        elif outcome == "shield":
                            shields.append(action["player_id"])
                if delta:
                    db.execute(
                        "UPDATE match_players SET coins = coins + ? "
                        "WHERE match_id = ? AND player_id = ?",
                        (delta, match_id, action["player_id"]),
                    )
                    self._append_ledger(
                        db, match_id, round_no, action["player_id"], delta,
                        "black_box_bonus" if delta > 0 else "black_box_trap", now=now,
                    )
                entries.append({
                    "player_id": action["player_id"],
                    "player_name": action["display_name"],
                    "box": (action["choice_value"] + 1)
                        if action["choice_type"] == "box" and action["choice_value"] is not None else None,
                    "outcome": outcome,
                    "delta": delta,
                })
            event_result.update({
                "entries": entries,
                "shield_player_ids": shields,
                "description": "كُشفت الصناديق: مكافآت وحمايات وفخاخ مختلفة.",
            })

        elif event_id == "bomb":
            if event.get("bomb_holder_id") not in player_map:
                raise StoreError("لم يتم تحديد حامل القنبلة الأولى.")
            by_player = {action["player_id"]: action for action in actions}
            holder_id = event["bomb_holder_id"]
            visited = []
            while holder_id not in visited:
                visited.append(holder_id)
                action = by_player.get(holder_id)
                if (
                    action is None
                    or action["choice_type"] != "pass"
                    or action["target_player_id"] not in player_map
                    or action["target_player_id"] == holder_id
                    or action["target_player_id"] in visited
                ):
                    break
                holder_id = action["target_player_id"]

            starter = player_map[event["bomb_holder_id"]]["display_name"]
            final_holder = player_map[holder_id]
            damage = min(2, final_holder["coins"])
            if damage:
                db.execute(
                    "UPDATE match_players SET coins = coins - ? "
                    "WHERE match_id = ? AND player_id = ?",
                    (damage, match_id, holder_id),
                )
                self._append_ledger(
                    db, match_id, round_no, holder_id, -damage, "bomb_penalty", now=now
                )
            event_result.update({
                "starter_name": starter,
                "path_names": [player_map[item]["display_name"] for item in visited],
                "final_holder_name": final_holder["display_name"],
                "damage": damage,
                "description": (
                    "انفجرت القنبلة مع %s وخسر %s عملات."
                    % (final_holder["display_name"], damage)
                ),
            })

        elif event_id == "secret_auction":
            bid_rows = [
                {
                    "player_id": action["player_id"],
                    "player_name": action["display_name"],
                    "seat": action["seat"],
                    "amount": action["amount"],
                }
                for action in actions
            ]
            highest = max((row["amount"] for row in bid_rows), default=0)
            winner = None
            if highest > 0:
                player_count = len(players)
                tie_start = (round_no - 1) % player_count
                winner = min(
                    (row for row in bid_rows if row["amount"] == highest),
                    key=lambda row: (row["seat"] - 1 - tie_start) % player_count,
                )
                db.execute(
                    "UPDATE match_players SET coins = coins - ? "
                    "WHERE match_id = ? AND player_id = ?",
                    (highest, match_id, winner["player_id"]),
                )
                self._append_ledger(
                    db, match_id, round_no, winner["player_id"], -highest,
                    "secret_auction_bid", now=now,
                )
            event_result.update({
                "entries": [
                    {"player_name": row["player_name"], "bid": row["amount"]}
                    for row in bid_rows
                ],
                "winner_name": winner["player_name"] if winner else None,
                "winning_bid": highest if winner else 0,
                "shield_player_ids": [winner["player_id"]] if winner else [],
                "description": (
                    "%s فاز بالمزاد وحصل على حماية مجانية بعد دفع %d عملات."
                    % (winner["player_name"], highest)
                    if winner else "لم يقدم أحد عرضًا موجبًا؛ انتهى المزاد دون فائز."
                ),
            })

        elif event_id == "court":
            vote_counts: Dict[str, int] = {}
            for action in actions:
                if action["choice_type"] == "vote" and action["target_player_id"] in player_map:
                    target_id = action["target_player_id"]
                    vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
            highest = max(vote_counts.values(), default=0)
            leaders = [player_id for player_id, count in vote_counts.items() if count == highest]
            target_id = leaders[0] if highest > 0 and len(leaders) == 1 else None
            has_majority = target_id is not None and highest > len(players) / 2
            penalty = 0
            target_name = player_map[target_id]["display_name"] if target_id else None
            if has_majority:
                penalty = min(1, player_map[target_id]["coins"])
                if penalty:
                    db.execute(
                        "UPDATE match_players SET coins = coins - ? "
                        "WHERE match_id = ? AND player_id = ?",
                        (penalty, match_id, target_id),
                    )
                    self._append_ledger(
                        db, match_id, round_no, target_id, -penalty,
                        "court_penalty", now=now,
                    )
            event_result.update({
                "entries": [
                    {
                        "player_name": action["display_name"],
                        "vote_name": (
                            player_map[action["target_player_id"]]["display_name"]
                            if action["choice_type"] == "vote"
                            and action["target_player_id"] in player_map
                            else "امتناع"
                        ),
                    }
                    for action in actions
                ],
                "vote_counts": [
                    {"player_name": player_map[player_id]["display_name"], "votes": count}
                    for player_id, count in sorted(
                        vote_counts.items(), key=lambda item: player_map[item[0]]["seat"]
                    )
                ],
                "target_name": target_name if has_majority else None,
                "majority": bool(has_majority),
                "penalty": penalty,
                "description": (
                    "%s أُدين بأغلبية مطلقة وخسر %d عملات."
                    % (target_name, penalty)
                    if has_majority else "لم تحصل أي قضية على أغلبية مطلقة؛ أُسقطت القضية."
                ),
            })

        db.execute(
            "UPDATE match_rounds SET event_result_json = ? "
            "WHERE match_id = ? AND round_no = ?",
            (json.dumps(event_result, ensure_ascii=False), match_id, round_no),
        )
        db.execute(
            "UPDATE matches SET deadline_at = ?, revision = revision + 1, updated_at = ? "
            "WHERE id = ?",
            (now + ACTION_SECONDS, now, match_id),
        )

    def submit_event(
        self,
        invite_code: str,
        player_id: str,
        request_id: Any,
        choice_type: Any,
        target_player_id: Any = None,
        amount: Any = 0,
        choice_value: Any = None,
    ) -> Dict[str, Any]:
        code = _normalize_code(invite_code)
        request_id = self._new_request_id(request_id)
        if not isinstance(choice_type, str):
            raise InvalidInput("اختيار الحدث غير صالح.")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise InvalidInput("قيمة العرض غير صالحة.")
        if choice_value is not None and (
            isinstance(choice_value, bool) or not isinstance(choice_value, int)
        ):
            raise InvalidInput("رقم الصندوق غير صالح.")
        now = int(time.time())

        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            match = self._room_match(db, code, active_only=True)
            self._authorize(db, match["id"], player_id)

            previous_request = db.execute(
                "SELECT * FROM event_actions WHERE match_id = ? AND player_id = ? AND request_id = ?",
                (match["id"], player_id, request_id),
            ).fetchone()
            if previous_request is not None:
                same = (
                    previous_request["choice_type"] == choice_type
                    and previous_request["target_player_id"] == target_player_id
                    and previous_request["amount"] == amount
                    and previous_request["choice_value"] == choice_value
                )
                if same:
                    db.commit()
                    return self.get_state(code, player_id)
                raise ActionLocked("معرّف هذا الطلب استُخدم لقرار حدث مختلف.")

            round_row = db.execute(
                "SELECT challenge_result_json, event_result_json FROM match_rounds "
                "WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()
            event = self._round_event(db, match["id"], match["round_no"])
            event_pending_before_advance = (
                bool(round_row and round_row["challenge_result_json"])
                and self._event_requires_input(event["id"])
                and not round_row["event_result_json"]
            )
            self._advance_expired(db, match, now)
            match = db.execute("SELECT * FROM matches WHERE id = ?", (match["id"],)).fetchone()
            if not event_pending_before_advance:
                raise MatchNotActive("لا توجد نافذة قرار حدث مفتوحة الآن.")
            if now >= match["deadline_at"] and match["phase"] != "actions":
                raise MatchNotActive("انتهى وقت الحدث؛ تم اعتماد القرارات الافتراضية.")
            round_row = db.execute(
                "SELECT challenge_result_json, event_result_json FROM match_rounds "
                "WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()
            if (
                not round_row
                or not round_row["challenge_result_json"]
                or round_row["event_result_json"]
                or not self._event_requires_input(event["id"])
            ):
                raise MatchNotActive("انتهت نافذة قرار الحدث.")
            if match["phase"] != "actions":
                raise MatchNotActive("مرحلة قرار الحدث غير مفتوحة الآن.")

            current = self._authorize(db, match["id"], player_id)
            player_count = db.execute(
                "SELECT COUNT(*) AS count FROM match_players WHERE match_id = ?",
                (match["id"],),
            ).fetchone()["count"]
            if event["id"] == "black_box":
                if choice_type != "box" or choice_value not in (0, 1, 2):
                    raise InvalidInput("اختر صندوقًا واحدًا من الصناديق الثلاثة.")
                if target_player_id is not None or amount != 0:
                    raise InvalidInput("اختيار الصندوق لا يحتاج إلى لاعب أو مبلغ.")
            elif event["id"] == "bomb":
                if choice_type not in ("keep", "pass"):
                    raise InvalidInput("اختر الاحتفاظ بالقنبلة أو تمريرها.")
                if choice_type == "pass":
                    if not isinstance(target_player_id, str) or not target_player_id:
                        raise InvalidInput("اختر اللاعب الذي ستمرر إليه القنبلة.")
                    self._authorize(db, match["id"], target_player_id)
                    if target_player_id == player_id:
                        raise InvalidInput("لا يمكنك تمرير القنبلة إلى نفسك.")
                elif target_player_id is not None:
                    raise InvalidInput("الاحتفاظ بالقنبلة لا يحتاج إلى هدف.")
                if amount != 0 or choice_value is not None:
                    raise InvalidInput("هذا القرار لا يحتاج إلى مبلغ أو رقم صندوق.")
            elif event["id"] == "secret_auction":
                if choice_type != "bid" or target_player_id is not None or choice_value is not None:
                    raise InvalidInput("أدخل عرضًا سريًا فقط.")
                if not 0 <= amount <= 3 or amount > current["coins"]:
                    raise InvalidInput("يجب أن يكون عرضك بين صفر وثلاث عملات وبحدود رصيدك.")
            elif event["id"] == "court":
                if choice_type == "vote":
                    if not isinstance(target_player_id, str) or not target_player_id:
                        raise InvalidInput("اختر لاعبًا آخر للتصويت عليه.")
                    self._authorize(db, match["id"], target_player_id)
                    if target_player_id == player_id:
                        raise InvalidInput("لا يمكنك التصويت ضد نفسك.")
                elif choice_type == "abstain":
                    if target_player_id is not None:
                        raise InvalidInput("الامتناع لا يحتاج إلى هدف.")
                else:
                    raise InvalidInput("اختر لاعبًا أو امتنع عن التصويت.")
                if amount != 0 or choice_value is not None:
                    raise InvalidInput("التصويت لا يحتاج إلى مبلغ أو رقم صندوق.")

            existing = db.execute(
                "SELECT * FROM event_actions WHERE match_id = ? AND round_no = ? AND player_id = ?",
                (match["id"], match["round_no"], player_id),
            ).fetchone()
            if existing is not None:
                same = (
                    existing["request_id"] == request_id
                    and existing["choice_type"] == choice_type
                    and existing["target_player_id"] == target_player_id
                    and existing["amount"] == amount
                    and existing["choice_value"] == choice_value
                )
                if same:
                    db.commit()
                    return self.get_state(code, player_id)
                raise ActionLocked("تم قفل قرارك لهذا الحدث.")

            db.execute(
                "INSERT INTO event_actions "
                "(match_id, round_no, player_id, choice_type, target_player_id, amount, "
                "choice_value, request_id, submitted_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    match["id"], match["round_no"], player_id, choice_type,
                    target_player_id, amount, choice_value, request_id, now,
                ),
            )
            submitted = db.execute(
                "SELECT COUNT(*) AS count FROM event_actions WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()["count"]
            if submitted >= player_count:
                self._resolve_event_choices(db, match, now)
            else:
                db.execute(
                    "UPDATE matches SET revision = revision + 1, updated_at = ? WHERE id = ?",
                    (now, match["id"]),
                )
            db.commit()

        return self.get_state(code, player_id)

    def _insert_timeout_passes(self, db: sqlite3.Connection, match: sqlite3.Row, now: int) -> None:
        db.execute(
            "INSERT OR IGNORE INTO round_actions "
            "(match_id, round_no, player_id, action_type, target_player_id, amount, request_id, submitted_at) "
            "SELECT ?, ?, mp.player_id, 'pass', NULL, 0, 'timeout-' || mp.player_id, ? "
            "FROM match_players mp WHERE mp.match_id = ? "
            "AND NOT EXISTS (SELECT 1 FROM round_actions a WHERE a.match_id = mp.match_id "
            "AND a.round_no = ? AND a.player_id = mp.player_id)",
            (match["id"], match["round_no"], now, match["id"], match["round_no"]),
        )

    def _resolve_actions(self, db: sqlite3.Connection, match: sqlite3.Row, now: int) -> None:
        match_id = match["id"]
        round_no = match["round_no"]
        event = self._round_event(db, match_id, round_no)
        event_id = event["id"]
        event_result_row = db.execute(
            "SELECT event_result_json FROM match_rounds WHERE match_id = ? AND round_no = ?",
            (match_id, round_no),
        ).fetchone()
        event_result = self._json_load(
            event_result_row["event_result_json"] if event_result_row else None, {}
        )
        king_id = event.get("king_player_id") if event_id == "temporary_king" else None
        event_shields = event_result.get("shield_player_ids", [])
        if not isinstance(event_shields, list):
            event_shields = []
        self._insert_timeout_passes(db, match, now)

        players = db.execute(
            "SELECT * FROM match_players WHERE match_id = ? ORDER BY seat",
            (match_id,),
        ).fetchall()
        player_map = {row["player_id"]: dict(row) for row in players}
        actions = db.execute(
            "SELECT a.*, mp.display_name, mp.seat "
            "FROM round_actions a JOIN match_players mp "
            "ON mp.match_id = a.match_id AND mp.player_id = a.player_id "
            "WHERE a.match_id = ? AND a.round_no = ? ORDER BY mp.seat",
            (match_id, round_no),
        ).fetchall()

        balances = {player_id: row["coins"] for player_id, row in player_map.items()}
        guarded = {
            player_id for player_id in event_shields if player_id in player_map
        }
        if king_id in player_map:
            guarded.add(king_id)
        public_actions = []
        blocked_attacks = []
        wager_results = []
        thefts = []
        eligible = {}

        for action in actions:
            if action["action_type"] == "guard":
                player_id = action["player_id"]
                if player_id in guarded:
                    continue
                player_guard_cost = (
                    0 if event_id == "free_guard" or player_id == king_id else GUARD_COST
                )
                if balances[player_id] >= player_guard_cost:
                    balances[player_id] -= player_guard_cost
                    guarded.add(player_id)
                    if player_guard_cost:
                        self._append_ledger(
                            db, match_id, round_no, player_id, -player_guard_cost,
                            "guard_cost", now=now,
                        )

        for action in actions:
            if action["action_type"] != "wager":
                continue
            player_id = action["player_id"]
            stake = action["amount"]
            won = bool(secrets.randbelow(2))
            delta = (stake * 2 if event_id == "high_stakes" else stake) if won else -stake
            balances[player_id] += delta
            self._append_ledger(
                db, match_id, round_no, player_id, delta,
                "wager_win" if won else "wager_loss", now=now,
            )
            wager_results.append({
                "player_id": player_id,
                "player_name": action["display_name"],
                "stake": stake,
                "won": won,
                "delta": delta,
            })

        for action in actions:
            if action["action_type"] != "steal":
                continue
            attacker_id = action["player_id"]
            target_id = action["target_player_id"]
            attacker = player_map[attacker_id]
            target = player_map[target_id]
            if target_id in guarded:
                db.execute(
                    "UPDATE match_players SET successful_guards = successful_guards + 1 "
                    "WHERE match_id = ? AND player_id = ?",
                    (match_id, target_id),
                )
                blocked_attacks.append({
                    "attacker_id": attacker_id,
                    "attacker_name": attacker["display_name"],
                    "target_id": target_id,
                    "target_name": target["display_name"],
                    "reason": "guarded",
                })
                continue

            attacker_steal_limit = MAX_STEAL + 1 if (
                event_id == "market_rush" or attacker_id == king_id
            ) else MAX_STEAL
            stolen = min(attacker_steal_limit, balances[target_id])
            if stolen <= 0:
                blocked_attacks.append({
                    "attacker_id": attacker_id,
                    "attacker_name": attacker["display_name"],
                    "target_id": target_id,
                    "target_name": target["display_name"],
                    "reason": "empty",
                })
                continue

            balances[target_id] -= stolen
            balances[attacker_id] += stolen
            self._append_ledger(db, match_id, round_no, attacker_id, stolen, "successful_steal", target_id, now)
            self._append_ledger(db, match_id, round_no, target_id, -stolen, "stolen_from", attacker_id, now)
            bounty = 1 if event_id == "bounty" else 0
            if bounty:
                balances[attacker_id] += bounty
                self._append_ledger(
                    db, match_id, round_no, attacker_id, bounty, "event_bounty", target_id, now
                )
            db.execute(
                "UPDATE match_players SET coins_stolen = coins_stolen + ? "
                "WHERE match_id = ? AND player_id = ?",
                (stolen, match_id, attacker_id),
            )
            thefts.append({
                "attacker_id": attacker_id,
                "attacker_name": attacker["display_name"],
                "target_id": target_id,
                "target_name": target["display_name"],
                "amount": stolen,
                "bonus": bounty,
            })
            eligible.setdefault(target_id, [])
            if attacker_id not in eligible[target_id]:
                eligible[target_id].append(attacker_id)

        for player_id, balance in balances.items():
            if balance < 0:
                raise RuntimeError("Match engine produced a negative coin balance.")
            db.execute(
                "UPDATE match_players SET coins = ? WHERE match_id = ? AND player_id = ?",
                (balance, match_id, player_id),
            )

        public_actions = []
        for action in actions:
            item = {
                "player_id": action["player_id"],
                "player_name": action["display_name"],
                "seat": action["seat"],
                "action": action["action_type"],
            }
            if action["action_type"] == "steal":
                item["target_id"] = action["target_player_id"]
                item["target_name"] = player_map[action["target_player_id"]]["display_name"]
            elif action["action_type"] == "wager":
                item["amount"] = action["amount"]
            public_actions.append(item)

        coin_changes = []
        for row in db.execute(
            "SELECT mp.player_id, mp.display_name, mp.seat, mp.coins "
            "FROM match_players mp WHERE mp.match_id = ? ORDER BY mp.seat",
            (match_id,),
        ).fetchall():
            original = player_map[row["player_id"]]["coins"]
            if original != row["coins"]:
                coin_changes.append({
                    "player_id": row["player_id"],
                    "name": row["display_name"],
                    "seat": row["seat"],
                    "before": original,
                    "after": row["coins"],
                    "delta": row["coins"] - original,
                })

        result = {
            "event": self._public_round_event(event, players),
            "event_result": self._public_event_result(event_result, players),
            "actions": public_actions,
            "thefts": thefts,
            "blocked_attacks": blocked_attacks,
            "wagers": wager_results,
            "coin_changes": coin_changes,
            "revenge_eligible": eligible,
            "revenge_results": [],
        }
        db.execute(
            "UPDATE match_rounds SET public_result_json = ?, settled_at = ? "
            "WHERE match_id = ? AND round_no = ?",
            (json.dumps(result, ensure_ascii=False), now, match_id, round_no),
        )

        next_phase = "revenge" if eligible else "result"
        next_deadline = now + (REVENGE_SECONDS if eligible else RESULT_SECONDS)
        db.execute(
            "UPDATE matches SET phase = ?, deadline_at = ?, revision = revision + 1, updated_at = ? "
            "WHERE id = ?",
            (next_phase, next_deadline, now, match_id),
        )

    def submit_action(
        self,
        invite_code: str,
        player_id: str,
        request_id: Any,
        action_type: Any,
        target_player_id: Any = None,
        amount: Any = 0,
    ) -> Dict[str, Any]:
        code = _normalize_code(invite_code)
        request_id = self._new_request_id(request_id)
        if action_type not in ("steal", "guard", "wager", "pass"):
            raise InvalidInput("الحركة المختارة غير معروفة.")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise InvalidInput("قيمة الحركة غير صحيحة.")
        if action_type in ("guard", "pass") and amount != 0:
            raise InvalidInput("هذه الحركة لا تحتاج إلى تحديد مبلغ.")
        if action_type == "wager" and not 1 <= amount <= MAX_WAGER:
            raise InvalidInput("المراهنة يجب أن تكون بين 1 و3 عملات.")
        if action_type != "wager" and amount != 0:
            raise InvalidInput("لا يمكن تحديد مبلغ لهذه الحركة.")
        if action_type == "steal" and (not isinstance(target_player_id, str) or not target_player_id):
            raise InvalidInput("اختر لاعبًا لاستهدافه.")
        if action_type != "steal" and target_player_id is not None:
            raise InvalidInput("هذه الحركة لا تحتاج إلى هدف.")

        now = int(time.time())
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            match = self._room_match(db, code, active_only=True)
            self._authorize(db, match["id"], player_id)
            previous_request = db.execute(
                "SELECT * FROM round_actions WHERE match_id = ? AND player_id = ? AND request_id = ?",
                (match["id"], player_id, request_id),
            ).fetchone()
            if previous_request is not None:
                same = (
                    previous_request["action_type"] == action_type
                    and previous_request["target_player_id"] == target_player_id
                    and previous_request["amount"] == amount
                )
                if same:
                    db.commit()
                    return self.get_state(code, player_id)
                raise ActionLocked("معرّف هذا الطلب استُخدم لحركة مختلفة.")

            before_advance = db.execute(
                "SELECT challenge_result_json, event_result_json FROM match_rounds "
                "WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()
            challenge_was_pending = (
                not before_advance or not before_advance["challenge_result_json"]
            )
            event_before = self._round_event(db, match["id"], match["round_no"])
            event_was_pending = (
                bool(before_advance and before_advance["challenge_result_json"])
                and self._event_requires_input(event_before["id"])
                and not before_advance["event_result_json"]
            )
            self._advance_expired(db, match, now)
            match = db.execute("SELECT * FROM matches WHERE id = ?", (match["id"],)).fetchone()
            if challenge_was_pending:
                raise MatchNotActive("انتهت مرحلة التحدي أو لم تُكشف إجاباته بعد؛ حدّث الشاشة.")
            if event_was_pending:
                raise MatchNotActive("انتهت مرحلة الحدث أو لم تُكشف نتيجته بعد؛ حدّث الشاشة.")
            round_progress = db.execute(
                "SELECT challenge_result_json, event_result_json FROM match_rounds "
                "WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()
            if not round_progress or not round_progress["challenge_result_json"]:
                raise MatchNotActive("أكمل التحدي أولًا؛ ستُفتح الحركات بعد كشف الإجابات.")
            current_event = self._round_event(db, match["id"], match["round_no"])
            if (
                self._event_requires_input(current_event["id"])
                and not round_progress["event_result_json"]
            ):
                raise MatchNotActive("أكمل قرار الحدث أولًا؛ الحركات لم تُفتح بعد.")
            existing = db.execute(
                "SELECT * FROM round_actions WHERE match_id = ? AND round_no = ? AND player_id = ?",
                (match["id"], match["round_no"], player_id),
            ).fetchone()
            if existing is not None:
                same = (
                    existing["request_id"] == request_id
                    and existing["action_type"] == action_type
                    and existing["target_player_id"] == target_player_id
                    and existing["amount"] == amount
                )
                if same:
                    db.commit()
                    return self.get_state(code, player_id)
                raise ActionLocked("تم قفل اختيارك لهذه الجولة. انتظر كشف النتائج.")

            if match["phase"] != "actions":
                raise MatchNotActive("انتهت مرحلة الاختيارات السرية لهذه الجولة.")

            current = self._authorize(db, match["id"], player_id)
            if action_type == "steal":
                target = self._authorize(db, match["id"], target_player_id)
                if target_player_id == player_id:
                    raise InvalidInput("لا يمكنك سرقة نفسك.")
            elif action_type == "guard":
                event = self._round_event(db, match["id"], match["round_no"])
                guard_cost = 0 if (
                    event["id"] == "free_guard"
                    or (
                        event["id"] == "temporary_king"
                        and event.get("king_player_id") == player_id
                    )
                ) else GUARD_COST
                if current["coins"] < guard_cost:
                    raise InvalidInput("تحتاج إلى عملة واحدة لاستخدام الحماية.")
            elif action_type == "wager" and current["coins"] < amount:
                raise InvalidInput("رصيدك لا يكفي لهذه المراهنة.")

            db.execute(
                "INSERT INTO round_actions "
                "(match_id, round_no, player_id, action_type, target_player_id, amount, request_id, submitted_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (match["id"], match["round_no"], player_id, action_type, target_player_id, amount, request_id, now),
            )
            submitted = db.execute(
                "SELECT COUNT(*) AS count FROM round_actions WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()["count"]
            player_count = db.execute(
                "SELECT COUNT(*) AS count FROM match_players WHERE match_id = ?",
                (match["id"],),
            ).fetchone()["count"]
            if submitted >= player_count:
                self._resolve_actions(db, match, now)
            else:
                db.execute(
                    "UPDATE matches SET revision = revision + 1, updated_at = ? WHERE id = ?",
                    (now, match["id"]),
                )
            db.commit()

        return self.get_state(code, player_id)

    def _eligible_revenge(self, result: Dict[str, Any], player_id: str) -> List[str]:
        eligible = result.get("revenge_eligible", {})
        targets = eligible.get(player_id, []) if isinstance(eligible, dict) else []
        return [target for target in targets if isinstance(target, str)]

    def _resolve_revenge(self, db: sqlite3.Connection, match: sqlite3.Row, now: int) -> None:
        match_id = match["id"]
        round_no = match["round_no"]
        round_row = db.execute(
            "SELECT public_result_json FROM match_rounds WHERE match_id = ? AND round_no = ?",
            (match_id, round_no),
        ).fetchone()
        result = self._json_load(round_row["public_result_json"] if round_row else None, {})
        eligible = result.get("revenge_eligible", {})
        victims = list(eligible.keys()) if isinstance(eligible, dict) else []

        for victim_id in victims:
            db.execute(
                "INSERT OR IGNORE INTO revenge_actions "
                "(match_id, round_no, player_id, target_player_id, action_type, request_id, submitted_at) "
                "VALUES (?, ?, ?, NULL, 'pass', ?, ?)",
                (match_id, round_no, victim_id, "timeout-revenge-" + victim_id, now),
            )

        actions = db.execute(
            "SELECT r.*, mp.display_name, mp.seat "
            "FROM revenge_actions r JOIN match_players mp "
            "ON mp.match_id = r.match_id AND mp.player_id = r.player_id "
            "WHERE r.match_id = ? AND r.round_no = ? ORDER BY mp.seat",
            (match_id, round_no),
        ).fetchall()
        revenge_results = []

        for action in actions:
            if action["action_type"] != "counterstrike":
                continue
            victim_id = action["player_id"]
            attacker_id = action["target_player_id"]
            victim = self._authorize(db, match_id, victim_id)
            attacker = self._authorize(db, match_id, attacker_id)
            if victim["revenge_charges"] <= 0:
                revenge_results.append({
                    "player_id": victim_id, "target_id": attacker_id,
                    "success": False, "reason": "no_charges",
                })
                continue

            victim_list = eligible.get(victim_id, [])
            if attacker_id not in victim_list:
                revenge_results.append({
                    "player_id": victim_id, "target_id": attacker_id,
                    "success": False, "reason": "not_eligible",
                })
                continue

            event = result.get("event") or self._round_event(db, match_id, round_no)
            revenge_limit = 2 if event.get("id") == "double_revenge" else REVENGE_AMOUNT
            revenge_amount = min(revenge_limit, attacker["coins"])
            if revenge_amount <= 0:
                revenge_results.append({
                    "player_id": victim_id, "target_id": attacker_id,
                    "success": False, "reason": "empty_target",
                })
                continue

            db.execute(
                "UPDATE match_players SET coins = coins + ?, revenge_charges = revenge_charges - 1, "
                "revenge_used = revenge_used + 1 WHERE match_id = ? AND player_id = ?",
                (revenge_amount, match_id, victim_id),
            )
            db.execute(
                "UPDATE match_players SET coins = coins - ? WHERE match_id = ? AND player_id = ?",
                (revenge_amount, match_id, attacker_id),
            )
            self._append_ledger(
                db, match_id, round_no, victim_id, revenge_amount,
                "revenge_counterstrike", attacker_id, now,
            )
            self._append_ledger(
                db, match_id, round_no, attacker_id, -revenge_amount,
                "revenge_paid", victim_id, now,
            )
            revenge_results.append({
                "player_id": victim_id,
                "player_name": victim["display_name"],
                "target_id": attacker_id,
                "target_name": attacker["display_name"],
                "success": True,
                "amount": revenge_amount,
            })

        result["revenge_results"] = revenge_results
        coin_rows = db.execute(
            "SELECT player_id, display_name, seat, coins FROM match_players "
            "WHERE match_id = ? ORDER BY seat",
            (match_id,),
        ).fetchall()
        result["final_coins"] = [
            {"player_id": row["player_id"], "name": row["display_name"], "seat": row["seat"], "coins": row["coins"]}
            for row in coin_rows
        ]
        db.execute(
            "UPDATE match_rounds SET public_result_json = ?, settled_at = ? "
            "WHERE match_id = ? AND round_no = ?",
            (json.dumps(result, ensure_ascii=False), now, match_id, round_no),
        )
        db.execute(
            "UPDATE matches SET phase = 'result', deadline_at = ?, revision = revision + 1, updated_at = ? "
            "WHERE id = ?",
            (now + RESULT_SECONDS, now, match_id),
        )

    def _advance_expired(self, db: sqlite3.Connection, match: sqlite3.Row, now: int) -> None:
        if match["status"] != "active" or now < match["deadline_at"]:
            return

        phase = match["phase"]
        if phase == "actions":
            round_progress = db.execute(
                "SELECT challenge_result_json, event_result_json FROM match_rounds "
                "WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()
            if not round_progress or not round_progress["challenge_result_json"]:
                self._resolve_challenge(db, match, now)
            else:
                event = self._round_event(db, match["id"], match["round_no"])
                if (
                    self._event_requires_input(event["id"])
                    and not round_progress["event_result_json"]
                ):
                    self._resolve_event_choices(db, match, now)
                else:
                    self._resolve_actions(db, match, now)
            return
        if phase == "revenge":
            self._resolve_revenge(db, match, now)
            return
        if phase != "result":
            return

        if match["round_no"] >= match["total_rounds"]:
            db.execute(
                "UPDATE matches SET status = 'finished', phase = 'finished', revision = revision + 1, updated_at = ? "
                "WHERE id = ?",
                (now, match["id"]),
            )
            return

        previous_event = self._round_event(db, match["id"], match["round_no"])
        next_round = match["round_no"] + 1
        next_event = self._prepare_round_event(
            db, match["id"], next_round, previous_event["id"]
        )
        next_challenge = self._claim_unique_challenge(db, match["id"], next_round)
        db.execute(
            "UPDATE matches SET round_no = ?, phase = 'actions', deadline_at = ?, "
            "revision = revision + 1, updated_at = ? WHERE id = ?",
            (next_round, now + CHALLENGE_SECONDS, now, match["id"]),
        )
        db.execute(
            "INSERT OR IGNORE INTO match_rounds "
            "(match_id, round_no, created_at, event_json, challenge_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                match["id"], next_round, now, json.dumps(next_event, ensure_ascii=False),
                json.dumps(next_challenge, ensure_ascii=False),
            ),
        )

    def submit_revenge(
        self,
        invite_code: str,
        player_id: str,
        request_id: Any,
        action_type: Any,
        target_player_id: Any = None,
    ) -> Dict[str, Any]:
        code = _normalize_code(invite_code)
        request_id = self._new_request_id(request_id)
        if action_type not in ("counterstrike", "pass"):
            raise InvalidInput("اختيار الانتقام غير معروف.")
        if action_type == "counterstrike" and not isinstance(target_player_id, str):
            raise InvalidInput("اختر اللاعب الذي ستنتقم منه.")
        if action_type == "pass" and target_player_id is not None:
            raise InvalidInput("تجاوز الانتقام لا يحتاج إلى هدف.")

        now = int(time.time())
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            match = self._room_match(db, code, active_only=True)
            self._authorize(db, match["id"], player_id)
            self._advance_expired(db, match, now)
            match = db.execute("SELECT * FROM matches WHERE id = ?", (match["id"],)).fetchone()
            round_row = db.execute(
                "SELECT public_result_json FROM match_rounds WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()
            result = self._json_load(round_row["public_result_json"] if round_row else None, {})
            targets = self._eligible_revenge(result, player_id)
            if not targets:
                raise MatchNotActive("لم تتعرض لسرقة ناجحة في هذه الجولة.")

            existing = db.execute(
                "SELECT * FROM revenge_actions WHERE match_id = ? AND round_no = ? AND player_id = ?",
                (match["id"], match["round_no"], player_id),
            ).fetchone()
            if existing is not None:
                same = (
                    existing["request_id"] == request_id
                    and existing["action_type"] == action_type
                    and existing["target_player_id"] == target_player_id
                )
                if same:
                    db.commit()
                    return self.get_state(code, player_id)
                raise ActionLocked("تم تسجيل قرار الانتقام لهذه الجولة.")

            if match["phase"] != "revenge":
                raise MatchNotActive("مرحلة الانتقام غير مفتوحة الآن.")

            current = self._authorize(db, match["id"], player_id)
            if action_type == "counterstrike":
                if target_player_id not in targets:
                    raise InvalidInput("يمكنك الانتقام فقط من لاعب سرق منك في هذه الجولة.")
                if current["revenge_charges"] <= 0:
                    raise InvalidInput("استخدمت فرص الانتقام المتاحة لك.")
                target = self._authorize(db, match["id"], target_player_id)
                if target["coins"] < REVENGE_AMOUNT:
                    raise InvalidInput("لا يملك اللاعب المستهدف عملات يمكن استردادها.")

            db.execute(
                "INSERT INTO revenge_actions "
                "(match_id, round_no, player_id, target_player_id, action_type, request_id, submitted_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (match["id"], match["round_no"], player_id, target_player_id, action_type, request_id, now),
            )
            submitted = db.execute(
                "SELECT COUNT(*) AS count FROM revenge_actions WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()["count"]
            if submitted >= len(result.get("revenge_eligible", {})):
                self._resolve_revenge(db, match, now)
            else:
                db.execute(
                    "UPDATE matches SET revision = revision + 1, updated_at = ? WHERE id = ?",
                    (now, match["id"]),
                )
            db.commit()

        return self.get_state(code, player_id)

    def get_state(self, invite_code: str, player_id: str) -> Dict[str, Any]:
        code = _normalize_code(invite_code)
        now = int(time.time())
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            match = self._room_match(db, code)
            self._authorize(db, match["id"], player_id)
            self._advance_expired(db, match, now)
            match = db.execute("SELECT * FROM matches WHERE id = ?", (match["id"],)).fetchone()

            players = db.execute(
                "SELECT mp.*, p.last_seen FROM match_players mp "
                "LEFT JOIN players p ON p.id = mp.player_id "
                "WHERE mp.match_id = ? ORDER BY mp.seat",
                (match["id"],),
            ).fetchall()
            round_row = db.execute(
                "SELECT public_result_json, event_json, challenge_json, challenge_result_json, event_result_json "
                "FROM match_rounds WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()
            result = self._json_load(round_row["public_result_json"] if round_row else None, None)
            challenge_data = self._json_load(
                round_row["challenge_json"] if round_row else None, ROUND_CHALLENGES[0]
            )
            challenge_result = self._json_load(
                round_row["challenge_result_json"] if round_row else None, None
            )
            if not isinstance(challenge_data, dict):
                challenge_data = dict(ROUND_CHALLENGES[0])
            public_challenge = {
                "id": challenge_data["id"],
                "mode": challenge_data.get("mode", "quiz"),
                "mode_label": challenge_data.get("mode_label", "تحدّي معلومات"),
                "mode_description": challenge_data.get(
                    "mode_description", "أجب عن السؤال؛ الإجابة الصحيحة تمنحك عملتين."
                ),
                "family": challenge_data["family"],
                "title": challenge_data["title"],
                "prompt": challenge_data["prompt"],
                "options": list(challenge_data["options"]),
                "reward": CHALLENGE_REWARD,
                "duel_opponent": None,
            }
            if public_challenge["mode"] == "duel":
                for pair in challenge_data.get("duel_pairs", []):
                    if player_id in pair:
                        opponent_id = pair[0] if pair[1] == player_id else pair[1]
                        opponent = next(
                            (row for row in players if row["player_id"] == opponent_id),
                            None,
                        )
                        public_challenge["duel_opponent"] = (
                            opponent["display_name"] if opponent else None
                        )
                        break
            event_result_raw = self._json_load(
                round_row["event_result_json"] if round_row else None, None
            )
            event_raw = self._round_event(db, match["id"], match["round_no"])
            event_pending = (
                match["status"] == "active"
                and match["phase"] == "actions"
                and challenge_result is not None
                and self._event_requires_input(event_raw["id"])
                and event_result_raw is None
            )
            public_phase = (
                "challenge"
                if match["status"] == "active"
                and match["phase"] == "actions"
                and challenge_result is None
                else ("event" if event_pending else match["phase"])
            )
            round_event = self._public_round_event(event_raw, players)
            event_result = self._public_event_result(event_result_raw, players)

            challenge_count = db.execute(
                "SELECT COUNT(*) AS count FROM challenge_answers WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()["count"]
            my_challenge = db.execute(
                "SELECT 1 FROM challenge_answers WHERE match_id = ? AND round_no = ? AND player_id = ?",
                (match["id"], match["round_no"], player_id),
            ).fetchone()
            event_count = db.execute(
                "SELECT COUNT(*) AS count FROM event_actions WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()["count"]
            my_event = db.execute(
                "SELECT 1 FROM event_actions WHERE match_id = ? AND round_no = ? AND player_id = ?",
                (match["id"], match["round_no"], player_id),
            ).fetchone()
            action_count = db.execute(
                "SELECT COUNT(*) AS count FROM round_actions WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()["count"]
            my_action = db.execute(
                "SELECT 1 FROM round_actions WHERE match_id = ? AND round_no = ? AND player_id = ?",
                (match["id"], match["round_no"], player_id),
            ).fetchone()

            revenge_submitted = db.execute(
                "SELECT 1 FROM revenge_actions WHERE match_id = ? AND round_no = ? AND player_id = ?",
                (match["id"], match["round_no"], player_id),
            ).fetchone()
            my_row = next((row for row in players if row["player_id"] == player_id), None)
            if my_row is None:
                raise MatchNotActive("لم يتم العثور على مقعدك في المباراة.")

            eligible_targets = self._eligible_revenge(result or {}, player_id)
            public_players = []
            for row in players:
                public_players.append({
                    "id": row["player_id"],
                    "seat": row["seat"],
                    "name": row["display_name"],
                    "color": row["color"],
                    "avatar": row["avatar"],
                    "coins": row["coins"],
                    "connected": row["last_seen"] is not None and now - row["last_seen"] <= 25,
                })

            db.commit()

        ranking = sorted(
            public_players,
            key=lambda player: (
                -player["coins"],
                -next(row["coins_stolen"] for row in players if row["player_id"] == player["id"]),
                player["seat"],
            ),
        )
        state = {
            "ok": True,
            "match_id": match["id"],
            "status": match["status"],
            "phase": public_phase,
            "round": match["round_no"],
            "total_rounds": match["total_rounds"],
            "deadline_at": match["deadline_at"],
            "seconds_remaining": max(0, match["deadline_at"] - now),
            "revision": match["revision"],
            "player_count": len(public_players),
            "players": public_players,
            "round_event": round_event,
            "event_result": event_result,
            "event_submitted_count": event_count,
            "event_submit_total": len(public_players),
            "challenge": public_challenge,
            "challenge_result": challenge_result,
            "challenge_answers_submitted": challenge_count,
            "challenge_answer_total": len(public_players),
            "actions_submitted": action_count,
            "action_total": len(public_players),
            "private": {
                "challenge_submitted": bool(my_challenge),
                "event_submitted": bool(my_event),
                "is_temporary_king": (
                    event_raw.get("id") == "temporary_king"
                    and event_raw.get("king_player_id") == player_id
                ),
                "action_submitted": bool(my_action),
                "revenge_submitted": bool(revenge_submitted),
                "revenge_charges": my_row["revenge_charges"],
                "revenge_targets": eligible_targets,
            },
            "result": result if match["phase"] in ("revenge", "result", "finished") else None,
            "ranking": ranking if match["status"] == "finished" else None,
        }
        return state
