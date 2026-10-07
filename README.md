# sql-drill-kit

SQLドリルを**環境構築なし**で解くための、自動採点キットと練習用データベースです。
Python があれば動きます(pip でのインストールは不要)。

- 問題文・ヒント・解説は、Zennの記事に掲載しています:https://zenn.dev/kurikuri1024/articles/sql-drill-chapter1
- このリポジトリには、問題文・模範解答は含まれていません

## 動作環境
- Python 3.8 以上(標準ライブラリだけで動きます)
- SQLite 3.25 以上(Python に同梱されています。古い場合は `grade.py` が教えてくれます)
- Windows / macOS / Linux

## 使い方

1. このリポジトリをダウンロードします(緑の「Code」ボタン →「Download ZIP」でも可)
2. `answers/1-01.sql` を開いて、解答のSQLを書きます
3. ターミナル(Windowsはコマンドプロンプト)で、このフォルダに移動して実行します

```bash
python grade.py 1-01
```

※ macOS / Linux で `python` が見つからない場合は `python3` で実行してください。

| コマンド | 内容 |
|---|---|
| `python grade.py 1-01` | 1問だけ採点 |
| `python grade.py --chapter 1` | 第1章をまとめて採点 |
| `python grade.py` | 全問を採点(未着手の問題は飛ばします) |
| `python grade.py 1-01 --show` | 自分のSQLの実行結果(先頭10行)も表示 |

### 採点結果の見方
- `[OK]` 正解です
- `[NG] 列が違います` 列名や列の順番が問題の指定と違います(`AS` で列名を付ける問題もあります)
- `[NG] 行数が違います` 絞り込みの条件を見直しましょう
- `[NG] 列と行数は合っています。値か並び順(ORDER BY)が違います` 計算や並び順を見直しましょう
- 正誤は、実行結果をハッシュ化して照合しています。`expected.json` には答えそのものは入っていません

### SQLを直接試したいとき
`shop.db` は普通のSQLiteのデータベースです。`sqlite3 shop.db` や、DB Browser for SQLite などのツールで開いて、自由にSELECTを試せます(採点は `grade.py` で行ってください)。

## データについて(架空のECサイト「くりくり珈琲店」)

2024年10月〜2026年9月の、架空の注文データです。**すべて乱数から生成したもので、実在の人物・店舗・商品とは関係ありません。** 氏名・メールアドレス・住所などの個人情報は含みません。
実務で出会うような「汚れ」(未入力、表記ゆれ、退会済み会員の注文など)を、わざと含めています。

| テーブル | 内容 | 主な列 |
|---|---|---|
| `users` | 会員(2,000人) | user_id, nickname, prefecture(未登録はNULL), birth_year(未登録はNULL), registered_at |
| `categories` | 商品カテゴリ(大分類・小分類) | category_id, name, parent_id(大分類はNULL) |
| `products` | 商品 | product_id, name, category_id, price(現在の税抜価格), is_active(1:販売中 / 0:販売終了), launched_at |
| `coupons` | クーポン | coupon_id, code, discount_rate(%), valid_from, valid_to |
| `orders` | 注文(15,000件) | order_id, user_id, ordered_at, status(completed / cancelled / returned), coupon_id |
| `order_items` | 注文明細 | order_id, product_id, quantity, unit_price(注文時点の税抜単価) |
| `events` | 閲覧・カート追加・購入のログ | event_id, user_id, event_type(view / cart / purchase), product_id, occurred_at |
| `reviews` | 商品レビュー | review_id, user_id, product_id, rating(1〜5), posted_at |

日時は `'YYYY-MM-DD HH:MM:SS'` 形式の文字列(日本時間)です。

`build_db.py` は `shop.db` を作り直すスクリプトです。採点は配布した `shop.db` を基準にするので、通常は実行する必要はありません。

## ライセンス
- 採点スクリプト・データ生成スクリプト・データベース:MIT License(`LICENSE` を参照)
- 問題文・ヒント・解説は、Zennの記事と本の著作物です(このリポジトリには含みません)

このキットは著者(kurikuri)が作成し、AI(Claude Code)の支援を受けて実装・検証しました。
「データサイエンス100本ノック」(データサイエンティスト協会)とは関係のない、オリジナルの問題とデータです。

