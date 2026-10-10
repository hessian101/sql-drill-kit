"""SQLドリルの自動採点スクリプト(Python 標準ライブラリだけで動きます)

使い方:
  python grade.py 1-01          1問だけ採点
  python grade.py 1-01 1-02     複数の問題を採点
  python grade.py --chapter 1   第1章をまとめて採点
  python grade.py               全問を採点(未着手の問題は飛ばします)
  python grade.py 1-01 --show   自分のSQLの実行結果(先頭10行)も表示

answers/<問題番号>.sql に解答のSQLを書いてから実行してください。
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "shop.db"
ANSWERS = HERE / "answers"
MIN_SQLITE = (3, 25, 0)  # ウィンドウ関数に対応したバージョン


def normalize(columns, rows, ordered):
    """列名を小文字にそろえ、小数を丸め、順序を問わない問題では行を並べ替える"""
    def cell(v):
        if isinstance(v, float):
            v = round(v, 6)
            return int(v) if v.is_integer() else v  # 5060.0 と 5060 は同じ値として扱う
        return v

    rows = [[cell(v) for v in r] for r in rows]
    if not ordered:
        rows.sort(key=lambda r: json.dumps(r, ensure_ascii=False))
    return {"columns": [c.lower() for c in columns], "rows": rows}


def digest(result):
    return hashlib.sha256(json.dumps(result, ensure_ascii=False).encode("utf-8")).hexdigest()


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(sql, problem):
    """解答SQLを実行して (列名, 行, 実行計画) を返す。元の shop.db は変更しない"""
    if problem.get("type") == "dml" or "setup" in problem:
        # DBをメモリ上に複製してから実行する。更新系の問題は、検証用のクエリで結果を確かめる
        src = sqlite3.connect(str(DB_PATH))
        con = sqlite3.connect(":memory:")
        src.backup(con)
        src.close()
        if "setup" in problem:
            con.executescript(problem["setup"])
    else:
        con = sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True)
    if problem.get("type") == "dml":
        con.executescript(sql)
        target = problem["check"]
    else:
        target = sql
    cur = con.execute(target)
    if cur.description is None:
        raise sqlite3.Error("結果を返すSELECT文になっていません")
    columns = [d[0] for d in cur.description]
    rows = cur.fetchall()
    plan = None
    if "plan" in problem:
        plan = [r[3] for r in con.execute("EXPLAIN QUERY PLAN " + target)]
        tables = dict(con.execute("SELECT name, tbl_name FROM sqlite_master WHERE type = 'index'"))
        plan = (plan, tables)
    con.close()
    return columns, rows, plan


def check_plan(rule, plan):
    """実行計画で、指定のテーブルをインデックスで絞り込んでいるか(SEARCH ... USING INDEX)を確かめる

    実行計画の書式は SQLite のバージョンで少し違う(古い版は SEARCH TABLE orders AS o ...)ので、両方を受け付ける
    """
    lines, tables = plan
    used = []
    for line in lines:
        m = re.match(r"SEARCH (?:TABLE )?\S+(?: AS \S+)? USING (COVERING )?INDEX (\S+)", line)
        if m and tables.get(m.group(2)) == rule["table"]:
            used.append(bool(m.group(1)))
    if not used:
        return f"結果は合っていますが、{rule['table']} をインデックスで絞り込めていません(SEARCH ... USING INDEX になっていません)"
    if rule.get("covering") and not any(used):
        return "結果は合っていますが、カバリングインデックスになっていません(USING COVERING INDEX になっていません)"
    return None


def grade_one(pid, problem, expected, show):
    path = ANSWERS / f"{pid}.sql"
    if not path.exists():
        return None, f"[--] {pid}: answers/{pid}.sql がありません"
    sql = path.read_text(encoding="utf-8-sig")
    body = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--")).strip()
    if not body:
        return None, f"[--] {pid}: まだ解答が書かれていません"
    try:
        columns, rows, plan = execute(sql, problem)
    except (sqlite3.Warning, sqlite3.Error) as e:
        if "one statement" in str(e):
            return False, f"[NG] {pid}: SQL文は1つだけ書いてください(途中の ; を確認)"
        if "readonly" in str(e):
            return False, f"[NG] {pid}: この問題はSELECT文で答えます(データは書き換えできません)"
        return False, f"[NG] {pid}: SQLエラー: {e}"

    lines = []
    if show:
        lines.append("     " + " | ".join(columns))
        for r in rows[:10]:
            lines.append("     " + " | ".join("NULL" if v is None else str(v) for v in r))
        if len(rows) > 10:
            lines.append(f"     ...(全{len(rows)}行)")

    if plan is not None:
        lines.append("     実行計画:")
        lines.extend("       " + line for line in plan[0])

    got = normalize(columns, rows, problem.get("ordered", False))
    exp = expected[pid]
    if digest(got) == exp["hash"]:
        plan_msg = check_plan(problem["plan"], plan) if plan is not None else None
        if plan_msg:
            return False, "\n".join([f"[NG] {pid}: {plan_msg}"] + lines)
        return True, "\n".join([f"[OK] {pid}"] + lines)
    if got["columns"] != exp["columns"]:
        msg = f"[NG] {pid}: 列が違います\n     期待: {exp['columns']}\n     実際: {got['columns']}"
    elif len(got["rows"]) != exp["row_count"]:
        msg = f"[NG] {pid}: 行数が違います(期待 {exp['row_count']} 行 / 実際 {len(got['rows'])} 行)"
    elif problem.get("ordered"):
        msg = f"[NG] {pid}: 列と行数は合っています。値か並び順(ORDER BY)が違います"
    else:
        msg = f"[NG] {pid}: 列と行数は合っています。値が違います"
    return False, "\n".join([msg] + lines)


def main():
    parser = argparse.ArgumentParser(description="SQLドリルの自動採点")
    parser.add_argument("ids", nargs="*", help="問題番号(例: 1-01)")
    parser.add_argument("--chapter", type=int, help="章番号を指定してまとめて採点")
    parser.add_argument("--show", action="store_true", help="自分のSQLの実行結果を表示")
    args = parser.parse_args()

    if sqlite3.sqlite_version_info < MIN_SQLITE:
        sys.exit(f"SQLite {sqlite3.sqlite_version} は古いため、3.25 以上が必要です。"
                 "Python を新しいバージョンにしてください")
    if not DB_PATH.exists():
        sys.exit("shop.db が見つかりません。grade.py と同じフォルダに置いてください")

    problems = json.loads((HERE / "problems.json").read_text(encoding="utf-8"))
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    if file_sha256(DB_PATH) != expected["_meta"]["db_sha256"]:
        print("注意: shop.db が配布時と異なります。採点結果が正しくならない可能性があります\n")

    known = [pid for pid in problems if pid in expected]
    if args.ids:
        unknown = [pid for pid in args.ids if pid not in known]
        if unknown:
            sys.exit(f"問題番号が見つかりません: {', '.join(unknown)}")
        targets = args.ids
    elif args.chapter is not None:
        targets = [pid for pid in known if pid.split("-")[0] == str(args.chapter)]
    else:
        targets = known

    passed = attempted = 0
    for pid in targets:
        ok, message = grade_one(pid, problems[pid], expected, args.show)
        print(message)
        if ok is not None:
            attempted += 1
            passed += ok
    print(f"\n結果: {passed}/{attempted} 問正解(未着手 {len(targets) - attempted} 問)")


if __name__ == "__main__":
    main()
