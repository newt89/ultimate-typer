#!/usr/bin/env python3
"""Ultimate Typer — Backend API
Languages: English, Russian, Arabic (Quran), Sanskrit (Bhagavad Gita + Home Row)
"""
import os, re, time, sqlite3, unicodedata
from pathlib import Path
from flask import Flask, jsonify, request, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "sessions.db"

# ── Arabic normalisation ───────────────────────────────────────────────────────
_RE_DIAC = re.compile(
    r'[\u0610-\u061A\u064B-\u065F\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]')

def deep_norm_ar(text):
    if not text: return text
    text = unicodedata.normalize("NFKC", text)
    text = text.replace('\u0670', '\u0627')
    text = _RE_DIAC.sub("", text)
    text = re.sub(r'\u0640', '', text)
    text = re.sub(r'[\u200B-\u200F\u202A-\u202E\uFEFF]', '', text)
    text = re.sub(r'[\u0622\u0623\u0625\u0671-\u0675]', '\u0627', text)
    text = re.sub(r'\u0629', '\u0647', text)
    text = re.sub(r'[\u0649\u06CC\u0626]', '\u064A', text)
    text = re.sub(r'\u06A9', '\u0643', text)
    text = re.sub(r'[\u06BE\u06C1\u06C0]', '\u0647', text)
    text = re.sub(r'\u0624', '\u0648', text)
    text = re.sub(r'[\u0621\u0654\u0655]', '', text)
    return unicodedata.normalize("NFC", text)

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(str(DB_PATH))
        g.db.row_factory = sqlite3.Row
        g.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    DEFAULT 'anonymous',
                language    TEXT    NOT NULL,
                prompt_name TEXT,
                wpm         REAL,
                avg_wpm     REAL,
                accuracy    REAL,
                chars_typed INTEGER,
                words_typed INTEGER,
                errors      INTEGER,
                duration    REAL,
                created_at  REAL    DEFAULT (unixepoch())
            );
        """)
        g.db.commit()
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

# ── Text content ──────────────────────────────────────────────────────────────
ENGLISH_TEXTS = {
    "pangrams": (
        "The quick brown fox jumps over the lazy dog. "
        "Pack my box with five dozen liquor jugs. "
        "How vexingly quick daft zebras jump. "
        "Sphinx of black quartz judge my vow. "
        "The five boxing wizards jump quickly."
    ),
    "home_row": (
        "asdf jkl; asdf jkl; add all fall hall sad fad lad "
        "flask glad flag ask dash flash shall glass salad "
        "false falls flask glass lads fads adds halls flasks "
        "glad flags asks dashes flashes shalls glasses salads"
    ),
    "common_words": (
        "the be to of and a in that have it for not on with he as you do at "
        "this but his by from they we say her she or an will my one all would "
        "there their what so up out if about who get which go me when make can "
        "like time no just him know take people into year your good some could "
        "them see other than then now look only come its over think also back "
        "after use two how our work first well way even new want because any "
        "these give day most us great between need large often hand high place "
        "hold cause across air young gold long though open seem together next"
    ),
}

RUSSIAN_TEXTS = {
    "basics": (
        "привет мир как дела хорошо спасибо пожалуйста "
        "да нет может быть конечно понятно хорошо "
        "доброе утро добрый день добрый вечер спокойной ночи "
        "меня зовут рад познакомиться как вас зовут"
    ),
    "home_row": (
        "фыва олдж фыва олдж фыва олдж фыва олдж "
        "вол два жало дол лов фол жов вал "
        "фол вол жол дол ало дал жал вал дав "
        "ловля дольше жалоба овладеть давление"
    ),
    "pushkin": (
        "я вас любил любовь ещё быть может "
        "в душе моей угасла не совсем "
        "но пусть она вас больше не тревожит "
        "я не хочу печалить вас ничем "
        "я вас любил безмолвно безнадежно "
        "то робостью то ревностью томим "
        "я вас любил так искренно так нежно "
        "как дай вам бог любимой быть другим"
    ),
    "tolstoy": (
        "все счастливые семьи похожи друг на друга "
        "каждая несчастливая семья несчастлива по своему "
        "все смешалось в доме облонских "
        "жена узнала что муж был в связи "
        "с бывшею в их доме француженкою гувернанткою "
        "и объявила мужу что не может жить с ним в одном доме"
    ),
}

ARABIC_TEXTS = {
    "al_fatiha": (
        "بسم الله الرحمن الرحيم "
        "الحمد لله رب العالمين "
        "الرحمن الرحيم "
        "مالك يوم الدين "
        "اياك نعبد واياك نستعين "
        "اهدنا الصراط المستقيم "
        "صراط الذين انعمت عليهم "
        "غير المغضوب عليهم ولا الضالين"
    ),
    "al_ikhlas": (
        "بسم الله الرحمن الرحيم "
        "قل هو الله احد "
        "الله الصمد "
        "لم يلد ولم يولد "
        "ولم يكن له كفوا احد"
    ),
    "al_nas": (
        "بسم الله الرحمن الرحيم "
        "قل اعوذ برب الناس "
        "ملك الناس "
        "اله الناس "
        "من شر الوسواس الخناس "
        "الذي يوسوس في صدور الناس "
        "من الجنة والناس"
    ),
    "al_falaq": (
        "بسم الله الرحمن الرحيم "
        "قل اعوذ برب الفلق "
        "من شر ما خلق "
        "ومن شر غاسق اذا وقب "
        "ومن شر النفاثات في العقد "
        "ومن شر حاسد اذا حسد"
    ),
    "al_baqarah_1": (
        "الم ذلك الكتاب لا ريب فيه هدى للمتقين "
        "الذين يؤمنون بالغيب ويقيمون الصلاة "
        "ومما رزقناهم ينفقون "
        "والذين يؤمنون بما انزل اليك "
        "وما انزل من قبلك "
        "وبالاخرة هم يوقنون "
        "اولئك على هدى من ربهم "
        "واولئك هم المفلحون"
    ),
}

# Bhagavad Gita — key shlokas per chapter in Devanagari
GITA = {
    1: {
        "name": "अर्जुन विषाद योग",
        "name_en": "Arjuna Vishada Yoga — The Grief of Arjuna",
        "verses": [
            "धृतराष्ट्र उवाच धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय",
            "दृष्ट्वा तु पाण्डवानीकं व्यूढं दुर्योधनस्तदा आचार्यमुपसङ्गम्य राजा वचनमब्रवीत्",
            "अर्जुन उवाच सेनयोरुभयोर्मध्ये रथं स्थापय मेऽच्युत यावदेतान्निरीक्षेऽहं योद्धुकामानवस्थितान्",
        ]
    },
    2: {
        "name": "सांख्य योग",
        "name_en": "Sankhya Yoga — Transcendent Knowledge",
        "verses": [
            "श्रीभगवानुवाच कुतस्त्वा कश्मलमिदं विषमे समुपस्थितम् अनार्यजुष्टमस्वर्ग्यमकीर्तिकरमर्जुन",
            "क्लैब्यं मा स्म गमः पार्थ नैतत्त्वय्युपपद्यते क्षुद्रं हृदयदौर्बल्यं त्यक्त्वोत्तिष्ठ परन्तप",
            "नैनं छिन्दन्ति शस्त्राणि नैनं दहति पावकः न चैनं क्लेदयन्त्यापो न शोषयति मारुतः",
            "अव्यक्तोऽयमचिन्त्योऽयमविकार्योऽयमुच्यते तस्मादेवं विदित्वैनं नानुशोचितुमर्हसि",
            "नित्यस्य उक्तः शरीरस्य नान्तः क्षयोऽस्ति तस्मात्सर्वाणि भूतानि न त्वं शोचितुमर्हसि",
        ]
    },
    3: {
        "name": "कर्म योग",
        "name_en": "Karma Yoga — The Yoga of Action",
        "verses": [
            "नियतं कुरु कर्म त्वं कर्म ज्यायो ह्यकर्मणः शरीरयात्रापि च ते न प्रसिद्ध्येदकर्मणः",
            "यज्ञार्थात्कर्मणोऽन्यत्र लोकोऽयं कर्मबन्धनः तदर्थं कर्म कौन्तेय मुक्तसङ्गः समाचर",
            "श्रेयान्स्वधर्मो विगुणः परधर्मात्स्वनुष्ठितात् स्वधर्मे निधनं श्रेयः परधर्मो भयावहः",
        ]
    },
    4: {
        "name": "ज्ञान कर्म संन्यास योग",
        "name_en": "Jnana Karma Sanyasa Yoga — The Path of Knowledge",
        "verses": [
            "इमं विवस्वते योगं प्रोक्तवानहमव्ययम् विवस्वान्मनवे प्राह मनुरिक्ष्वाकवेऽब्रवीत्",
            "यदा यदा हि धर्मस्य ग्लानिर्भवति भारत अभ्युत्थानमधर्मस्य तदात्मानं सृजाम्यहम्",
            "परित्राणाय साधूनां विनाशाय च दुष्कृताम् धर्मसंस्थापनार्थाय सम्भवामि युगे युगे",
        ]
    },
    5: {
        "name": "कर्म संन्यास योग",
        "name_en": "Karma Sanyasa Yoga — Renunciation of Action",
        "verses": [
            "सर्वकर्माणि मनसा संन्यस्यास्ते सुखं वशी नवद्वारे पुरे देही नैव कुर्वन्न कारयन्",
            "ब्रह्मण्याधाय कर्माणि सङ्गं त्यक्त्वा करोति यः लिप्यते न स पापेन पद्मपत्रमिवाम्भसा",
        ]
    },
    6: {
        "name": "ध्यान योग",
        "name_en": "Dhyana Yoga — Meditation",
        "verses": [
            "उद्धरेदात्मनात्मानं नात्मानमवसादयेत् आत्मैव ह्यात्मनो बन्धुरात्मैव रिपुरात्मनः",
            "बन्धुरात्मात्मनस्तस्य येनात्मैवात्मना जितः अनात्मनस्तु शत्रुत्वे वर्तेतात्मैव शत्रुवत्",
            "योगस्थः कुरु कर्माणि सङ्गं त्यक्त्वा धनञ्जय सिद्ध्यसिद्ध्योः समो भूत्वा समत्वं योग उच्यते",
        ]
    },
    7: {
        "name": "ज्ञान विज्ञान योग",
        "name_en": "Jnana Vijnana Yoga — Knowledge and Wisdom",
        "verses": [
            "मनुष्याणां सहस्रेषु कश्चिद्यतति सिद्धये यततामपि सिद्धानां कश्चिन्मां वेत्ति तत्त्वतः",
            "भूमिरापोऽनलो वायुः खं मनो बुद्धिरेव च अहङ्कार इतीयं मे भिन्ना प्रकृतिरष्टधा",
        ]
    },
    8: {
        "name": "अक्षर ब्रह्म योग",
        "name_en": "Aksara Brahma Yoga — The Eternal Godhead",
        "verses": [
            "अन्तकाले च मामेव स्मरन्मुक्त्वा कलेवरम् यः प्रयाति स मद्भावं याति नास्त्यत्र संशयः",
        ]
    },
    9: {
        "name": "राज विद्या योग",
        "name_en": "Raja Vidya Yoga — The Royal Path",
        "verses": [
            "पत्रं पुष्पं फलं तोयं यो मे भक्त्या प्रयच्छति तदहं भक्त्युपहृतमश्नामि प्रयतात्मनः",
            "यत्करोषि यदश्नासि यज्जुहोषि ददासि यत् यत्तपस्यसि कौन्तेय तत्कुरुष्व मदर्पणम्",
        ]
    },
    10: {
        "name": "विभूति योग",
        "name_en": "Vibhuti Yoga — Divine Manifestations",
        "verses": [
            "अहमात्मा गुडाकेश सर्वभूताशयस्थितः अहमादिश्च मध्यं च भूतानामन्त एव च",
        ]
    },
    11: {
        "name": "विश्वरूप दर्शन योग",
        "name_en": "Vishwarupa Darshana Yoga — The Cosmic Vision",
        "verses": [
            "अर्जुन उवाच मदनुग्रहाय परमं गुह्यमध्यात्मसञ्ज्ञितम् यत्त्वयोक्तं वचस्तेन मोहोऽयं विगतो मम",
            "दिव्यमाल्याम्बरधरं दिव्यगन्धानुलेपनम् सर्वाश्चर्यमयं देवमनन्तं विश्वतोमुखम्",
        ]
    },
    12: {
        "name": "भक्ति योग",
        "name_en": "Bhakti Yoga — The Path of Devotion",
        "verses": [
            "मय्येव मन आधत्स्व मयि बुद्धिं निवेशय निवसिष्यसि मय्येव अत ऊर्ध्वं न संशयः",
            "अद्वेष्टा सर्वभूतानां मैत्रः करुण एव च निर्ममो निरहङ्कारः समदुःखसुखः क्षमी",
        ]
    },
    13: {
        "name": "क्षेत्र क्षेत्रज्ञ योग",
        "name_en": "Kshetra Kshetragya Yoga — The Field and Its Knower",
        "verses": [
            "इदं शरीरं कौन्तेय क्षेत्रमित्यभिधीयते एतद्यो वेत्ति तं प्राहुः क्षेत्रज्ञ इति तद्विदः",
        ]
    },
    14: {
        "name": "गुणत्रय विभाग योग",
        "name_en": "Gunatraya Vibhaga Yoga — The Three Qualities",
        "verses": [
            "सत्त्वं रजस्तम इति गुणाः प्रकृतिसम्भवाः निबध्नन्ति महाबाहो देहे देहिनमव्ययम्",
        ]
    },
    15: {
        "name": "पुरुषोत्तम योग",
        "name_en": "Purushottama Yoga — The Supreme Being",
        "verses": [
            "ऊर्ध्वमूलमधःशाखमश्वत्थं प्राहुरव्ययम् छन्दांसि यस्य पर्णानि यस्तं वेद स वेदवित्",
        ]
    },
    16: {
        "name": "दैवासुर सम्पद् विभाग योग",
        "name_en": "Daivasura Sampad Vibhaga Yoga — Divine and Demonic",
        "verses": [
            "अभयं सत्त्वसंशुद्धिर्ज्ञानयोगव्यवस्थितिः दानं दमश्च यज्ञश्च स्वाध्यायस्तप आर्जवम्",
        ]
    },
    17: {
        "name": "श्रद्धात्रय विभाग योग",
        "name_en": "Shraddhatraya Vibhaga Yoga — Three Kinds of Faith",
        "verses": [
            "त्रिविधा भवति श्रद्धा देहिनां सा स्वभावजा सात्त्विकी राजसी चैव तामसी चेति तां शृणु",
        ]
    },
    18: {
        "name": "मोक्ष संन्यास योग",
        "name_en": "Moksha Sanyasa Yoga — Liberation through Renunciation",
        "verses": [
            "सर्वधर्मान्परित्यज्य मामेकं शरणं व्रज अहं त्वां सर्वपापेभ्यो मोक्षयिष्यामि मा शुचः",
            "इदं ते नातपस्काय नाभक्ताय कदाचन न चाशुश्रूषवे वाच्यं न च मां योऽभ्यसूयति",
            "य इमं परमं गुह्यं मद्भक्तेष्वभिधास्यति भक्तिं मयि परां कृत्वा मामेवैष्यत्यसंशयः",
        ]
    },
}

# Sanskrit home row levels — Devanagari touch typing trainer
SANSKRIT_LEVELS = {
    "level1": {
        "name": "Level 1 — Home Row Core (क ख ग घ)",
        "desc": "Start with the four most common consonants on home row",
        "words": ["क", "ख", "ग", "घ", "कक", "खख", "गग", "घघ",
                  "कग", "खघ", "गक", "घख", "कखगघ", "घगखक",
                  "कग कग", "खघ खघ", "गक गक", "घख घख"],
    },
    "level2": {
        "name": "Level 2 — Consonants Row 1 (च छ ज झ)",
        "desc": "Next four consonants, building muscle memory",
        "words": ["च", "छ", "ज", "झ", "चच", "छछ", "जज", "झझ",
                  "चज", "छझ", "जच", "झछ", "कचगज", "खछघझ"],
    },
    "level3": {
        "name": "Level 3 — Top Row (ट ठ ड ढ ण)",
        "desc": "Retroflex consonants — reach up",
        "words": ["ट", "ठ", "ड", "ढ", "ण", "टठ", "डढ",
                  "टड", "ठढ", "णट", "कटचड", "गठजढ"],
    },
    "level4": {
        "name": "Level 4 — Dentals (त थ द ध न)",
        "desc": "The dental consonants",
        "words": ["त", "थ", "द", "ध", "न", "तत", "थथ", "दद", "धध", "नन",
                  "तद", "थध", "दत", "धथ", "नत", "तथदधन"],
    },
    "level5": {
        "name": "Level 5 — Labials (प फ ब भ म)",
        "desc": "Labial consonants",
        "words": ["प", "फ", "ब", "भ", "म", "पप", "फफ", "बब", "भभ", "मम",
                  "पब", "फभ", "बप", "भफ", "मप", "पफबभम"],
    },
    "level6": {
        "name": "Level 6 — Semi-vowels (य र ल व)",
        "desc": "Semi-vowels and liquid consonants",
        "words": ["य", "र", "ल", "व", "यय", "रर", "लल", "वव",
                  "यर", "लव", "रय", "वल", "यरलव", "वलरय"],
    },
    "level7": {
        "name": "Level 7 — Sibilants & Aspirate (श ष स ह)",
        "desc": "Sibilants and aspirate",
        "words": ["श", "ष", "स", "ह", "शश", "षष", "सस", "हह",
                  "शस", "षह", "सश", "हष", "कशगस", "खषघह"],
    },
    "level8": {
        "name": "Level 8 — Vowels (अ आ इ ई)",
        "desc": "The primary vowels",
        "words": ["अ", "आ", "इ", "ई", "अआ", "इई", "अइ", "आई",
                  "अक", "आख", "इग", "ईघ", "कअ", "खआ", "गइ", "घई"],
    },
    "level9": {
        "name": "Level 9 — More Vowels (उ ऊ ए ऐ ओ औ)",
        "desc": "Remaining vowels",
        "words": ["उ", "ऊ", "ए", "ऐ", "ओ", "औ",
                  "उऊ", "एऐ", "ओऔ", "अउ", "आऊ", "इए", "ईऐ",
                  "कु", "खू", "गे", "घै", "चो", "छौ"],
    },
    "level10": {
        "name": "Level 10 — Vowel Marks (Matras)",
        "desc": "Practice vowel combining marks",
        "words": ["का", "कि", "की", "कु", "कू", "के", "कै", "को", "कौ",
                  "रा", "री", "रु", "रे", "रो", "ना", "नि", "नु", "ने",
                  "मा", "मि", "मु", "मे", "मो"],
    },
    "level11": {
        "name": "Level 11 — Common Words",
        "desc": "Basic Sanskrit vocabulary",
        "words": ["नमः", "धर्म", "कर्म", "योग", "भक्ति", "ज्ञान",
                  "सत्य", "अहिंसा", "शान्ति", "आनन्द", "प्रेम",
                  "गुरु", "शिष्य", "वेद", "गीता", "श्लोक"],
    },
    "level12": {
        "name": "Level 12 — Full Sentences",
        "desc": "Complete Sanskrit phrases",
        "words": ["नमस्ते", "सत्यमेव जयते", "अहं ब्रह्मास्मि",
                  "तत्त्वमसि", "सर्वे भवन्तु सुखिनः",
                  "ॐ शान्तिः शान्तिः शान्तिः"],
    },
}

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/api/languages')
def get_languages():
    return jsonify([
        {"id": "english",  "name": "English",  "flag": "🇬🇧", "dir": "ltr",
         "script": "Latin", "desc": "Pangrams · Home row · Common words"},
        {"id": "russian",  "name": "Русский",  "flag": "🇷🇺", "dir": "ltr",
         "script": "Cyrillic", "desc": "Basics · Pushkin · Tolstoy"},
        {"id": "arabic",   "name": "العربية",   "flag": "🕌", "dir": "rtl",
         "script": "Arabic", "desc": "Quran — Al-Fatiha · Al-Ikhlas · An-Nas · Al-Falaq"},
        {"id": "sanskrit", "name": "संस्कृतम्", "flag": "🕉️",  "dir": "ltr",
         "script": "Devanagari", "desc": "Bhagavad Gita · Home Row Trainer"},
    ])

@app.route('/api/prompts/<lang>')
def get_prompts(lang):
    if lang == "english":
        return jsonify([
            {"id": "pangrams",     "name": "Pangrams",         "type": "text",    "words": None},
            {"id": "home_row",     "name": "Home Row Drill",   "type": "trainer", "words": None},
            {"id": "common_words", "name": "1000 Common Words","type": "text",    "words": None},
        ])
    if lang == "russian":
        return jsonify([
            {"id": "basics",   "name": "Basics & Greetings",    "type": "text",    "words": None},
            {"id": "home_row", "name": "Home Row (ФЫВА ОЛДЖ)",  "type": "trainer", "words": None},
            {"id": "pushkin",  "name": "Pushkin — Я вас любил", "type": "literature", "words": None},
            {"id": "tolstoy",  "name": "Tolstoy — Anna Karenina","type": "literature","words": None},
        ])
    if lang == "arabic":
        return jsonify([
            {"id": "al_fatiha",    "name": "سورة الفاتحة — Al-Fatiha",    "type": "quran", "words": None},
            {"id": "al_ikhlas",    "name": "سورة الإخلاص — Al-Ikhlas",   "type": "quran", "words": None},
            {"id": "al_nas",       "name": "سورة الناس — An-Nas",         "type": "quran", "words": None},
            {"id": "al_falaq",     "name": "سورة الفلق — Al-Falaq",       "type": "quran", "words": None},
            {"id": "al_baqarah_1", "name": "سورة البقرة — Al-Baqarah (1)","type": "quran", "words": None},
        ])
    if lang == "sanskrit":
        prompts = []
        # Home row trainer levels
        for lid, lvl in SANSKRIT_LEVELS.items():
            prompts.append({"id": f"train_{lid}", "name": lvl["name"],
                            "type": "trainer", "desc": lvl["desc"]})
        # Gita chapters
        prompts.append({"id": "gita_all", "name": "भगवद्गीता — All 18 Chapters",
                        "type": "gita", "desc": "Complete Bhagavad Gita"})
        for ch, data in GITA.items():
            prompts.append({
                "id":   f"gita_{ch}",
                "name": f"Ch.{ch} — {data['name_en']}",
                "type": "gita",
                "desc": data['name'],
            })
        # Multi-chapter ranges
        prompts.append({"id": "gita_1_6",  "name": "Gita Chapters 1–6 (Karma Kanda)",
                        "type": "gita", "desc": "Action and Duty"})
        prompts.append({"id": "gita_7_12", "name": "Gita Chapters 7–12 (Bhakti Kanda)",
                        "type": "gita", "desc": "Devotion and Knowledge"})
        prompts.append({"id": "gita_13_18","name": "Gita Chapters 13–18 (Jnana Kanda)",
                        "type": "gita", "desc": "Liberation"})
        return jsonify(prompts)
    return jsonify([])

@app.route('/api/words', methods=['POST'])
def get_words():
    data      = request.json or {}
    lang      = data.get('lang', 'english')
    prompt_id = data.get('prompt_id', '')

    words = []
    direction = 'ltr'

    if lang == 'english':
        raw = ENGLISH_TEXTS.get(prompt_id, ENGLISH_TEXTS['pangrams'])
        words = raw.split()

    elif lang == 'russian':
        raw = RUSSIAN_TEXTS.get(prompt_id, RUSSIAN_TEXTS['basics'])
        words = raw.split()

    elif lang == 'arabic':
        direction = 'rtl'
        raw = ARABIC_TEXTS.get(prompt_id, ARABIC_TEXTS['al_fatiha'])
        # Strip diacritics then deep-normalise each word
        raw = _RE_DIAC.sub('', raw)
        words = [deep_norm_ar(w) for w in raw.split() if w]

    elif lang == 'sanskrit':
        if prompt_id.startswith('train_'):
            level_id = prompt_id[6:]   # strip 'train_'
            lvl = SANSKRIT_LEVELS.get(level_id, SANSKRIT_LEVELS['level1'])
            # Expand word list for training (repeat + shuffle)
            base = lvl['words'] * 6
            import random; random.shuffle(base)
            words = base[:60]
        elif prompt_id == 'gita_all':
            verses = []
            for ch in GITA.values():
                verses.extend(ch['verses'])
            words = ' '.join(verses).split()
        elif prompt_id == 'gita_1_6':
            verses = []
            for ch in range(1, 7):
                verses.extend(GITA[ch]['verses'])
            words = ' '.join(verses).split()
        elif prompt_id == 'gita_7_12':
            verses = []
            for ch in range(7, 13):
                verses.extend(GITA[ch]['verses'])
            words = ' '.join(verses).split()
        elif prompt_id == 'gita_13_18':
            verses = []
            for ch in range(13, 19):
                verses.extend(GITA[ch]['verses'])
            words = ' '.join(verses).split()
        elif prompt_id.startswith('gita_'):
            try:
                ch_num = int(prompt_id[5:])
                ch = GITA.get(ch_num, GITA[1])
                words = ' '.join(ch['verses']).split()
            except (ValueError, KeyError):
                words = ' '.join(GITA[1]['verses']).split()
        else:
            lvl = SANSKRIT_LEVELS['level1']
            words = lvl['words'] * 6

    return jsonify({"lang": lang, "words": words, "dir": direction})

@app.route('/api/session', methods=['POST'])
def save_session():
    d  = request.json or {}
    db = get_db()
    db.execute(
        "INSERT INTO sessions (username,language,prompt_name,wpm,avg_wpm,"
        "accuracy,chars_typed,words_typed,errors,duration) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (d.get('username','anonymous'), d.get('lang',''), d.get('prompt_name',''),
         d.get('wpm',0), d.get('avg_wpm',0), d.get('accuracy',100),
         d.get('chars_typed',0), d.get('words_typed',0),
         d.get('errors',0), d.get('duration',0))
    )
    db.commit()
    return jsonify({"ok": True})

@app.route('/api/stats/<lang>')
def get_stats(lang):
    db   = get_db()
    rows = db.execute(
        "SELECT wpm,avg_wpm,accuracy,words_typed,duration,prompt_name,errors,created_at "
        "FROM sessions WHERE language=? ORDER BY created_at DESC LIMIT 100", (lang,)
    ).fetchall()
    sessions = [dict(r) for r in rows]
    wpms = [r['wpm'] for r in sessions if r.get('wpm')]
    return jsonify({
        "sessions": sessions,
        "best_wpm":       round(max(wpms), 1) if wpms else 0,
        "avg_wpm":        round(sum(wpms)/len(wpms), 1) if wpms else 0,
        "total_sessions": len(sessions),
        "total_words":    sum(r.get('words_typed',0) for r in sessions),
    })

@app.route('/api/leaderboard')
def leaderboard():
    db   = get_db()
    rows = db.execute(
        "SELECT username,language,MAX(wpm) best_wpm,AVG(accuracy) avg_acc,"
        "COUNT(*) sessions FROM sessions "
        "GROUP BY username,language ORDER BY best_wpm DESC LIMIT 20"
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
