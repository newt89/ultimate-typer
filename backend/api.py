#!/usr/bin/env python3
"""Ultimate Typer Backend API v3.0 — 100+ Books, Login, 114 Surahs, Russian, Sanskrit"""
import os, re, time, sqlite3, unicodedata, json, threading, hashlib
from pathlib import Path
from urllib.request import urlopen, Request
from flask import Flask, jsonify, request, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_DIR  = Path(os.environ.get("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH   = DATA_DIR / "sessions.db"
BOOKS_DIR = DATA_DIR / "books"
BOOKS_DIR.mkdir(parents=True, exist_ok=True)

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

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(str(DB_PATH))
        g.db.row_factory = sqlite3.Row
        g.db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at REAL DEFAULT (unixepoch())
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT DEFAULT 'anonymous',
                language TEXT NOT NULL, prompt_name TEXT,
                wpm REAL, avg_wpm REAL, accuracy REAL,
                chars_typed INTEGER, words_typed INTEGER,
                errors INTEGER, duration REAL,
                created_at REAL DEFAULT (unixepoch())
            );
        """)
        g.db.commit()
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()

@app.route('/api/signup', methods=['POST'])
def signup():
    d  = request.json or {}
    u  = (d.get('username') or '').strip()[:30]
    pw = (d.get('password') or '').strip()
    if not u or not pw or len(pw) < 4:
        return jsonify({"ok": False, "error": "Username and password (min 4 chars) required"}), 400
    try:
        get_db().execute("INSERT INTO users (username,password) VALUES (?,?)", (u, _hash(pw)))
        get_db().commit()
        return jsonify({"ok": True, "username": u})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "Username already taken"}), 409

@app.route('/api/login', methods=['POST'])
def login():
    d  = request.json or {}
    u  = (d.get('username') or '').strip()
    pw = (d.get('password') or '').strip()
    row = get_db().execute("SELECT username FROM users WHERE username=? AND password=?",
                           (u, _hash(pw))).fetchone()
    if row: return jsonify({"ok": True, "username": row['username']})
    return jsonify({"ok": False, "error": "Wrong username or password"}), 401

# ── Gutenberg books ───────────────────────────────────────────────────────────
GUTENBERG = {
    "Pride and Prejudice":("1342","Austen"),"Sense and Sensibility":("161","Austen"),
    "Emma":("158","Austen"),"Persuasion":("105","Austen"),
    "Northanger Abbey":("121","Austen"),"Mansfield Park":("141","Austen"),
    "Bleak House":("1023","Dickens"),"The Pickwick Papers":("580","Dickens"),
    "Little Dorrit":("963","Dickens"),"Nicholas Nickleby":("967","Dickens"),
    "The Old Curiosity Shop":("700","Dickens"),"A Tale of Two Cities":("98","Dickens"),
    "Great Expectations":("1400","Dickens"),"David Copperfield":("766","Dickens"),
    "Oliver Twist":("730","Dickens"),"Dombey and Son":("821","Dickens"),
    "Moby Dick":("2701","Melville"),"Bartleby the Scrivener":("11231","Melville"),
    "Billy Budd":("9798","Melville"),"Typee":("1900","Melville"),
    "Tom Sawyer":("74","Twain"),"Huckleberry Finn":("76","Twain"),
    "The Prince and the Pauper":("1837","Twain"),"A Connecticut Yankee":("86","Twain"),
    "The Innocents Abroad":("3176","Twain"),
    "The Time Machine":("35","Wells"),"The War of the Worlds":("36","Wells"),
    "The Invisible Man":("5230","Wells"),"Island of Doctor Moreau":("159","Wells"),
    "The First Men in the Moon":("1013","Wells"),"The Food of the Gods":("11870","Wells"),
    "Twenty Thousand Leagues":("164","Verne"),"Journey to the Center":("183","Verne"),
    "Around the World in 80 Days":("103","Verne"),"From the Earth to the Moon":("83","Verne"),
    "The Mysterious Island":("1268","Verne"),"Five Weeks in a Balloon":("3526","Verne"),
    "The Count of Monte Cristo":("1184","Dumas"),"The Three Musketeers":("1257","Dumas"),
    "The Man in the Iron Mask":("2759","Dumas"),"The Black Tulip":("965","Dumas"),
    "Don Quixote":("996","Cervantes"),"Robinson Crusoe":("521","Defoe"),
    "Gulliver's Travels":("829","Swift"),
    "Dracula":("345","Stoker"),"Jewel of Seven Stars":("13","Stoker"),
    "Frankenstein":("84","Shelley"),"The Last Man":("18247","Shelley"),
    "Dr Jekyll and Mr Hyde":("43","Stevenson"),
    "The King in Yellow":("8492","Chambers"),
    "The Yellow Wallpaper":("1952","Gilman"),
    "Treasure Island":("120","Stevenson"),"Kidnapped":("421","Stevenson"),
    "The Black Arrow":("849","Stevenson"),
    "Adventures of Sherlock Holmes":("1661","Doyle"),
    "Memoirs of Sherlock Holmes":("834","Doyle"),
    "Hound of the Baskervilles":("2852","Doyle"),
    "Return of Sherlock Holmes":("108","Doyle"),
    "The Valley of Fear":("3289","Doyle"),
    "The Sign of the Four":("2097","Doyle"),
    "Alice in Wonderland":("11","Carroll"),
    "Through the Looking-Glass":("12","Carroll"),
    "The Secret Garden":("113","Burnett"),"A Little Princess":("146","Burnett"),
    "Little Lord Fauntleroy":("404","Burnett"),
    "Little Women":("514","Alcott"),"Good Wives":("2869","Alcott"),
    "Little Men":("2788","Alcott"),"Jo's Boys":("1420","Alcott"),
    "The Call of the Wild":("215","London"),"White Fang":("910","London"),
    "The Sea-Wolf":("1074","London"),"Martin Eden":("1056","London"),
    "The Scarlet Letter":("25344","Hawthorne"),
    "House of Seven Gables":("77","Hawthorne"),
    "The Legend of Sleepy Hollow":("41","Irving"),
    "The Picture of Dorian Gray":("174","Wilde"),
    "The Importance of Being Earnest":("844","Wilde"),
    "The Canterville Ghost":("14522","Wilde"),
    "Ethan Frome":("4517","Wharton"),"The Age of Innocence":("541","Wharton"),
    "The Wonderful Wizard of Oz":("55","Baum"),"The Marvelous Land of Oz":("54","Baum"),
    "Ozma of Oz":("33361","Baum"),"The Road to Oz":("26624","Baum"),
    "Hamlet":("1524","Shakespeare"),"Romeo and Juliet":("1513","Shakespeare"),
    "Macbeth":("1533","Shakespeare"),"Othello":("1531","Shakespeare"),
    "King Lear":("1532","Shakespeare"),"The Tempest":("23042","Shakespeare"),
    "A Midsummer Night's Dream":("1514","Shakespeare"),
    "The Merchant of Venice":("1515","Shakespeare"),
    "War and Peace":("2600","Tolstoy"),"Anna Karenina":("1399","Tolstoy"),
    "Crime and Punishment":("2554","Dostoevsky"),
    "The Brothers Karamazov":("28054","Dostoevsky"),
    "Les Miserables":("135","Hugo"),
    "The Iliad":("6130","Homer"),"The Odyssey":("1727","Homer"),
    "Paradise Lost":("26","Milton"),
    "Middlemarch":("145","Eliot"),
    "Jane Eyre":("1260","Bronte"),"Wuthering Heights":("768","Bronte"),
    "Tess of the d'Urbervilles":("110","Hardy"),
    "Far from the Madding Crowd":("107","Hardy"),
    "The Mayor of Casterbridge":("143","Hardy"),
}

def _bpath(t): return BOOKS_DIR / f"{re.sub(r'[^\w]','_',t)[:45]}.txt"

def _fetch_gutenberg_words(title, gid, max_words=3000):
    import random
    urls = [
        f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
        f"https://www.gutenberg.org/files/{gid}/{gid}-0.txt",
        f"https://www.gutenberg.org/files/{gid}/{gid}.txt",
        f"https://www.gutenberg.org/ebooks/{gid}.txt.utf-8",
        f"https://gutenberg.pglaf.org/files/{gid}/{gid}-0.txt",
    ]
    for url in urls:
        try:
            req  = Request(url, headers={"User-Agent":"Mozilla/5.0 UltimateTyper/4.0"})
            data = urlopen(req, timeout=30).read().decode("utf-8", errors="replace")
            for m in ["*** START OF THE PROJECT","*** START OF THIS PROJECT","*** START OF THIS"]:
                i = data.find(m)
                if i != -1: data = data[data.find("\n",i)+1:]; break
            for m in ["*** END OF THE PROJECT","*** END OF THIS PROJECT"]:
                i = data.find(m)
                if i != -1: data = data[:i]; break
            text = " ".join(l.strip() for l in data.splitlines() if l.strip())
            if len(text) < 1000: continue
            start = random.randint(0, max(0, len(text) - 30000))
            chunk = text[start:start+30000]
            words = chunk.split()[:max_words]
            for i, w in enumerate(words[:50]):
                if w and w[0].isupper() and len(w) > 1:
                    words = words[i:]; break
            if words:
                try: _bpath(title).write_text(' '.join(words), encoding='utf-8')
                except: pass
                return words
        except Exception:
            continue
    return []

def _dl_book(title, gid):
    p = _bpath(title)
    if p.exists() and p.stat().st_size > 2000: return True
    words = _fetch_gutenberg_words(title, gid, max_words=100000)
    return bool(words)

def _bg_dl():
    for t,(gid,auth) in GUTENBERG.items():
        _dl_book(t, gid); time.sleep(0.4)

threading.Thread(target=_bg_dl, daemon=True).start()

# ── 114 Surahs ────────────────────────────────────────────────────────────────
SURAHS = [
    (1,"الفاتحة","Al-Fatiha",7),(2,"البقرة","Al-Baqara",286),
    (3,"آل عمران","Al-Imran",200),(4,"النساء","An-Nisa",176),
    (5,"المائدة","Al-Maida",120),(6,"الأنعام","Al-Anam",165),
    (7,"الأعراف","Al-Araf",206),(8,"الأنفال","Al-Anfal",75),
    (9,"التوبة","At-Tawba",129),(10,"يونس","Yunus",109),
    (11,"هود","Hud",123),(12,"يوسف","Yusuf",111),
    (13,"الرعد","Ar-Rad",43),(14,"إبراهيم","Ibrahim",52),
    (15,"الحجر","Al-Hijr",99),(16,"النحل","An-Nahl",128),
    (17,"الإسراء","Al-Isra",111),(18,"الكهف","Al-Kahf",110),
    (19,"مريم","Maryam",98),(20,"طه","Ta-Ha",135),
    (21,"الأنبياء","Al-Anbiya",112),(22,"الحج","Al-Hajj",78),
    (23,"المؤمنون","Al-Muminun",118),(24,"النور","An-Nur",64),
    (25,"الفرقان","Al-Furqan",77),(26,"الشعراء","Ash-Shuara",227),
    (27,"النمل","An-Naml",93),(28,"القصص","Al-Qasas",88),
    (29,"العنكبوت","Al-Ankabut",69),(30,"الروم","Ar-Rum",60),
    (31,"لقمان","Luqman",34),(32,"السجدة","As-Sajda",30),
    (33,"الأحزاب","Al-Ahzab",73),(34,"سبأ","Saba",54),
    (35,"فاطر","Fatir",45),(36,"يس","Ya-Sin",83),
    (37,"الصافات","As-Saffat",182),(38,"ص","Sad",88),
    (39,"الزمر","Az-Zumar",75),(40,"غافر","Ghafir",85),
    (41,"فصلت","Fussilat",54),(42,"الشورى","Ash-Shura",53),
    (43,"الزخرف","Az-Zukhruf",89),(44,"الدخان","Ad-Dukhan",59),
    (45,"الجاثية","Al-Jathiya",37),(46,"الأحقاف","Al-Ahqaf",35),
    (47,"محمد","Muhammad",38),(48,"الفتح","Al-Fath",29),
    (49,"الحجرات","Al-Hujurat",18),(50,"ق","Qaf",45),
    (51,"الذاريات","Adh-Dhariyat",60),(52,"الطور","At-Tur",49),
    (53,"النجم","An-Najm",62),(54,"القمر","Al-Qamar",55),
    (55,"الرحمن","Ar-Rahman",78),(56,"الواقعة","Al-Waqia",96),
    (57,"الحديد","Al-Hadid",29),(58,"المجادلة","Al-Mujadila",22),
    (59,"الحشر","Al-Hashr",24),(60,"الممتحنة","Al-Mumtahana",13),
    (61,"الصف","As-Saf",14),(62,"الجمعة","Al-Jumua",11),
    (63,"المنافقون","Al-Munafiqun",11),(64,"التغابن","At-Taghabun",18),
    (65,"الطلاق","At-Talaq",12),(66,"التحريم","At-Tahrim",12),
    (67,"الملك","Al-Mulk",30),(68,"القلم","Al-Qalam",52),
    (69,"الحاقة","Al-Haqqa",52),(70,"المعارج","Al-Maarij",44),
    (71,"نوح","Nuh",28),(72,"الجن","Al-Jinn",28),
    (73,"المزمل","Al-Muzzammil",20),(74,"المدثر","Al-Muddaththir",56),
    (75,"القيامة","Al-Qiyama",40),(76,"الإنسان","Al-Insan",31),
    (77,"المرسلات","Al-Mursalat",50),(78,"النبأ","An-Naba",40),
    (79,"النازعات","An-Naziat",46),(80,"عبس","Abasa",42),
    (81,"التكوير","At-Takwir",29),(82,"الانفطار","Al-Infitar",19),
    (83,"المطففين","Al-Mutaffifin",36),(84,"الانشقاق","Al-Inshiqaq",25),
    (85,"البروج","Al-Buruj",22),(86,"الطارق","At-Tariq",17),
    (87,"الأعلى","Al-Ala",19),(88,"الغاشية","Al-Ghashiya",26),
    (89,"الفجر","Al-Fajr",30),(90,"البلد","Al-Balad",20),
    (91,"الشمس","Ash-Shams",15),(92,"الليل","Al-Layl",21),
    (93,"الضحى","Ad-Duha",11),(94,"الشرح","Ash-Sharh",8),
    (95,"التين","At-Tin",8),(96,"العلق","Al-Alaq",19),
    (97,"القدر","Al-Qadr",5),(98,"البينة","Al-Bayyina",8),
    (99,"الزلزلة","Az-Zalzala",8),(100,"العاديات","Al-Adiyat",11),
    (101,"القارعة","Al-Qaria",11),(102,"التكاثر","At-Takathur",8),
    (103,"العصر","Al-Asr",3),(104,"الهمزة","Al-Humaza",9),
    (105,"الفيل","Al-Fil",5),(106,"قريش","Quraish",4),
    (107,"الماعون","Al-Maun",7),(108,"الكوثر","Al-Kawthar",3),
    (109,"الكافرون","Al-Kafirun",6),(110,"النصر","An-Nasr",3),
    (111,"المسد","Al-Masad",5),(112,"الإخلاص","Al-Ikhlas",4),
    (113,"الفلق","Al-Falaq",5),(114,"الناس","An-Nas",6),
]

ARABIC_BUILTIN = {
    "al_fatiha":          "بسم الله الرحمن الرحيم الحمد لله رب العالمين الرحمن الرحيم مالك يوم الدين اياك نعبد واياك نستعين اهدنا الصراط المستقيم صراط الذين انعمت عليهم غير المغضوب عليهم ولا الضالين",
    "al_ikhlas":          "بسم الله الرحمن الرحيم قل هو الله احد الله الصمد لم يلد ولم يولد ولم يكن له كفوا احد",
    "al_nas":             "بسم الله الرحمن الرحيم قل اعوذ برب الناس ملك الناس اله الناس من شر الوسواس الخناس الذي يوسوس في صدور الناس من الجنة والناس",
    "al_falaq":           "بسم الله الرحمن الرحيم قل اعوذ برب الفلق من شر ما خلق ومن شر غاسق اذا وقب ومن شر النفاثات في العقد ومن شر حاسد اذا حسد",
    "ayat_kursi":         "الله لا اله الا هو الحي القيوم لا تاخذه سنة ولا نوم له ما في السماوات وما في الارض من ذا الذي يشفع عنده الا باذنه يعلم ما بين ايديهم وما خلفهم ولا يحيطون بشيء من علمه الا بما شاء وسع كرسيه السماوات والارض ولا يؤوده حفظهما وهو العلي العظيم",
    "al_baqarah_opening": "الم ذلك الكتاب لا ريب فيه هدى للمتقين الذين يؤمنون بالغيب ويقيمون الصلاة ومما رزقناهم ينفقون والذين يؤمنون بما انزل اليك وما انزل من قبلك وبالاخرة هم يوقنون",
    "al_mulk":            "تبارك الذي بيده الملك وهو على كل شيء قدير الذي خلق الموت والحياة ليبلوكم ايكم احسن عملا وهو العزيز الغفور الذي خلق سبع سماوات طباقا",
    "al_yasin":           "يس والقران الحكيم انك لمن المرسلين على صراط مستقيم تنزيل العزيز الرحيم لتنذر قوما ما انذر اباؤهم فهم غافلون",
    "ar_rahman":          "الرحمن علم القران خلق الانسان علمه البيان الشمس والقمر بحسبان والنجم والشجر يسجدان والسماء رفعها ووضع الميزان",
}

# Arabic classical literature — bundled texts
ARABIC_CLASSICAL = {
    "kalila_wa_dimna":    ("كليلة ودمنة — Kalila wa Dimna", "text",
        "زعموا ان ملكا من ملوك الهند كان له وزير حكيم عاقل يقال له بيدبا وكان هذا الملك يحب الحكمة ويطلبها ويكرم اهلها فسال الوزير ذات يوم ان يضع له كتابا في السياسة والتدبير فوضع له كليلة ودمنة وجعله على السنة البهائم والطير اذ كانوا يعلمون ان الملك يفهم ذلك ويعقله"),
    "muallaqat_imru":     ("معلقة امرئ القيس — Mu'allaqat Imru al-Qays", "poetry",
        "قفا نبك من ذكرى حبيب ومنزل بسقط اللوى بين الدخول فحومل فتوضح فالمقراة لم يعف رسمها لما نسجتها من جنوب وشمال ترى بعر الارآم في عرصاتها وقيعانها كانه حب فلفل كانه ان خرجت من مخدعها يا ابا ثروان ولدت"),
    "muallaqat_zuhair":   ("معلقة زهير — Mu'allaqat Zuhair", "poetry",
        "امن ام اوفى دمنة لم تكلم بحومانة الدراج فالمتثلم ودار لها بالرقمتين كانها مراجع وشم في نواشر معصم بها العين والارآم يمشين خلفة وارآم عين المالح المتوسم"),
    "maqamat_hariri":     ("مقامات الحريري — Maqamat al-Hariri", "text",
        "حدثنا الحارث بن همام قال سافرت في شبيبتي وكنت في ربيع عمري حين كنت احسب الغنى الغنيمة والشباب الغانمة فلما انتهيت في سفري الى البصرة وانقطعت بي النفقة نزلت بالجامع المنسوب الى علي والتمست من يرفدني بما اسد به خلتي"),
    "alf_layla_1":        ("ألف ليلة وليلة — Arabian Nights (1)", "story",
        "يحكى انه كان في قديم الزمان وسالف العصر والاوان ملك من ملوك ساسان في جزائر الهند والصين له جيوش وحشم وخدم وعبيد وجنود وكان له اخ يقال له شاه زمان ملك سمرقند الاعجم فمكث في مملكته يوما من الدهر"),
    "alf_layla_sindbad":  ("ألف ليلة — قصة السندباد البحري", "story",
        "كان في بغداد رجل فقير يحمل الاحمال على رأسه وكان اسمه السندباد الحمال فاتفق انه مر بباب دار رجل عظيم فوجد على الباب كراسي من جريد النخل وعليها جلوس التجار وارباب الاموال ووجد منها رائحة الطعام والشراب وسمع اصوات المغنيات والطنبور"),
    "ibn_battuta_rihla":  ("رحلة ابن بطوطة — Ibn Battuta Travels", "text",
        "بسم الله الرحمن الرحيم وصلى الله على سيدنا محمد وعلى اله وصحبه وسلم قال الشيخ الامام العالم الرحال جامع الاشتات ابو عبدالله محمد بن عبدالله بن محمد بن ابراهيم اللواتي الطنجي ابن بطوطة رضى الله عنه لما تعمر الكعبة المشرفة وزرت قبر الرسول الكريم"),
    "ibn_khaldun_muq":    ("مقدمة ابن خلدون — Ibn Khaldun Muqaddima", "text",
        "ان فن التاريخ من الفنون التي تتداولها الامم والاجيال وتشد اليه الركائب في كل جيل وتسمو الى معرفته السوقة والاغفال وتتنافس فيه الملوك والاقيال ويتساوى في فهمه العلماء والجهال اذ هو في ظاهره لا يزيد على اخبار عن الايام والدول والسوابق من القرون الاول"),
    "mutanabbi_poetry":   ("شعر المتنبي — Al-Mutanabbi Poetry", "poetry",
        "على قدر اهل العزم تاتي العزائم وتاتي على قدر الكرام المكارم وتعظم في عين الصغير صغارها وتصغر في عين العظيم العظائم انا الذي نظر الاعمى الى ادبي واسمعت كلماتي من به صمم الخيل والليل والبيداء تعرفني والسيف والرمح والقرطاس والقلم"),
    "abu_nuwas_poetry":   ("شعر ابي نواس — Abu Nuwas Poetry", "poetry",
        "دع عنك لومي فان اللوم اغراء وداوني بالتي كانت هي الداء صفراء لا تنزل الاحزان ساحتها لو مسها حجر مسته سراء من كف ذات حر كالعقيق يرى في خدها والنهود البيض احساء قامت باداء جواب حين قلت لها هلي مهيا قالت وهي حسناء"),
    "jahiz_bayan":        ("البيان والتبيين — Al-Jahiz", "text",
        "ان احق ما ابتدا به الخطيب في خطبته ومن في مقامه وابدى به القاضي في حكمه ومن في مجلسه ان يعلم ان البيان اسم جامع لكل شيء كشف لك قناع المعنى وهتك الحجاب دون الضمير حتى يفضي السامع الى حقيقته ويهجم على محصوله"),
    "imam_shafii_poetry": ("شعر الامام الشافعي — Imam Shafi'i", "poetry",
        "نعم لا تملك اللذات حرا وكيف تملك اللذات حرا صبرت على المكاره وهي تمضي وما تمضي عليك بها الامورا وما يبقى من الدنيا لحي ولا ما فات منها يعود طورا ومن كانت مطيته الليالي فانه وان ظلم المسيرا"),
    "ghazali_ihya": ("إحياء علوم الدين — Al-Ghazali Ihya", "text",
        "الحمد لله الذي شرح بنور معرفته صدور العارفين وانار ببهجة محبته قلوب المشتاقين وفتح لاهل الانس والمراقبة ابواب الوصول الى دار المقربين"),
    "ibn_battuta_rihla": ("رحلة ابن بطوطة — Ibn Battuta Travels", "text",
        "بسم الله الرحمن الرحيم لما تعمر الكعبة المشرفة وزرت قبر الرسول الكريم خرجت من مدينة طنجة مسقط راسي يوم الخميس ثاني رجب سنة خمس وعشرين وسبعمائة"),
    "nahjul_balagha": ("نهج البلاغة — Nahjul Balagha", "text",
        "الحمد لله الذي لا يبلغه بعد الثناء عليه ولا تحصيه سعة العد الأمد له والمُنتهى عنده ومن إليه المرجع"),
    "maqamat_badi": ("مقامات بديع الزمان — Badi al-Zaman", "text",
        "حدث عيسى بن هشام قال كنت بالبصرة مع صديق لي ونحن نتذاكر الاعراب وامرها والعرب واخبارها اذ وقع بصري على شيخ يلوح عليه النسك"),
}

RUSSIAN_TEXTS = {
    "ru_home_row":       "фыва олдж фыва олдж фыва олдж вол два жало дол лов фол вол жол дол ало дал жал вал дав",
    "ru_basics":         "привет мир как дела хорошо спасибо пожалуйста да нет может быть конечно понятно",
    "ru_pushkin_vy":     "я вас любил любовь ещё быть может в душе моей угасла не совсем но пусть она вас больше не тревожит я не хочу печалить вас ничем я вас любил безмолвно безнадежно то робостью то ревностью томим я вас любил так искренно так нежно как дай вам бог любимой быть другим",
    "ru_pushkin_onegin": "мой дядя самых честных правил когда не в шутку занемог он уважать себя заставил и лучше выдумать не мог его пример другим наука но боже мой какая скука с больным сидеть и день и ночь не отходя ни шагу прочь какое низкое коварство",
    "ru_pushkin_medny":  "на берегу пустынных волн стоял он дум великих полн и вдаль глядел пред ним широко река неслася бедный чёлн по ней стремился одиноко по мшистым топким берегам чернели избы здесь и там приют убогого чухонца",
    "ru_lermontov":      "выхожу один я на дорогу сквозь туман кремнистый путь блестит ночь тиха пустыня внемлет богу и звезда с звездою говорит в небесах торжественно и чудно спит земля в сиянье голубом что же мне так больно и так трудно жду ль чего жалею ли о чём",
    "ru_tolstoy_anna":   "все счастливые семьи похожи друг на друга каждая несчастливая семья несчастлива по своему все смешалось в доме облонских жена узнала что муж был в связи с бывшею в их доме француженкою гувернанткою и объявила мужу что не может жить с ним в одном доме",
    "ru_tolstoy_voina":  "что ж вам всё таки скучно в петербурге нет не скучно отвечала анна павловна но как вам угодно ну что такое сказала анна павловна она умела изречь банальную фразу с значительностью",
    "ru_tolstoy_voskr":  "как ни старались люди собравшись в одно небольшое место несколько сот тысяч изуродовать ту землю на которой они жались как ни забивали камнями землю чтобы ничего не росло на ней",
    "ru_dostoevsky_pre": "в начале июля в чрезвычайно жаркое время под вечер один молодой человек вышел из своей каморки которую нанимал от жильцов в с переулке на улицу и медленно нерешительно направился к к мосту",
    "ru_dostoevsky_idi": "в конце ноября в оттепель часов в девять утра поезд петербургско-варшавской железной дороги на всех парах подходил к петербургу в такое сырое и туманное утро что с трудом можно было различить что-либо",
    "ru_dostoevsky_bra": "алексей фёдорович карамазов был третьим сыном помещика нашего уезда фёдора павловича карамазова столь известного в своё время и до сих пор ещё у нас вспоминаемого по трагической и тёмной гибели своей",
    "ru_chekhov_vishny": "вишнёвый сад продан сегодня весь вишнёвый сад и имение продано с торгов сегодня был аукцион продано лопахину аня купила варя и я пошли в поле а лопахин остался вчера я была на аукционе",
    "ru_chekhov_dama":   "говорили что на набережной появилось новое лицо дама с собачкой дмитрий дмитрич гуров проживший в ялте уже две недели привыкший тут и тоже начавший интересоваться новыми лицами однажды утром увидел на набережной молодую женщину",
    "ru_chekhov_palata": "в больничном дворе стоит небольшой флигель окружённый целым лесом репейника крапивы и дикой конопли флигель этот давно уже не служит своему прямому назначению крыша у него ржавая",
    "ru_gogol_mertvye":  "в ворота гостиницы губернского города н н въехала довольно красивая рессорная небольшая бричка в какой ездят холостяки отставные подполковники штабс-капитаны помещики имеющие около сотни душ",
    "ru_gogol_revizor":  "я пригласил вас господа с тем чтобы сообщить вам пренеприятное известие к нам едет ревизор антон антонович что вы как ревизор да ревизор из петербурга инкогнито и ещё с секретным предписанием",
    "ru_bulgakov":       "однажды весною в час небывало жаркого заката в москве на патриарших прудах появились два гражданина первый из них приблизительно сорокалетний одетый в серенькую летнюю пару был маленького роста брюнет упитанный лысый",
    "ru_turgenev":       "что аркадий николаич сказал николай петрович и усилил шаги ласково отвечал аркадий николай петрович взглянул на своего сына и вдруг что-то в нём защемило нет дело не в сыне заметил он про себя",
    "ru_akhmatova":      "я научилась просто мудро жить смотреть на небо и молиться богу и долго перед вечером бродить чтоб утомить ненужную тревогу когда шуршат в овраге лопухи и никнет гроздь рябины желто-красной",
}

ENGLISH_TEXTS = {
    "Pangrams":          "The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs. How vexingly quick daft zebras jump. Sphinx of black quartz judge my vow. The five boxing wizards jump quickly. Jackdaws love my big sphinx of quartz. How quickly daft jumping zebras vex.",
    "Famous Quotes":     "To be or not to be that is the question whether tis nobler in the mind to suffer the slings and arrows of outrageous fortune. It was the best of times it was the worst of times it was the age of wisdom it was the age of foolishness. Call me Ishmael. It is a truth universally acknowledged that a single man in possession of a good fortune must be in want of a wife. All happy families are alike each unhappy family is unhappy in its own way.",
    "Common Words":      "the be to of and a in that have it for not on with he as you do at this but his by from they we say her she or an will my one all would there their what so up out if about who get which go me when make can like time no just him know take people into year your good some could them see other than then now look only come its over think also back after use two how our work first well way even new want because any these give day most us",
    "Programming":       "function variable return if else while for loop array string boolean integer float class object method import export const let async await promise callback event listener module package library algorithm recursive iteration conditional inheritance polymorphism abstraction encapsulation",
    "Home Row Basics":   "asdf jkl; asdf jkl; add all fall hall sad fad lad flask glad flag ask dash flash shall glass salad false falls flask glass lads fads adds halls",
}

SANSKRIT_TRAINER = {
    "sa_level_1_vowels":   "अ आ इ ई उ ऊ ऋ ए ऐ ओ औ",
    "sa_level_2_ka":       "क ख ग घ ङ कक खख गग कग खघ गक घख",
    "sa_level_3_ca":       "च छ ज झ ञ चज छझ कचगज",
    "sa_level_4_ta":       "ट ठ ड ढ ण त थ द ध न टड थध",
    "sa_level_5_pa":       "प फ ब भ म पब फभ मप",
    "sa_level_6_semi":     "य र ल व श ष स ह",
    "sa_level_7_matras":   "का कि की कु कू के कै को कौ रा री रे ना नि",
    "sa_level_8_words":    "नमः धर्म कर्म योग भक्ति ज्ञान सत्य अहिंसा शान्ति",
    "sa_level_9_phrases":  "नमस्ते सत्यमेव जयते अहं ब्रह्मास्मि ॐ शान्तिः",
    "sa_level_10_gita":    "धर्म कर्म योग सत्य ज्ञान भक्ति मुक्ति शान्ति अर्जुन",
}

GITA = {
    1:{"name_en":"Arjuna Vishada Yoga","verses":["धृतराष्ट्र उवाच धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय","सञ्जय उवाच दृष्ट्वा तु पाण्डवानीकं व्यूढं दुर्योधनस्तदा आचार्यमुपसङ्गम्य राजा वचनमब्रवीत्"]},
    2:{"name_en":"Sankhya Yoga","verses":["श्रीभगवानुवाच कुतस्त्वा कश्मलमिदं विषमे समुपस्थितम्","नैनं छिन्दन्ति शस्त्राणि नैनं दहति पावकः न चैनं क्लेदयन्त्यापो न शोषयति मारुतः","अव्यक्तोऽयमचिन्त्योऽयमविकार्योऽयमुच्यते तस्मादेवं विदित्वैनं नानुशोचितुमर्हसि","क्लैब्यं मा स्म गमः पार्थ नैतत्त्वय्युपपद्यते क्षुद्रं हृदयदौर्बल्यं त्यक्त्वोत्तिष्ठ परन्तप"]},
    3:{"name_en":"Karma Yoga","verses":["नियतं कुरु कर्म त्वं कर्म ज्यायो ह्यकर्मणः","यज्ञार्थात्कर्मणोऽन्यत्र लोकोऽयं कर्मबन्धनः तदर्थं कर्म कौन्तेय मुक्तसङ्गः समाचर","श्रेयान्स्वधर्मो विगुणः परधर्मात्स्वनुष्ठितात् स्वधर्मे निधनं श्रेयः परधर्मो भयावहः"]},
    4:{"name_en":"Jnana Karma Sanyasa Yoga","verses":["यदा यदा हि धर्मस्य ग्लानिर्भवति भारत अभ्युत्थानमधर्मस्य तदात्मानं सृजाम्यहम्","परित्राणाय साधूनां विनाशाय च दुष्कृताम् धर्मसंस्थापनार्थाय सम्भवामि युगे युगे"]},
    5:{"name_en":"Karma Sanyasa Yoga","verses":["सर्वकर्माणि मनसा संन्यस्यास्ते सुखं वशी नवद्वारे पुरे देही नैव कुर्वन्न कारयन्"]},
    6:{"name_en":"Dhyana Yoga","verses":["उद्धरेदात्मनात्मानं नात्मानमवसादयेत् आत्मैव ह्यात्मनो बन्धुरात्मैव रिपुरात्मनः","योगस्थः कुरु कर्माणि सङ्गं त्यक्त्वा धनञ्जय सिद्ध्यसिद्ध्योः समो भूत्वा समत्वं योग उच्यते"]},
    7:{"name_en":"Jnana Vijnana Yoga","verses":["मनुष्याणां सहस्रेषु कश्चिद्यतति सिद्धये यततामपि सिद्धानां कश्चिन्मां वेत्ति तत्त्वतः"]},
    8:{"name_en":"Aksara Brahma Yoga","verses":["अन्तकाले च मामेव स्मरन्मुक्त्वा कलेवरम् यः प्रयाति स मद्भावं याति नास्त्यत्र संशयः"]},
    9:{"name_en":"Raja Vidya Yoga","verses":["पत्रं पुष्पं फलं तोयं यो मे भक्त्या प्रयच्छति तदहं भक्त्युपहृतमश्नामि प्रयतात्मनः","यत्करोषि यदश्नासि यज्जुहोषि ददासि यत् यत्तपस्यसि कौन्तेय तत्कुरुष्व मदर्पणम्"]},
    10:{"name_en":"Vibhuti Yoga","verses":["अहमात्मा गुडाकेश सर्वभूताशयस्थितः अहमादिश्च मध्यं च भूतानामन्त एव च"]},
    11:{"name_en":"Vishwarupa Darshana Yoga","verses":["दिव्यमाल्याम्बरधरं दिव्यगन्धानुलेपनम् सर्वाश्चर्यमयं देवमनन्तं विश्वतोमुखम्"]},
    12:{"name_en":"Bhakti Yoga","verses":["मय्येव मन आधत्स्व मयि बुद्धिं निवेशय निवसिष्यसि मय्येव अत ऊर्ध्वं न संशयः","अद्वेष्टा सर्वभूतानां मैत्रः करुण एव च निर्ममो निरहङ्कारः समदुःखसुखः क्षमी"]},
    13:{"name_en":"Kshetra Kshetragya Yoga","verses":["इदं शरीरं कौन्तेय क्षेत्रमित्यभिधीयते एतद्यो वेत्ति तं प्राहुः क्षेत्रज्ञ इति तद्विदः"]},
    14:{"name_en":"Gunatraya Vibhaga Yoga","verses":["सत्त्वं रजस्तम इति गुणाः प्रकृतिसम्भवाः निबध्नन्ति महाबाहो देहे देहिनमव्ययम्"]},
    15:{"name_en":"Purushottama Yoga","verses":["ऊर्ध्वमूलमधःशाखमश्वत्थं प्राहुरव्ययम् छन्दांसि यस्य पर्णानि यस्तं वेद स वेदवित्"]},
    16:{"name_en":"Daivasura Sampad Vibhaga Yoga","verses":["अभयं सत्त्वसंशुद्धिर्ज्ञानयोगव्यवस्थितिः दानं दमश्च यज्ञश्च स्वाध्यायस्तप आर्जवम्"]},
    17:{"name_en":"Shraddhatraya Vibhaga Yoga","verses":["त्रिविधा भवति श्रद्धा देहिनां सा स्वभावजा सात्त्विकी राजसी चैव तामसी चेति तां शृणु"]},
    18:{"name_en":"Moksha Sanyasa Yoga","verses":["सर्वधर्मान्परित्यज्य मामेकं शरणं व्रज अहं त्वां सर्वपापेभ्यो मोक्षयिष्यामि मा शुचः","य इमं परमं गुह्यं मद्भक्तेष्वभिधास्यति भक्तिं मयि परां कृत्वा मामेवैष्यत्यसंशयः"]},
}

# Sanskrit scriptures beyond the Gita
SANSKRIT_SCRIPTURES = {
    "upanishads_isha": ("ईशावास्योपनिषद् — Isha Upanishad",
        "ईशावास्यमिदम् सर्वं यत्किञ्च जगत्यां जगत् तेन त्यक्तेन भुञ्जीथा मा गृधः कस्य स्विद्धनम् कुर्वन्नेवेह कर्माणि जिजीविषेच्छतम् समाः एवं त्वयि नान्यथेतोऽस्ति न कर्म लिप्यते नरे"),
    "upanishads_kena": ("केनोपनिषद् — Kena Upanishad",
        "केनेषितं पतति प्रेषितं मनः केन प्राणः प्रथमः प्रैति युक्तः केनेषितां वाचमिमां वदन्ति चक्षुः श्रोत्रं क उ देवो युनक्ति श्रोत्रस्य श्रोत्रं मनसो मनो यद्वाचो ह वाचं स उ प्राणस्य प्राणः चक्षुषश्चक्षुरतिमुच्य धीराः"),
    "upanishads_mandukya": ("माण्डूक्योपनिषद् — Mandukya Upanishad",
        "ॐ इत्येतदक्षरमिदम् सर्वम् तस्योपव्याख्यानम् भूतम् भवत् भविष्यदिति सर्वमोमकार एव यच्चान्यत् त्रिकालातीतम् तदप्योमकार एव सर्वम् ह्येतद् ब्रह्म अयमात्मा ब्रह्म सोयमात्मा चतुष्पात्"),
    "panchatantra_1": ("पंचतन्त्र — Panchatantra (मित्रभेद)", "story",
        "अस्ति मगधदेशे पाटलिपुत्रनाम नगरम् तत्र अमरशक्तिनाम राजा आसीत् तस्य त्रयः पुत्राः बहुशक्तिः उग्रशक्तिः अनन्तशक्तिश्च तेषाम् महामूर्खत्वम् दृष्ट्वा राजा चिन्तितः अभवत् किम् करोमि इति"),
    "panchatantra_2": ("पंचतन्त्र — Panchatantra (मित्रसम्प्राप्ति)",
        "अस्ति दक्षिणारण्ये महिलारोप्यनाम नगरम् तत्र हिरण्यकनाम मूषको वसति स्म तस्य च मित्रम् लघुपतनकनाम काकः आसीत् एकदा काकः अटन् गच्छन् दृष्टवान् यत् तृणबिन्दुनाम मृगः पाशे बद्धः"),
    "ramayana_bala": ("रामायण बालकाण्ड — Ramayana Bala Kanda",
        "तपःस्वाध्यायनिरतम् तपस्वी वाग्विदाम् वरम् नारदम् परिपप्रच्छ वाल्मीकिर्मुनिपुङ्गवम् को न्वस्मिन्साम्प्रतम् लोके गुणवान् कश्च वीर्यवान् धर्मज्ञश्च कृतज्ञश्च सत्यवाक्यो दृढव्रतः"),
    "ramayana_sundara": ("रामायण सुन्दरकाण्ड — Ramayana Sundara Kanda",
        "ततो रावणनीतायाः सीतायाः शत्रुकर्षणः ईयेष पदमन्वेष्टुम् चारणाचरिते पथि महेन्द्रस्य नगे तिष्ठन् दध्यौ वायुसुतस्तदा"),
    "yoga_sutras": ("योगसूत्र — Patanjali Yoga Sutras",
        "अथ योगानुशासनम् योगश्चित्तवृत्तिनिरोधः तदा द्रष्टुः स्वरूपेऽवस्थानम् वृत्तिसारूप्यमितरत्र प्रमाणविपर्ययविकल्पनिद्रास्मृतयः प्रत्यक्षानुमानागमाः प्रमाणानि विपर्ययो मिथ्याज्ञानमतद्रूपप्रतिष्ठम्"),
    "chanakya_niti": ("चाणक्यनीति — Chanakya Niti",
        "प्रणम्य शिरसा विष्णुम् त्रैलोक्याधिपतिम् प्रभुम् नानाशास्त्रोद्धृतम् वक्ष्ये राजनीतिसमुच्चयम् अधीत्य चतुरो वेदान् सर्वशास्त्राण्यनेकशः ब्रह्मतत्त्वम् न जानाति दर्वी पाकरसम् यथा"),
    "kalidasa_shakuntala": ("अभिज्ञानशाकुन्तलम् — Kalidasa Shakuntala",
        "या सृष्टिः स्रष्टुराद्या वहति विधिहुतम् या हविर्या च होत्री ये द्वे कालम् विधत्तः श्रुतिविषयगुणा या स्थिता व्याप्य विश्वम् याम् आहुः सर्वबीजप्रकृतिरिति यया प्राणिनः प्राणवन्तः प्रत्यक्षाभिः प्रपन्नस्तनुभिरवतु वस्ताभिरष्टाभिरीशः"),
    "vikramorvashiya": ("विक्रमोर्वशीयम् — Kalidasa Vikramorvashiya",
        "अयमहमात्मविसारिभिरङ्गुलीर् अनुसरिष्यति तेजसि सोमवत् अनुचितमपि कालविलम्बनम् स्मरति मनो न पुरातनमद्य तत्"),
    "arthashastra": ("अर्थशास्त्र — Kautilya Arthashastra",
        "सुखस्य मूलम् धर्मः धर्मस्य मूलम् अर्थः अर्थस्य मूलम् राज्यम् राज्यस्य मूलम् इन्द्रियजयः इन्द्रियजयस्य मूलम् विनयः विनयस्य मूलम् वृद्धोपसेवा"),
    "vishnu_sahasranama": ("विष्णुसहस्रनाम — Vishnu Sahasranama",
        "विश्वम् विष्णुर्वषट्कारो भूतभव्यभवत्प्रभुः भूतकृद्भूतभृद्भावो भूतात्मा भूतभावनः पूतात्मा परमात्मा च मुक्तानाम् परमागतिः"),
    "sundara_kanda_full": ("सुन्दरकाण्ड — Sundarakanda Extended",
        "ततः रावणनीतायाः सीतायाः शत्रुकर्षणः ईयेष पदमन्वेष्टुम् चारणाचरिते पथि स ददर्श ततः स्त्रीभिर्बहुभिः परिवारिताम् देवीम् रावणगृहे सीताम् वनवास कृशाम् शुभाम्"),
    "durga_saptashati": ("दुर्गासप्तशती — Devi Mahatmya",
        "नमो देव्यै महादेव्यै शिवायै सततम् नमः नमः प्रकृत्यै भद्रायै नियताः प्रणताः स्म ताम् रौद्रायै नमो नित्यायै गौर्यै धात्र्यै नमो नमः ज्योत्स्नायै चेन्दुरूपिण्यै सुखायै सततम् नमः"),
    "manava_dharmashastra": ("मनुस्मृति — Manusmriti",
        "मनुम् एकाग्रमासीनम् अभिगम्य महर्षयः प्रतिपूज्य यथान्यायम् इदम् वचनम् अब्रुवन् भगवन् सर्ववर्णानाम् यथावदनुपूर्वशः अन्तरप्रभवाणाम् च धर्मान् नो वक्तुमर्हसि"),
    "shankaracharya_viveka": ("विवेकचूडामणि — Adi Shankaracharya",
        "जन्तूनाम् नरजन्म दुर्लभमतः पुम्स्त्वम् ततो विप्रता तस्माद्वैदिकधर्ममार्गपरता विद्वत्त्वमस्मात्परम् आत्मानात्मविवेचनम् स्वनुभवो ब्रह्मात्मना संस्थितिः मुक्तिर्नो शतजन्मकोटिसुकृतैः पुण्यैर्विना लभ्यते"),
}

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/api/languages')
def get_languages():
    rdy = sum(1 for t in GUTENBERG if _bpath(t).exists() and _bpath(t).stat().st_size>2000)
    return jsonify([
        {"id":"english","name":"English","flag":"🇬🇧","dir":"ltr",
         "desc":f"{len(ENGLISH_TEXTS)} built-in + {rdy}/{len(GUTENBERG)} books ready"},
        {"id":"russian","name":"Русский","flag":"🇷🇺","dir":"ltr",
         "desc":f"{len(RUSSIAN_TEXTS)} texts — Pushkin · Tolstoy · Dostoevsky · Chekhov · Bulgakov"},
        {"id":"arabic","name":"العربية","flag":"🕌","dir":"rtl",
         "desc":f"114 Surahs + {len(ARABIC_CLASSICAL)} classical texts"},
        {"id":"sanskrit","name":"संस्कृतम्","flag":"🕉️","dir":"ltr",
         "desc":f"Gita · Upanishads · Ramayana · Panchatantra · Yoga Sutras · {len(SANSKRIT_TRAINER)} trainer levels"},
    ])

@app.route('/api/prompts/<lang>')
def get_prompts(lang):
    if lang=="english":
        out=[]
        # Books first (sorted by author then title)
        for title,(gid,auth) in sorted(GUTENBERG.items(),key=lambda x:(x[1][1],x[0])):
            p=_bpath(title); rdy=p.exists() and p.stat().st_size>2000
            out.append({"id":f"book_{re.sub(r'[^\w]','_',title)[:40]}","name":title,
                        "type":"book","author":auth,"desc":"✓ cached" if rdy else "click to load from Gutenberg"})
        # Built-in practice texts after
        for name in ENGLISH_TEXTS:
            out.append({"id":f"en_{re.sub(r'[^\w]','_',name)}","name":name,"type":"text","author":"Built-in"})
        return jsonify(out)
    if lang=="russian":
        names={
            "ru_home_row":"Домашний ряд — ФЫВА ОЛДЖ","ru_basics":"Основы — приветствия",
            "ru_pushkin_vy":"Пушкин — Я вас любил","ru_pushkin_onegin":"Пушкин — Евгений Онегин",
            "ru_pushkin_medny":"Пушкин — Медный всадник","ru_lermontov":"Лермонтов — Выхожу один",
            "ru_tolstoy_anna":"Толстой — Анна Каренина","ru_tolstoy_voina":"Толстой — Война и мир",
            "ru_tolstoy_voskr":"Толстой — Воскресение",
            "ru_dostoevsky_pre":"Достоевский — Преступление и наказание",
            "ru_dostoevsky_idi":"Достоевский — Идиот","ru_dostoevsky_bra":"Достоевский — Братья Карамазовы",
            "ru_chekhov_vishny":"Чехов — Вишнёвый сад","ru_chekhov_dama":"Чехов — Дама с собачкой",
            "ru_chekhov_palata":"Чехов — Палата №6","ru_gogol_mertvye":"Гоголь — Мёртвые души",
            "ru_gogol_revizor":"Гоголь — Ревизор","ru_bulgakov":"Булгаков — Мастер и Маргарита",
            "ru_turgenev":"Тургенев — Отцы и дети","ru_akhmatova":"Ахматова — стихи",
        }
        return jsonify([{"id":k,"name":names.get(k,k),"type":"text"}
                        for k in RUSSIAN_TEXTS])

    if lang=="arabic":
        out=[
            {"id":"al_fatiha","name":"001. الفاتحة — Al-Fatiha","type":"quran","desc":"built-in"},
            {"id":"al_ikhlas","name":"112. الإخلاص — Al-Ikhlas","type":"quran","desc":"built-in"},
            {"id":"al_nas","name":"114. الناس — An-Nas","type":"quran","desc":"built-in"},
            {"id":"al_falaq","name":"113. الفلق — Al-Falaq","type":"quran","desc":"built-in"},
            {"id":"ayat_kursi","name":"آية الكرسي — Ayat Al-Kursi","type":"quran","desc":"built-in"},
            {"id":"al_baqarah_opening","name":"002. البقرة — Al-Baqarah opening","type":"quran","desc":"built-in"},
            {"id":"al_mulk","name":"067. الملك — Al-Mulk","type":"quran","desc":"built-in"},
            {"id":"al_yasin","name":"036. يس — Ya-Sin","type":"quran","desc":"built-in"},
            {"id":"ar_rahman","name":"055. الرحمن — Ar-Rahman","type":"quran","desc":"built-in"},
        ]
        # Classical Arabic literature
        for kid,(kname,ktype,_) in ARABIC_CLASSICAL.items():
            out.append({"id":f"classical_{kid}","name":kname,"type":"text","desc":"Classical Arabic"})
        # All 114 Surahs
        for (n,na,ne,ay) in SURAHS:
            out.append({"id":f"surah_{n}","name":f"{n:03d}. {na} — {ne}","type":"quran","desc":f"{ay} ayahs"})
        return jsonify(out)

    if lang=="sanskrit":
        lvl_names={
            "sa_level_1_vowels":"Level 1 — Vowels (अ आ इ ई)",
            "sa_level_2_ka":"Level 2 — Ka group (क ख ग घ)",
            "sa_level_3_ca":"Level 3 — Ca group (च छ ज झ)",
            "sa_level_4_ta":"Level 4 — Ta/Da group (ट ठ ड ढ ण)",
            "sa_level_5_pa":"Level 5 — Pa group (प फ ब भ म)",
            "sa_level_6_semi":"Level 6 — Semi-vowels (य र ल व)",
            "sa_level_7_matras":"Level 7 — Vowel marks (का कि की)",
            "sa_level_8_words":"Level 8 — Sanskrit words",
            "sa_level_9_phrases":"Level 9 — Sanskrit phrases",
            "sa_level_10_gita":"Level 10 — Gita vocabulary",
        }
        out=[{"id":k,"name":lvl_names.get(k,k),"type":"trainer"} for k in SANSKRIT_TRAINER]
        out.append({"id":"gita_all","name":"Bhagavad Gita — Complete (18 Chapters)","type":"gita"})
        out.append({"id":"gita_1_6","name":"Gita Ch.1–6 — Karma Kanda","type":"gita"})
        out.append({"id":"gita_7_12","name":"Gita Ch.7–12 — Bhakti Kanda","type":"gita"})
        out.append({"id":"gita_13_18","name":"Gita Ch.13–18 — Jnana Kanda","type":"gita"})
        for ch,d in GITA.items():
            out.append({"id":f"gita_{ch}","name":f"Ch.{ch:02d} — {d['name_en']}","type":"gita",
                        "desc":f"{len(d['verses'])} shlokas"})
        # Sanskrit scriptures beyond the Gita
        for sid,(sname,stext) in SANSKRIT_SCRIPTURES.items():
            out.append({"id":f"scripture_{sid}","name":sname,"type":"text","desc":"Sanskrit Scripture"})
        return jsonify(out)
    return jsonify([])

@app.route('/api/words', methods=['POST'])
def get_words():
    d=request.json or {}; lang=d.get('lang','english'); pid=d.get('prompt_id','')
    words=[]; direction='ltr'

    if lang=='english':
        if pid.startswith('book_'):
            bkey=pid[5:]
            matched_title=None; matched_gid=None
            for title,(gid,auth) in GUTENBERG.items():
                if re.sub(r'[^\w]','_',title)[:40]==bkey:
                    matched_title=title; matched_gid=gid; break
            if matched_title:
                # Try filesystem cache first
                p=_bpath(matched_title)
                if p.exists() and p.stat().st_size>2000:
                    try:
                        text=p.read_text(encoding='utf-8')
                        import random
                        start=random.randint(0,max(0,len(text)-25000))
                        chunk=text[start:start+25000]
                        words=chunk.split()[:3000]
                        for i,w in enumerate(words[:30]):
                            if w and w[0].isupper() and len(w)>1:
                                words=words[i:]; break
                    except: pass
                # If not cached, fetch directly from Gutenberg right now
                if not words:
                    words=_fetch_gutenberg_words(matched_title, matched_gid)
                # Save to cache for next time
                if words and not (p.exists() and p.stat().st_size>2000):
                    try: p.write_text(' '.join(words), encoding='utf-8')
                    except: pass
            if not words:
                # Return empty with message instead of gibberish home row text
                return jsonify({'lang':lang,'words':[],'dir':'ltr',
                    'error':f'Could not load book. Gutenberg may be slow. Try again.'})
        else:
            name=pid[3:].replace('_',' ')
            text=ENGLISH_TEXTS.get(name,list(ENGLISH_TEXTS.values())[0])
            words=text.split()

    elif lang=='russian':
        text=RUSSIAN_TEXTS.get(pid,list(RUSSIAN_TEXTS.values())[0]); words=text.split()

    elif lang=='arabic':
        direction='rtl'
        if pid.startswith('classical_'):
            kid=pid[10:]
            if kid in ARABIC_CLASSICAL:
                entry=ARABIC_CLASSICAL[kid]
                raw=entry[2] if len(entry)>2 else entry[-1]
            else: raw=ARABIC_BUILTIN['al_fatiha']
        elif pid in ARABIC_BUILTIN: raw=ARABIC_BUILTIN[pid]
        elif pid.startswith('surah_'):
            try: raw=_fetch_surah(int(pid[6:])) or ARABIC_BUILTIN['al_fatiha']
            except: raw=ARABIC_BUILTIN['al_fatiha']
        else: raw=ARABIC_BUILTIN.get(pid,ARABIC_BUILTIN['al_fatiha'])
        raw=_strip_all_ar(raw); words=[w for w in raw.split() if w and not all(c in '*()[]{}' for c in w)]

    elif lang=='sanskrit':
        if pid.startswith('scripture_'):
            sid=pid[10:]
            if sid in SANSKRIT_SCRIPTURES:
                entry=SANSKRIT_SCRIPTURES[sid]
                raw=entry[-1]  # last element is always the text
                words=raw.split()
            else: words=(list(SANSKRIT_TRAINER.values())[0].split()*8)[:60]
        elif pid.startswith('sa_level'):
            raw=SANSKRIT_TRAINER.get(pid,list(SANSKRIT_TRAINER.values())[0])
            words=(raw.split()*8)[:60]
        elif pid=='gita_all': words=' '.join(v for c in GITA.values() for v in c['verses']).split()
        elif pid=='gita_1_6': words=' '.join(v for i in range(1,7) for v in GITA[i]['verses']).split()
        elif pid=='gita_7_12': words=' '.join(v for i in range(7,13) for v in GITA[i]['verses']).split()
        elif pid=='gita_13_18': words=' '.join(v for i in range(13,19) for v in GITA[i]['verses']).split()
        elif pid.startswith('gita_'):
            try: words=' '.join(GITA[int(pid[5:])]['verses']).split()
            except: words=' '.join(GITA[1]['verses']).split()
        else: words=(list(SANSKRIT_TRAINER.values())[0].split()*8)[:60]

    return jsonify({"lang":lang,"words":words,"dir":direction})

def _strip_all_ar(text):
    """Nuclear Arabic diacritic removal — strips everything non-letter."""
    if not text: return text
    # Remove asterisks, verse markers, numbers, punctuation
    text = re.sub(r'[\*\(\)\[\]\{\}0-9٠-٩۰-۹]', '', text)
    text = re.sub(r'[\u06DD\u06DE\u06DF]', '', text)  # Arabic end of ayah markers
    text = re.sub(r'[\u0600-\u0605]', '', text)  # Arabic number signs
    # All diacritic ranges
    text = re.sub(r'[\u0600-\u0615]', '', text)   # Arabic signs
    text = re.sub(r'[\u0610-\u061A]', '', text)   # honorifics
    text = re.sub(r'[\u064B-\u065F]', '', text)   # all harakat/diacritics
    text = re.sub(r'[\u0670]',        '', text)   # superscript alef
    text = re.sub(r'[\u06D6-\u06DC]', '', text)   # small high marks
    text = re.sub(r'[\u06DF-\u06E4]', '', text)   # more marks
    text = re.sub(r'[\u06E7-\u06E8]', '', text)   # small high yeh/noon
    text = re.sub(r'[\u06EA-\u06ED]', '', text)   # more small marks
    text = re.sub(r'\u0640',          '', text)   # tatweel
    text = re.sub(r'[\u200B-\u200F\u202A-\u202E\uFEFF]', '', text)
    return deep_norm_ar(text)

def _fetch_surah(n):
    # Try the simple/clean Arabic edition first (no diacritics)
    sources = [
        f"https://api.alquran.cloud/v1/surah/{n}/ar.simple",
        f"https://api.alquran.cloud/v1/surah/{n}",
    ]
    for url in sources:
        try:
            data=json.loads(urlopen(Request(url,headers={"User-Agent":"UltimateTyper/3.0"}),timeout=12).read().decode())
            if data.get("code")==200:
                raw=" ".join(a["text"] for a in data["data"]["ayahs"])
                return _strip_all_ar(raw)
        except: continue
    return ""

@app.route('/api/session', methods=['POST'])
def save_session():
    d=request.json or {}; db=get_db()
    db.execute("INSERT INTO sessions (username,language,prompt_name,wpm,avg_wpm,accuracy,"
               "chars_typed,words_typed,errors,duration) VALUES (?,?,?,?,?,?,?,?,?,?)",
               (d.get('username','anonymous'),d.get('lang',''),d.get('prompt_name',''),
                d.get('wpm',0),d.get('avg_wpm',0),d.get('accuracy',100),
                d.get('chars_typed',0),d.get('words_typed',0),d.get('errors',0),d.get('duration',0)))
    db.commit(); return jsonify({"ok":True})

@app.route('/api/stats/<lang>')
def get_stats(lang):
    username=request.args.get('username',''); db=get_db()
    q=("SELECT wpm,avg_wpm,accuracy,words_typed,duration,prompt_name,errors,username,created_at "
       "FROM sessions WHERE language=?")
    args=[lang]
    if username: q+=" AND username=?"; args.append(username)
    q+=" ORDER BY created_at DESC LIMIT 100"
    rows=[dict(r) for r in db.execute(q,args).fetchall()]
    wpms=[r['wpm'] for r in rows if r.get('wpm')]
    return jsonify({"sessions":rows,"best_wpm":round(max(wpms),1) if wpms else 0,
                    "avg_wpm":round(sum(wpms)/len(wpms),1) if wpms else 0,
                    "total_sessions":len(rows),"total_words":sum(r.get('words_typed',0) for r in rows)})

@app.route('/api/leaderboard')
def leaderboard():
    lang     = request.args.get('lang','')
    group_by = request.args.get('group','prompt')  # 'prompt' or 'user'
    db       = get_db()
    base = ("SELECT username, language, prompt_name, "
            "MAX(wpm) best_wpm, AVG(accuracy) avg_acc, "
            "COUNT(*) sessions, SUM(words_typed) total_words "
            "FROM sessions")
    if lang and lang != 'all':
        rows = db.execute(base+" WHERE language=? "
            "GROUP BY username, language, prompt_name "
            "ORDER BY best_wpm DESC LIMIT 50", (lang,)).fetchall()
    else:
        rows = db.execute(base+
            " GROUP BY username, language, prompt_name "
            "ORDER BY language, best_wpm DESC LIMIT 100").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/books/status')
def books_status():
    return jsonify({t:{"ready":_bpath(t).exists() and _bpath(t).stat().st_size>2000,"author":a}
                    for t,(g,a) in GUTENBERG.items()})

@app.route('/health')
def health():
    rdy=sum(1 for t in GUTENBERG if _bpath(t).exists() and _bpath(t).stat().st_size>2000)
    return jsonify({"status":"ok","books":f"{rdy}/{len(GUTENBERG)}"})

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
