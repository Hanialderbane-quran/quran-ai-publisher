"""
Quran AI Publisher
SEO Engine
Version: 1.0
"""


def generate_title(verse):
    return f"{verse['surah']} | الآية {verse['ayah']} | قرآن كريم"


def generate_description(verse):
    return f"""📖 {verse['surah']} - الآية {verse['ayah']}

استمع إلى تلاوة عطرة من القرآن الكريم.

🌿 لا تنس الاشتراك في القناة وتفعيل الجرس.

#القرآن_الكريم
#قرآن
#Quran
#Shorts
"""


def generate_tags():
    return [
        "القرآن الكريم",
        "قرآن",
        "Quran",
        "Islam",
        "Shorts",
        "تلاوة",
        "آيات",
        "ذكر",
        "سورة"
    ]


def build_seo(verse):
    return {
        "title": generate_title(verse),
        "description": generate_description(verse),
        "tags": generate_tags()
    }
