"""架空のECサイト「くりくり珈琲店」の練習用データベース shop.db を生成する。

- データはすべて乱数から作った架空のもので、実在の人物・店舗・商品とは関係ありません
- 個人情報(氏名・メールアドレス・住所・電話番号)は含みません
- 固定シードを使うため、同じ Python で実行すれば毎回同じ内容になります
  (採点は配布した shop.db を基準にします。作り直した場合は grade.py が警告します)

使い方: python build_db.py
"""
import bisect
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20261008
DB_PATH = Path(__file__).with_name("shop.db")
START = datetime(2024, 10, 1)
END = datetime(2026, 9, 30, 23, 59, 59)

SCHEMA = """
CREATE TABLE users (
    user_id       INTEGER PRIMARY KEY,
    nickname      TEXT NOT NULL,
    prefecture    TEXT,             -- 未登録は NULL。表記ゆれあり
    birth_year    INTEGER,          -- 未登録は NULL
    registered_at TEXT NOT NULL     -- 'YYYY-MM-DD HH:MM:SS'(日本時間)
);
CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    parent_id   INTEGER             -- 大分類は NULL
);
CREATE TABLE products (
    product_id  INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    price       INTEGER NOT NULL,   -- 現在の税抜価格(円)
    is_active   INTEGER NOT NULL,   -- 1: 販売中, 0: 販売終了
    launched_at TEXT NOT NULL       -- 'YYYY-MM-DD'
);
CREATE TABLE coupons (
    coupon_id     INTEGER PRIMARY KEY,
    code          TEXT NOT NULL,
    discount_rate INTEGER NOT NULL, -- 割引率(%)
    valid_from    TEXT NOT NULL,
    valid_to      TEXT NOT NULL
);
CREATE TABLE orders (
    order_id   INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL,    -- 退会済みで users に存在しない ID もある
    ordered_at TEXT NOT NULL,
    status     TEXT NOT NULL,       -- 'completed' / 'cancelled' / 'returned'
    coupon_id  INTEGER              -- 未使用は NULL
);
CREATE TABLE order_items (
    order_id   INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity   INTEGER NOT NULL,
    unit_price INTEGER NOT NULL,    -- 注文時点の税抜単価(価格改定前の値のこともある)
    PRIMARY KEY (order_id, product_id)
);
CREATE TABLE events (
    event_id    INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    event_type  TEXT NOT NULL,      -- 'view' / 'cart' / 'purchase'
    product_id  INTEGER NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE TABLE reviews (
    review_id  INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    rating     INTEGER NOT NULL,    -- 1〜5
    posted_at  TEXT NOT NULL
);
"""

# (表記, 重み)。末尾の数件はわざと混ぜた表記ゆれ
PREFECTURES = [
    ("東京都", 200), ("神奈川県", 90), ("大阪府", 80), ("愛知県", 60), ("埼玉県", 60),
    ("千葉県", 50), ("福岡県", 50), ("北海道", 40), ("兵庫県", 40), ("京都府", 30),
    ("静岡県", 25), ("広島県", 20), ("宮城県", 20), ("茨城県", 15), ("長野県", 15),
    ("新潟県", 15), ("岡山県", 12), ("熊本県", 12), ("沖縄県", 10), ("石川県", 10),
    ("東京", 6), (" 東京都", 4), ("東京都 ", 4), ("大阪", 4), ("神奈川", 3),
]

CATEGORIES = [
    (1, "コーヒー豆", None), (2, "抽出器具", None), (3, "食器", None), (4, "フード", None),
    (5, "シングルオリジン", 1), (6, "ブレンド", 1), (7, "デカフェ", 1),
    (8, "ドリッパー", 2), (9, "ミル", 2), (10, "ケトル", 2), (11, "フィルター", 2),
    (12, "マグカップ", 3), (13, "グラス", 3),
    (14, "焼き菓子", 4), (15, "ギフトセット", 4),
]

ORIGINS = ["ブラジル", "コロンビア", "エチオピア", "グアテマラ", "ケニア", "インドネシア",
           "コスタリカ", "ペルー", "ホンジュラス", "タンザニア"]
ROASTS = ["浅煎り", "中煎り", "深煎り"]
BLENDS = ["朝のブレンド", "夜のブレンド", "くりくりブレンド", "ビターブレンド",
          "やさしいブレンド", "季節のブレンド"]


def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def rand_dt(rng, start, end):
    span = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randrange(span + 1))


