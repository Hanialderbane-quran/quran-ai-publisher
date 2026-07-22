"""
Quran AI Publisher
Professional Quran SEO Engine
Version 2.0

Creates respectful Quran titles, descriptions,
hashtags and tags for Shorts and long videos.
"""

import random


SHORT_TITLE_TEMPLATES = [
    "تلاوة مؤثرة من سورة {surah} | الآيات {ayah_range}",
    "آيات تريح القلب من سورة {surah} | قرآن كريم",
    "استمع بقلبك | سورة {surah} الآيات {ayah_range}",
    "تلاوة هادئة من سورة {surah} | قرآن كريم",
    "آيات مباركة من سورة {surah} | {ayah_range}"
]

LONG_TITLE_TEMPLATES = [
    "سورة {surah} | الآيات {ayah_range} | تلاوة هادئة",
    "تلاوة مباركة من سورة {surah} | الآيات {ayah_range}",
    "استمع إلى سورة {surah} | من الآية {start} إلى الآية {end}",
    "قرآن كريم بصوت خاشع | سورة {surah} الآيات {ayah_range}",
    "تلاوة طويلة من سورة {surah} | راحة وطمأنينة"
]


def get_ayah_range(
    segment: dict
) -> str:
    start_ayah = int(
        segment["start_ayah"]
    )

    end_ayah = int(
        segment["end_ayah"]
    )

    if start_ayah == end_ayah:
        return str(start_ayah)

    return (
        f"{start_ayah}–{end_ayah}"
    )


def generate_title(
    segment: dict
) -> str:
    video_type = segment.get(
        "video_type",
        "short"
    )

    templates = (
        LONG_TITLE_TEMPLATES
        if video_type == "long"
        else SHORT_TITLE_TEMPLATES
    )

    template = random.choice(
        templates
    )

    title = template.format(
        surah=segment["surah"],
        ayah_range=get_ayah_range(
            segment
        ),
        start=segment["start_ayah"],
        end=segment["end_ayah"]
    )

    return title[:100]


def generate_description(
    segment: dict
) -> str:
    surah = segment["surah"]
    ayah_range = get_ayah_range(
        segment
    )

    video_type = segment.get(
        "video_type",
        "short"
    )

    ayah_count = segment.get(
        "ayah_count",
        1
    )

    if video_type == "long":
        format_text = (
            "تلاوة قرآنية طويلة وهادئة"
        )

        hashtags = (
            "#القرآن_الكريم #قرآن "
            "#تلاوة #سورة_"
            f"{surah.replace(' ', '_')}"
        )

    else:
        format_text = (
            "مقطع قرآني قصير بتلاوة هادئة"
        )

        hashtags = (
            "#القرآن_الكريم #قرآن "
            "#تلاوة #Shorts"
        )

    return f"""بسم الله الرحمن الرحيم

📖 سورة {surah}
📍 الآيات: {ayah_range}
📚 عدد الآيات في المقطع: {ayah_count}

{format_text} من كتاب الله عز وجل.

نسأل الله أن يجعل القرآن الكريم ربيع قلوبنا، ونور صدورنا، وجلاء أحزاننا.

يمكنك مشاركة المقطع لتعم الفائدة، والاشتراك في القناة لمتابعة تلاوات القرآن الكريم.

تنبيه:
النص الظاهر في الفيديو من القرآن الكريم، وقد صُمم المقطع بأسلوب هادئ يحافظ على وضوح الآيات واحترامها.

{hashtags}
"""


def generate_tags(
    segment: dict
) -> list[str]:
    surah = segment["surah"]

    tags = [
        "القرآن الكريم",
        "قرآن كريم",
        "تلاوة القرآن",
        "تلاوة خاشعة",
        "تلاوة هادئة",
        "آيات من القرآن",
        f"سورة {surah}",
        surah,
        "Quran",
        "Holy Quran",
        "Quran recitation",
        "Islam",
        "ذكر الله"
    ]

    if segment.get(
        "video_type"
    ) == "short":
        tags.extend(
            [
                "Shorts",
                "قرآن شورتس",
                "مقاطع قرآنية قصيرة"
            ]
        )
    else:
        tags.extend(
            [
                "تلاوة طويلة",
                "سورة كاملة",
                "الاستماع للقرآن"
            ]
        )

    return tags


def build_seo(
    segment: dict
) -> dict:
    if not isinstance(
        segment,
        dict
    ):
        raise RuntimeError(
            "SEO content must be a Quran segment."
        )

    required_fields = [
        "surah",
        "start_ayah",
        "end_ayah",
        "video_type"
    ]

    for field in required_fields:
        if field not in segment:
            raise RuntimeError(
                "SEO segment is missing: "
                f"{field}"
            )

    return {
        "title": generate_title(
            segment
        ),
        "description": generate_description(
            segment
        ),
        "tags": generate_tags(
            segment
        ),
        "category_id": "27",
        "language": "ar",
        "made_for_kids": False,
        "privacy_status": "private"
    }
