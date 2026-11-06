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
    def _next_round_event(previous_id: str) -> Dict[str, str]:
        choices = [
            event for event_id, event in ROUND_EVENTS.items()
            if event_id not in ("opening", previous_id)
        ]
        return dict(secrets.choice(choices))

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
                (match_id, room["id"], TOTAL_ROUNDS, now + ACTION_SECONDS, now, now),
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
            db.execute(
                "INSERT INTO match_rounds (match_id, round_no, created_at, event_json) "
                "VALUES (?, 1, ?, ?)",
                (
                    match_id, now,
                    json.dumps(ROUND_EVENTS["opening"], ensure_ascii=False),
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
        guard_cost = 0 if event_id == "free_guard" else GUARD_COST
        steal_limit = MAX_STEAL + 1 if event_id == "market_rush" else MAX_STEAL
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
        guarded = set()
        public_actions = []
        blocked_attacks = []
        wager_results = []
        thefts = []
        eligible = {}

        for action in actions:
            if action["action_type"] == "guard":
                player_id = action["player_id"]
                if balances[player_id] >= guard_cost:
                    balances[player_id] -= guard_cost
                    guarded.add(player_id)
                    self._append_ledger(db, match_id, round_no, player_id, -guard_cost, "guard_cost", now=now)

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

            stolen = min(steal_limit, balances[target_id])
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
            "event": event,
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
            self._advance_expired(db, match, now)
            match = db.execute("SELECT * FROM matches WHERE id = ?", (match["id"],)).fetchone()
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
                guard_cost = 0 if event["id"] == "free_guard" else GUARD_COST
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
        next_event = self._next_round_event(previous_event["id"])
        next_round = match["round_no"] + 1
        db.execute(
            "UPDATE matches SET round_no = ?, phase = 'actions', deadline_at = ?, "
            "revision = revision + 1, updated_at = ? WHERE id = ?",
            (next_round, now + ACTION_SECONDS, now, match["id"]),
        )
        db.execute(
            "INSERT OR IGNORE INTO match_rounds "
            "(match_id, round_no, created_at, event_json) VALUES (?, ?, ?, ?)",
            (match["id"], next_round, now, json.dumps(next_event, ensure_ascii=False)),
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
                "SELECT public_result_json, event_json FROM match_rounds "
                "WHERE match_id = ? AND round_no = ?",
                (match["id"], match["round_no"]),
            ).fetchone()
            result = self._json_load(round_row["public_result_json"] if round_row else None, None)
            round_event = self._json_load(
                round_row["event_json"] if round_row else None, ROUND_EVENTS["opening"]
            )
            if not isinstance(round_event, dict):
                round_event = dict(ROUND_EVENTS["opening"])

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
            "phase": match["phase"],
            "round": match["round_no"],
            "total_rounds": match["total_rounds"],
            "deadline_at": match["deadline_at"],
            "seconds_remaining": max(0, match["deadline_at"] - now),
            "revision": match["revision"],
            "player_count": len(public_players),
            "players": public_players,
            "round_event": round_event,
            "actions_submitted": action_count,
            "action_total": len(public_players),
            "private": {
                "action_submitted": bool(my_action),
                "revenge_submitted": bool(revenge_submitted),
                "revenge_charges": my_row["revenge_charges"],
                "revenge_targets": eligible_targets,
            },
            "result": result if match["phase"] in ("revenge", "result", "finished") else None,
            "ranking": ranking if match["status"] == "finished" else None,
        }
        return state
