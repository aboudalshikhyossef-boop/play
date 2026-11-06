"""Family-friendly Arabic multiple-choice round challenges.

Content lives outside the match engine so prompts can be reviewed and expanded
without changing settlement logic. The correct option is server-only until the
shared reveal phase.
"""

CHALLENGE_SECONDS = 25
CHALLENGE_REWARD = 2

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