def weighted(rng, pairs):
    total = sum(w for _, w in pairs)
    r = rng.randrange(total)
    for value, w in pairs:
        r -= w
        if r < 0:
            return value
    raise AssertionError


def build_products(rng):
    rows = []
    pid = 0

    def add(name, cat, price):
        nonlocal pid
        pid += 1
        launched = rand_dt(rng, datetime(2023, 4, 1), datetime(2026, 6, 30))
        # 2026年以降に出た商品は販売中、それ以前は1割が販売終了
        active = 1 if launched.year >= 2026 or rng.random() >= 0.1 else 0
        rows.append((pid, name, cat, price, active, launched.strftime("%Y-%m-%d")))

    for origin in ORIGINS:
        for roast in rng.sample(ROASTS, 2):
            for grams, base in ((200, 1200), (500, 2700)):
                add(f"{origin} {roast} {grams}g", 5, base + rng.randrange(0, 9) * 100)
    for blend in BLENDS:
        for grams, base in ((200, 1000), (500, 2300)):
            add(f"{blend} {grams}g", 6, base + rng.randrange(0, 6) * 100)
    for name in ["デカフェ コロンビア 200g", "デカフェ エチオピア 200g",
                 "デカフェ ブレンド 200g", "デカフェ ブレンド 500g"]:
        add(name, 7, 1300 + rng.randrange(0, 6) * 100)
    tools = {
        8: ["ドリッパー 陶器 1〜2杯用", "ドリッパー 陶器 2〜4杯用", "ドリッパー 樹脂 1〜2杯用",
            "ドリッパー ガラス 2〜4杯用", "ドリッパー 銅 1〜2杯用"],
        9: ["手挽きミル セラミック刃", "手挽きミル ステンレス刃", "電動ミル コンパクト",
            "電動ミル プロペラ式", "電動ミル コニカル刃"],
        10: ["ドリップケトル 0.6L", "ドリップケトル 1.0L", "電気ケトル 温度調整 0.8L",
             "電気ケトル 温度調整 1.0L"],
        11: ["ペーパーフィルター 1〜2杯用 100枚", "ペーパーフィルター 2〜4杯用 100枚",
             "ペーパーフィルター 無漂白 100枚", "ステンレスフィルター"],
        12: ["マグカップ 白 300ml", "マグカップ 黒 300ml", "マグカップ 青 350ml",
             "マグカップ 二重構造 250ml", "マグカップ 琺瑯 300ml"],
        13: ["耐熱グラス 240ml", "耐熱グラス 360ml", "アイスコーヒーグラス 400ml",
             "デミタスグラス 90ml"],
        14: ["コーヒークッキー 8枚", "フィナンシェ 5個", "ナッツのビスコッティ 6本",
             "ドライフルーツのパウンドケーキ", "チョコレートサブレ 10枚"],
        15: ["ギフト 豆3種セット", "ギフト 豆5種セット", "ギフト ドリップバッグ20袋",
             "ギフト 焼き菓子とコーヒー", "ギフト マグとコーヒー"],
    }
    price_range = {8: (800, 4500), 9: (2500, 15000), 10: (3000, 12000), 11: (400, 2500),
                   12: (1200, 3500), 13: (900, 2800), 14: (600, 2200), 15: (2500, 6000)}
    for cat, names in tools.items():
        lo, hi = price_range[cat]
        for name in names:
            add(name, cat, rng.randrange(lo // 100, hi // 100 + 1) * 100)
    # 商品名の末尾に空白が入ってしまった登録ミス(文字列整形の題材)
    for i in rng.sample(range(len(rows)), 3):
        r = list(rows[i])
        r[1] = r[1] + " "
        rows[i] = tuple(r)
    return rows


def build():
    rng = random.Random(SEED)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(str(DB_PATH))
    con.executescript(SCHEMA)

    # users: 後半ほど登録が増える
    users = []
    for uid in range(1, 2001):
        u = rng.random() ** 0.8
        reg = START + timedelta(seconds=int(u * (END - START).total_seconds()))
        pref = None if rng.random() < 0.06 else weighted(rng, PREFECTURES)
        birth = None if rng.random() < 0.12 else rng.randrange(1958, 2007)
        users.append((uid, f"user_{uid:04d}", pref, birth, ts(reg)))
    con.executemany("INSERT INTO users VALUES (?,?,?,?,?)", users)
    con.executemany("INSERT INTO categories VALUES (?,?,?)", CATEGORIES)

    products = build_products(rng)
    con.executemany("INSERT INTO products VALUES (?,?,?,?,?,?)", products)
    # 2025-10-01 に一部商品を値上げした。それより前の注文は旧価格で記録される
    raised = set(rng.sample([p[0] for p in products], 30))

    coupons = []
    for cid in range(1, 11):
        start = START + timedelta(days=72 * (cid - 1))
        coupons.append((cid, f"KURI{cid:02d}", rng.choice([5, 10, 15, 20]),
                        start.strftime("%Y-%m-%d"),
                        (start + timedelta(days=30)).strftime("%Y-%m-%d")))
    con.executemany("INSERT INTO coupons VALUES (?,?,?,?,?)", coupons)

    # orders / order_items
    active_weight = {u[0]: rng.choice([1, 1, 1, 2, 3, 6, 12]) for u in users}
    user_pool = sorted((u for u in users for _ in range(active_weight[u[0]])), key=lambda u: u[4])
    pool_regs = [u[4] for u in user_pool]

    def activity():
        """事業の成長に合わせて後半ほど多くなる日時と、その時点で登録済みの会員を選ぶ"""
        while True:
            at = START + timedelta(seconds=int(rng.random() ** 0.8 * (END - START).total_seconds()))
            n = bisect.bisect_right(pool_regs, ts(at))
            if n:
                return at, user_pool[rng.randrange(n)]
    orders, items = [], []
    oid = 0
    product_ids = [p[0] for p in products]
    price_of = {p[0]: p[3] for p in products}
    launched_of = {p[0]: p[5] for p in products}
    while oid < 15000:
        if rng.random() < 0.012:  # 退会済み会員の注文(users に存在しない)
            at, _ = activity()
            uid = rng.randrange(2001, 2051)
        else:
            at, u = activity()
            uid = u[0]
        oid += 1
        status = weighted(rng, [("completed", 88), ("cancelled", 8), ("returned", 4)])
        coupon = None
        for c in coupons:
            if c[3] <= at.strftime("%Y-%m-%d") <= c[4] and rng.random() < 0.3:
                coupon = c[0]
        orders.append((oid, uid, ts(at), status, coupon))
        day = at.strftime("%Y-%m-%d")
        available = [p for p in product_ids if launched_of[p] <= day]
        for pid in rng.sample(available, min(len(available), weighted(rng, [(1, 50), (2, 30), (3, 15), (4, 5)]))):
            price = price_of[pid]
            if pid in raised and at < datetime(2025, 10, 1):
                price = price - 100 if price < 3000 else price - 300
            items.append((oid, pid, weighted(rng, [(1, 70), (2, 22), (3, 8)]), price))
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)
    con.executemany("INSERT INTO order_items VALUES (?,?,?,?)", items)

    # events: 閲覧 → カート → 購入 のファネル
    events = []
    eid = 0
    for _ in range(30000):
        at, u = activity()
        day = at.strftime("%Y-%m-%d")
        pid = rng.choice([p for p in product_ids if launched_of[p] <= day])
        steps = ["view"]
        if rng.random() < 0.35:
            steps.append("cart")
            if rng.random() < 0.45:
                steps.append("purchase")
        for step in steps:
            if at > END:
                break
            eid += 1
            events.append((eid, u[0], step, pid, ts(at)))
            at += timedelta(seconds=rng.randrange(30, 1800))
    con.executemany("INSERT INTO events VALUES (?,?,?,?,?)", events)

    # reviews: 同じ人が同じ商品に2回投稿した重複も混ぜる
    reviews = []
    for rid in range(1, 3001):
        if reviews and rng.random() < 0.03:
            prev = rng.choice(reviews)
            uid, pid = prev[1], prev[2]
            at = datetime.strptime(prev[4], "%Y-%m-%d %H:%M:%S") + timedelta(minutes=rng.randrange(1, 120))
        else:
            at, u = activity()
            uid = u[0]
            day = at.strftime("%Y-%m-%d")
            pid = rng.choice([p for p in product_ids if launched_of[p] <= day])
        rating = weighted(rng, [(5, 40), (4, 32), (3, 15), (2, 8), (1, 5)])
        reviews.append((rid, uid, pid, rating, ts(at)))
    con.executemany("INSERT INTO reviews VALUES (?,?,?,?,?)", reviews)

    con.commit()
    con.execute("VACUUM")
    con.close()


if __name__ == "__main__":
    build()
    print(f"作成しました: {DB_PATH}")
