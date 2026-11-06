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
from typing import Any, Dict, List, Sequence

CHALLENGE_SECONDS = 25
CHALLENGE_REWARD = 2
DUEL_WIN_REWARD = 3

MODE_DETAILS = {
    "quiz": {
        "label": "تحدّي معلومات",
        "description": "أجب عن السؤال. كل إجابة صحيحة تمنحك عملتين إضافيتين.",
    },
    "bluff": {
        "label": "اكتشف الكذبة",
        "description": "أمامك ثلاث معادلات؛ اثنتان صحيحتان وواحدة مزيفة. اكتشف المعادلة الخاطئة لتحصل على عملتين.",
    },
    "prediction": {
        "label": "توقّع النرد",
        "description": "توقّع مجموع نردين قبل كشف النتيجة. الاختيار الصحيح يمنحك عملتين؛ هذا تحدٍّ للحظ.",
    },
    "duel": {
        "label": "مواجهة ثنائية",
        "description": "تواجه لاعبًا واحدًا. إذا كنت الوحيد الذي أجاب صحيحًا تكسب 3 عملات؛ إذا أصبتما معًا تكسبان عملتين لكل منكما؛ ولا خصم عند الخطأ.",
    },
}

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


def challenge_fingerprint(prompt: str, options: Sequence[str] = ()) -> str:
    """Stable identity for the full question and its option set.

    Sorting normalized options means reordering the same choices does not make
    an old question appear new. The prompt itself is kept intact after cleanup.
    """
    normalized_prompt = " ".join(
        unicodedata.normalize("NFKC", prompt).split()
    ).casefold()
    normalized_options = sorted(
        " ".join(unicodedata.normalize("NFKC", option).split()).casefold()
        for option in options
    )
    canonical = json.dumps(
        [normalized_prompt, normalized_options],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _random_int(low: int, high: int) -> int:
    return low + secrets.randbelow(high - low + 1)


def _numeric_options(correct: int, offsets: Sequence[int] = (-2, -1, 1, 2, 5)) -> List[str]:
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
    return options


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
    mode: str = "quiz",
) -> Dict[str, Any]:
    values = list(options)
    if len(values) < 3 or len(set(values)) != len(values):
        raise ValueError("Challenge options must contain at least three unique values.")
    if correct_answer not in values:
        raise ValueError("Correct answer must be one of the displayed options.")
    if mode not in MODE_DETAILS:
        raise ValueError("Unknown challenge mode: %s" % mode)
    mode_details = MODE_DETAILS[mode]
    return {
        "id": "generated-" + uuid.uuid4().hex,
        "mode": mode,
        "mode_label": mode_details["label"],
        "mode_description": mode_details["description"],
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
    options = _numeric_options(answer, (-1, 1, -10, 10))
    return _make_challenge(
        "حساب ذهني", "اجمع الرقمين",
        "احسب بسرعة: %d + %d = ؟" % (left, right),
        options, str(answer), "%d + %d = %d." % (left, right, answer),
    )


def _subtraction() -> Dict[str, Any]:
    start = _random_int(35, 180)
    removed = _random_int(5, start - 5)
    answer = start - removed
    options = _numeric_options(answer, (-2, -1, 1, 2, 5))
    return _make_challenge(
        "حساب ذهني", "كم بقي؟",
        "كان معك %d قطعة وأعطيت %d قطعة. كم قطعة بقيت؟" % (start, removed),
        options, str(answer), "%d − %d = %d." % (start, removed, answer),
    )


def _multiplication() -> Dict[str, Any]:
    left, right = _random_int(3, 18), _random_int(2, 15)
    answer = left * right
    options = _numeric_options(answer, (-left, -right, left, right, -2, 2))
    return _make_challenge(
        "حساب ذهني", "اضربها بسرعة",
        "في كل صندوق %d كرات، ولدينا %d صناديق. كم كرة لدينا؟" % (left, right),
        options, str(answer), "%d × %d = %d كرة." % (left, right, answer),
    )


def _sequence() -> Dict[str, Any]:
    start, step = _random_int(1, 45), _random_int(2, 13)
    values = [start + step * index for index in range(4)]
    answer = values[-1] + step
    options = _numeric_options(answer, (-step, -1, 1, step))
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


def _bluff() -> Dict[str, Any]:
    equations = []
    false_index = secrets.randbelow(3)
    for index in range(3):
        left, right = _random_int(7, 55), _random_int(6, 48)
        answer = left + right
        shown = answer
        if index == false_index:
            shown += _random_int(2, 9)
        equations.append({
            "left": left,
            "right": right,
            "shown": shown,
            "correct": answer,
        })

    statements = [
        "%d + %d = %d" % (item["left"], item["right"], item["shown"])
        for item in equations
    ]
    options = ["المعادلة الأولى", "المعادلة الثانية", "المعادلة الثالثة"]
    return _make_challenge(
        "خداع وتركيز",
        "اكتشف المعادلة المزيفة",
        "اثنتان من هذه المعادلات صحيحتان وواحدة خاطئة. أي واحدة هي الكذبة؟\n"
        + "\n".join(
            "%d) %s" % (index + 1, statement)
            for index, statement in enumerate(statements)
        ),
        options,
        options[false_index],
        "المعادلة الخاطئة هي: %d + %d = %d، والصحيح هو %d + %d = %d." % (
            equations[false_index]["left"],
            equations[false_index]["right"],
            equations[false_index]["shown"],
            equations[false_index]["left"],
            equations[false_index]["right"],
            equations[false_index]["correct"],
        ),
        mode="bluff",
    )


def _prediction() -> Dict[str, Any]:
    first_die, second_die = _random_int(1, 6), _random_int(1, 6)
    total = first_die + second_die
    distractors = []
    for candidate in (total - 2, total + 2, total - 1, total + 1):
        if 2 <= candidate <= 12 and candidate != total and candidate not in distractors:
            distractors.append(candidate)
        if len(distractors) == 2:
            break
    while len(distractors) < 2:
        candidate = _random_int(2, 12)
        if candidate != total and candidate not in distractors:
            distractors.append(candidate)
    options = [str(total)] + [str(value) for value in distractors]
    secrets.SystemRandom().shuffle(options)
    return _make_challenge(
        "توقّع وحظ",
        "توقّع مجموع النرد",
        "جهّز الخادم رمية نردين من 1 إلى 6. توقّع مجموع النردين قبل كشفهما.",
        options,
        str(total),
        "كانت النردتان %d و%d؛ ومجموعهما %d." % (first_die, second_die, total),
        mode="prediction",
    )


def _duel() -> Dict[str, Any]:
    challenge = _addition()
    challenge["mode"] = "duel"
    challenge["mode_label"] = MODE_DETAILS["duel"]["label"]
    challenge["mode_description"] = MODE_DETAILS["duel"]["description"]
    challenge["family"] = "مواجهة حسابية"
    challenge["title"] = "تحدّ وجهًا لوجه"
    challenge["explanation"] = (
        "الإجابة الصحيحة تحسم المواجهة. الفائز وحده يحصل على 3 عملات، "
        "وإذا أصاب اللاعبان يحصل كل واحد على عملتين."
    )
    return challenge


_BASE_GENERATORS = (
    _addition,
    _subtraction,
    _multiplication,
    _sequence,
    _clock,
    _memory,
    _odd_one_out,
    _comparison,
)

_MODE_GENERATORS = {
    "bluff": _bluff,
    "prediction": _prediction,
    "duel": _duel,
}


def generate_challenge(player_count: int = 3, mode: str = None) -> Dict[str, Any]:
    """Generate a family challenge; duels are only available with four players."""
    if player_count not in (3, 4):
        raise ValueError("Challenge generation requires three or four players.")

    if mode == "quiz" or mode is None:
        generators = list(_BASE_GENERATORS)
        if mode == "quiz":
            generator = secrets.choice(generators)
            return generator()
        generators.extend((_bluff, _prediction))
        if player_count == 4:
            generators.append(_duel)
        return secrets.choice(generators)()

    generator = _MODE_GENERATORS.get(mode)
    if generator is None:
        raise ValueError("Unknown challenge mode: %s" % mode)
    if mode == "duel" and player_count != 4:
        raise ValueError("A duel challenge requires exactly four players.")
    return generator()
