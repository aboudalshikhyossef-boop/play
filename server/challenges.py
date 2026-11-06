"""Non-repeating family-friendly Arabic challenge generation.

The engine records every prompt fingerprint in SQLite. This module creates
fresh questions from several deterministic-to-score templates with random
parameters; the answer key is never sent to browsers before reveal.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import unicodedata
import uuid
from typing import Any, Dict, List, Sequence, Tuple

CHALLENGE_SECONDS = 25
CHALLENGE_REWARD = 2

# Kept only so an existing SQLite database can import old prompts into the
# permanent no-repeat history when the engine is upgraded.
ROUND_CHALLENGES = (
    {
        "id": "three_apples",
        "family": "حساب بسيط",
        "title": "اختبار سريع",
        "prompt": "لديك 3 تفاحات وأعطيت تفاحة لصديقك. كم تفاحة بقيت معك؟",
        "options": ["1", "2", "3"],
        "correct_index": 1,
        "explanation": "ثلاث تفاحات ناقص واحدة تساوي تفاحتين.",
    },
    {
        "id": "even_sequence",
        "family": "اكتشف النمط",
        "title": "ما الرقم التالي؟",
        "prompt": "ما العدد التالي في السلسلة: 2، 4، 6، 8، ؟",
        "options": ["9", "10", "12"],
        "correct_index": 1,
        "explanation": "نضيف 2 في كل مرة، لذلك الرقم التالي هو 10.",
    },
    {
        "id": "equal_weight",
        "family": "فخ ذكي",
        "title": "انتبه للسؤال",
        "prompt": "كيلوغرام من الحديد وكيلوغرام من القطن: أيهما أثقل؟",
        "options": ["الحديد", "القطن", "الوزن متساوٍ"],
        "correct_index": 2,
        "explanation": "كلاهما كيلوغرام واحد؛ الوزن متساوٍ.",
    },
    {
        "id": "comb_teeth",
        "family": "لغز عائلي",
        "title": "من صاحب الأسنان؟",
        "prompt": "شيء له أسنان كثيرة لكنه لا يعض. ما هو؟",
        "options": ["المشط", "المفتاح", "الملعقة"],
        "correct_index": 0,
        "explanation": "المشط له أسنان لترتيب الشعر، لكنه لا يعض.",
    },
    {
        "id": "chair_legs",
        "family": "حساب بسيط",
        "title": "احسبها بسرعة",
        "prompt": "ثلاثة كراسٍ، لكل كرسي أربع أرجل. كم رجلًا بالمجموع؟",
        "options": ["7", "10", "12"],
        "correct_index": 2,
        "explanation": "3 كراسٍ × 4 أرجل = 12 رجلًا.",
    },
    {
        "id": "half_hour",
        "family": "وقت وتركيز",
        "title": "كم دقيقة؟",
        "prompt": "الساعة الآن 5:00. كم دقيقة حتى تصبح 5:30؟",
        "options": ["15 دقيقة", "30 دقيقة", "45 دقيقة"],
        "correct_index": 1,
        "explanation": "من الدقيقة صفر إلى الدقيقة 30 نصف ساعة، أي 30 دقيقة.",
    },
    {
        "id": "days_forward",
        "family": "تركيز",
        "title": "احسب الأيام",
        "prompt": "إذا كان اليوم الاثنين، فما اليوم بعد ثلاثة أيام؟",
        "options": ["الأربعاء", "الخميس", "الجمعة"],
        "correct_index": 1,
        "explanation": "الثلاثاء، ثم الأربعاء، ثم الخميس.",
    },
    {
        "id": "coin_change",
        "family": "حساب بسيط",
        "title": "احسب رصيدك",
        "prompt": "معك 10 عملات، دفعت 3 ثم ربحت عملتين. كم أصبح معك؟",
        "options": ["7 عملات", "9 عملات", "10 عملات"],
        "correct_index": 1,
        "explanation": "10 ناقص 3 يساوي 7، ثم نضيف 2 فيصبح المجموع 9.",
    },
)

CHALLENGE_BY_ID = {challenge["id"]: challenge for challenge in ROUND_CHALLENGES}

_MEMORY_WORDS = (
    "قمر", "مفتاح", "بحر", "وردة", "كتاب", "نافذة", "تفاحة", "سحابة",
    "مصباح", "طائرة", "نخلة", "ساعة", "حقيبة", "نهر", "مرآة", "نجمة",
    "كرسي", "ليمون", "باب", "فراشة", "قطار", "حديقة", "شمعة", "مطر",
)
_ODD_GROUPS = (
    ("تفاحة", "موزة", "برتقالة", "عنب", "مطرقة", "مفك"),
    ("قطة", "حصان", "أرنب", "فيل", "طاولة", "نافذة"),
    ("أحمر", "أزرق", "أخضر", "أصفر", "ملعقة", "كتاب"),
    ("قلم", "دفتر", "ممحاة", "مسطرة", "سمكة", "أسد"),
)


def challenge_fingerprint(prompt: str) -> str:
    """Stable SHA-256 identity for a prompt, independent of whitespace."""
    normalized = " ".join(unicodedata.normalize("NFKC", prompt).split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _random_int(low: int, high: int) -> int:
    return low + secrets.randbelow(high - low + 1)


def _numeric_options(correct: int, offsets: Sequence[int] = (-2, -1, 1, 2, 5)) -> Tuple[List[str], int]:
    distractors = []
    for offset in offsets:
        candidate = correct + offset
        if candidate >= 0 and candidate != correct and str(candidate) not in distractors:
            distractors.append(str(candidate))
        if len(distractors) == 2:
            break
    while len(distractors) < 2:
        candidate = correct + _random_int(3, 17)
        if candidate >= 0 and candidate != correct and str(candidate) not in distractors:
            distractors.append(str(candidate))
    options = [str(correct)] + distractors
    secrets.SystemRandom().shuffle(options)
    return options, options.index(str(correct))


def _time_label(total_minutes: int) -> str:
    hour = ((total_minutes // 60 - 1) % 12) + 1
    minute = total_minutes % 60
    return "%d:%02d" % (hour, minute)


def _make_challenge(
    family: str,
    title: str,
    prompt: str,
    options: Sequence[str],
    correct_answer: str,
    explanation: str,
) -> Dict[str, Any]:
    values = list(options)
    if len(values) < 3 or len(set(values)) != len(values):
        raise ValueError("Challenge options must contain at least three unique values.")
    if correct_answer not in values:
        raise ValueError("Correct answer must be one of the displayed options.")
    return {
        "id": "generated-" + uuid.uuid4().hex,
        "family": family,
        "title": title,
        "prompt": prompt,
        "options": values,
        "correct_index": values.index(correct_answer),
        "explanation": explanation,
    }


def _addition() -> Dict[str, Any]:
    left, right = _random_int(12, 99), _random_int(11, 89)
    answer = left + right
    options, correct = _numeric_options(answer, (-1, 1, -10, 10))
    return _make_challenge(
        "حساب ذهني", "اجمع الرقمين",
        "احسب بسرعة: %d + %d = ؟" % (left, right),
        options, str(answer), "%d + %d = %d." % (left, right, answer),
    )


def _subtraction() -> Dict[str, Any]:
    start = _random_int(35, 180)
    removed = _random_int(5, start - 5)
    answer = start - removed
    options, correct = _numeric_options(answer, (-2, -1, 1, 2, 5))
    return _make_challenge(
        "حساب ذهني", "كم بقي؟",
        "كان معك %d قطعة وأعطيت %d قطعة. كم قطعة بقيت؟" % (start, removed),
        options, str(answer), "%d − %d = %d." % (start, removed, answer),
    )


def _multiplication() -> Dict[str, Any]:
    left, right = _random_int(3, 18), _random_int(2, 15)
    answer = left * right
    options, correct = _numeric_options(answer, (-left, -right, left, right, -2, 2))
    return _make_challenge(
        "حساب ذهني", "اضربها بسرعة",
        "في كل صندوق %d كرات، ولدينا %d صناديق. كم كرة لدينا؟" % (left, right),
        options, str(answer), "%d × %d = %d كرة." % (left, right, answer),
    )


def _sequence() -> Dict[str, Any]:
    start, step = _random_int(1, 45), _random_int(2, 13)
    values = [start + step * index for index in range(4)]
    answer = values[-1] + step
    options, correct = _numeric_options(answer, (-step, -1, 1, step))
    prompt = "اكتشف النمط: %s، ؟ ما العدد التالي؟" % "، ".join(str(v) for v in values)
    return _make_challenge(
        "اكتشف النمط", "ما الرقم التالي؟", prompt, options, str(answer),
        "يزيد العدد بمقدار %d في كل خطوة؛ لذلك التالي هو %d." % (step, answer),
    )


def _clock() -> Dict[str, Any]:
    hour, minute = _random_int(1, 11), _random_int(0, 11) * 5
    duration = _random_int(2, 10) * 5
    start = hour * 60 + minute
    answer = _time_label(start + duration)
    distractors = [
        _time_label(start + duration + 10),
        _time_label(start + duration - 10),
    ]
    options = [answer] + distractors
    secrets.SystemRandom().shuffle(options)
    return _make_challenge(
        "وقت وتركيز", "احسب الوقت",
        "الساعة الآن %s. كم تصبح بعد %d دقيقة؟" % (_time_label(start), duration),
        options, answer,
        "نضيف %d دقيقة إلى %s، فتكون النتيجة %s." % (duration, _time_label(start), answer),
    )


def _memory() -> Dict[str, Any]:
    words = list(secrets.SystemRandom().sample(_MEMORY_WORDS, 4))
    answer = words[2]
    alternatives = list(secrets.SystemRandom().sample([word for word in _MEMORY_WORDS if word not in words], 2))
    options = [answer] + alternatives
    secrets.SystemRandom().shuffle(options)
    return _make_challenge(
        "ذاكرة سريعة", "تذكّر الترتيب",
        "تذكّر الكلمات بالترتيب: %s. ما الكلمة الثالثة؟" % "، ".join(words),
        options, answer, "الكلمة الثالثة في الترتيب هي «%s»." % answer,
    )


def _odd_one_out() -> Dict[str, Any]:
    group = secrets.choice(_ODD_GROUPS)
    members = list(secrets.SystemRandom().sample(group[:4], 3))
    odd = secrets.choice(group[4:])
    options = members + [odd]
    secrets.SystemRandom().shuffle(options)
    return _make_challenge(
        "ملاحظة وتركيز", "اكتشف المختلف",
        "ثلاث كلمات تنتمي إلى مجموعة واحدة. أي كلمة مختلفة؟",
        options, odd,
        "الكلمة «%s» لا تنتمي إلى المجموعة التي تنتمي إليها الكلمات الثلاث الأخرى." % odd,
    )


def _comparison() -> Dict[str, Any]:
    a, b, c, d = (_random_int(5, 45) for _ in range(4))
    first, second = a + b, c + d
    answer = "المجموع الأول أكبر" if first > second else (
        "المجموع الثاني أكبر" if second > first else "المجموعان متساويان"
    )
    options = ["المجموع الأول أكبر", "المجموع الثاني أكبر", "المجموعان متساويان"]
    return _make_challenge(
        "مقارنة وتفكير", "أي المجموعين أكبر؟",
        "قارن بين (%d + %d) و(%d + %d). أيهما أكبر؟" % (a, b, c, d),
        options, answer,
        "%d + %d = %d، و%d + %d = %d؛ لذلك %s." % (
            a, b, first, c, d, second, answer
        ),
    )


_GENERATORS = (
    _addition,
    _subtraction,
    _multiplication,
    _sequence,
    _clock,
    _memory,
    _odd_one_out,
    _comparison,
)


def generate_challenge() -> Dict[str, Any]:
    """Create a fresh question from one of several family-friendly formats."""
    return secrets.choice(_GENERATORS)()
