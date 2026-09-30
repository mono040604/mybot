import json
from pathlib import Path
from psycopg2.extras import RealDictCursor, Json
from storage import srs
from datetime import datetime, timezone, timedelta
import psycopg2
import math

_db = json.loads(Path("config.json").read_text(encoding="utf-8"))["database"]

def _get_connection():
    return psycopg2.connect(
        host=_db["host"],
        port=_db["port"],
        dbname=_db["dbname"],
        user=_db["user"],
        password=_db["password"],
    )


def init_db():
    conn = _get_connection()
    try:
        with conn.cursor() as cur:      # ✅ 你这条 with 保留：自动关游标
            cur.execute("""
                CREATE TABLE IF NOT EXISTS word_library(
                    word_id      SERIAL PRIMARY KEY,
                    cn_text      TEXT NOT NULL,
                    kor_text     TEXT NOT NULL,
                    extra_info   TEXT,
                    library_tag  TEXT NOT NULL,
                    created_at   TIMESTAMPTZ DEFAULT now(),
                    UNIQUE(cn_text, kor_text)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS student(
                student_id      SERIAL PRIMARY KEY,
                name            TEXT NOT NULL,
                class_name      TEXT NOT NULL,
                created_at      TIMESTAMPTZ DEFAULT now()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS student_word_record(
                    record_id             SERIAL PRIMARY KEY,
                    student_id            INTEGER NOT NULL,
                    word_id               INTEGER NOT NULL,
                    review_count          INTEGER NOT NULL DEFAULT 0,
                    consecutive_correct   INTEGER NOT NULL DEFAULT 0,
                    last_result           BOOLEAN,
                    next_review_at        TIMESTAMPTZ,
                    last_review_at        TIMESTAMPTZ,
                    created_at            TIMESTAMPTZ DEFAULT now(),
                    UNIQUE(student_id, word_id)
                    )"""
                    )
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS account(
                    account_id            SERIAL PRIMARY KEY,
                    username              TEXT NOT NULL UNIQUE,
                    password_hash         TEXT NOT NULL,
                    role                  TEXT NOT NULL CHECK (role IN ('manager', 'user')),
                    student_id            INTEGER NULL,
                    created_at            TIMESTAMPTZ DEFAULT now()
                    )
                    """)

            cur.execute("ALTER TABLE word_library ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1")
            cur.execute("ALTER TABLE word_library ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE")
            cur.execute("ALTER TABLE student ADD COLUMN IF NOT EXISTS student_version INTEGER NOT NULL DEFAULT 0")
            cur.execute("ALTER TABLE student_word_record ADD COLUMN IF NOT EXISTS mastered_at TIMESTAMPTZ")
            cur.execute("ALTER TABLE student_word_record ADD COLUMN IF NOT EXISTS strength DOUBLE PRECISION NOT NULL DEFAULT 50.0")
            cur.execute("ALTER TABLE word_library ADD COLUMN IF NOT EXISTS embedding JSONB")
        conn.commit()
    finally:
        conn.close()                    # ← 连接必须靠这行显式关闭

def import_word_library(cn_text, kor_text, extra_info, library_tag, embedding=None):
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                        INSERT INTO word_library (cn_text, kor_text, extra_info, library_tag, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT(cn_text, kor_text) DO NOTHING
                        """,
        (cn_text, kor_text, extra_info, library_tag, Json(embedding) if embedding else None),
        )
            affected = cur.rowcount
        conn.commit()
        return affected
    finally:
        conn.close()

def fetch_new_words(student_id, limit=None):
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
                  SELECT word_id, cn_text, kor_text, extra_info, library_tag, version
                  from word_library w
                  WHERE NOT EXISTS(
                    SELECT 1
                    FROM student_word_record r
                    WHERE r.word_id = w.word_id AND r.student_id = %s
                    )
                    AND w.is_deleted = FALSE
                  ORDER BY w.word_id
                    """
            params = [student_id]
            if limit is not None:
                sql += " LIMIT %s"
                params.append(limit)
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def add_student(name, class_name):
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO student(name, class_name)
                VALUES(%s, %s)
                RETURNING student_id
                """,
                (name, class_name)
                )
            new_id = cur.fetchone()[0]
            conn.commit()
            return new_id
    finally:
        conn.close()

def record_answer(student_id, word_id, 
                  is_correct, word_version):
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version, is_deleted FROM word_library WHERE word_id = %s",
                        (word_id,),
                        )
            row = cur.fetchone()
            if row is None:
                return {"ok": False, "error": "word not found"}
            version, is_deleted = row
            if is_deleted:
                return {"ok": False, "error": "word deleted"}
            if version != word_version:
                return {"ok": False, "error": "version conflict"}
            
            cur.execute(
                "SELECT consecutive_correct, strength, last_review_at FROM student_word_record "  # FIX: 漏了 strength，下面解包成 3 个变量会 ValueError
                "WHERE student_id = %s AND word_id = %s",
                (student_id, word_id),
            )
            old = cur.fetchone()

            now = datetime.now(timezone.utc)
            if old is None:
                old_consec = 0
                current = srs.INITIAL_STRENGTH
            else:
                old_consec, old_strength, last_review_at = old
                current = srs.current_strength(old_strength, last_review_at, now)

            new_consec = srs.next_streak(old_consec, is_correct)
            if is_correct:
                new_strength = srs.strength_after_correct(new_consec)
            else:
                new_strength = srs.strength_after_wrong(current)  # FIX: strength_after_worng → strength_after_wrong（Wrong 拼成 Worng）

            mastered_at = now if srs.should_archive(new_strength) else None
            due_at = now + timedelta(days=srs.days_until_due(new_strength))

            cur.execute(
                """
                INSERT INTO student_word_record(student_id, word_id, review_count, consecutive_correct, last_result, strength, last_review_at, mastered_at, next_review_at)
                VALUES(%s, %s, 1, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (student_id, word_id) DO UPDATE SET
                review_count        = student_word_record.review_count + 1,
                consecutive_correct = EXCLUDED.consecutive_correct,
                last_result         = EXCLUDED.last_result,
                strength            = EXCLUDED.strength,
                last_review_at      = EXCLUDED.last_review_at,
                mastered_at         = EXCLUDED.mastered_at,
                next_review_at      = EXCLUDED.next_review_at
                """,
                (student_id, word_id, new_consec, is_correct, new_strength, now, mastered_at, due_at)
            )
            cur.execute(
            "UPDATE student SET student_version = student_version + 1 "
            "WHERE student_id = %s",
            (student_id,),
        )
        conn.commit()
        return {"ok": True, "archived":srs.should_archive(new_strength),}

    finally:
        conn.close()

def fetch_due_review_words(student_id, limit=None, now=None):
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            now = now or datetime.now(timezone.utc)
            sql = """
                  SELECT w.word_id, w.cn_text, w.kor_text, w.extra_info, w.library_tag, w.version, r.strength, r.last_review_at
                  FROM student_word_record r
                  JOIN word_library w ON w.word_id = r.word_id
                  WHERE r.student_id = %s AND r.next_review_at <= %s AND r.mastered_at IS NULL AND w.is_deleted = FALSE 
                  ORDER BY r.next_review_at
                  """
            params = [student_id, now]
            if limit is not None:
                sql += "LIMIT %s"
                params.append(limit)
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def get_student_stat(student_id, now=None):
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            now = now or datetime.now(timezone.utc)  # FIX: 漏了这行，now 默认 None 会让 due_count 恒为 0
            sql = """
                  SELECT COUNT(*) FILTER (WHERE r.record_id IS NULL) AS new_count,
                         COUNT(*) FILTER (WHERE r.record_id IS NOT NULL AND r.mastered_at IS NULL) AS learning_count,
                         COUNT(*) FILTER (WHERE r.record_id IS NOT NULL AND r.mastered_at IS NULL AND r.next_review_at <= %s) AS due_count,
                         COUNT(*) FILTER (WHERE r.mastered_at IS NOT NULL) AS mastered_count,
                         COALESCE(SUM(r.review_count), 0) AS total_reviews
                  FROM word_library w
                  LEFT JOIN student_word_record r ON r.word_id = w.word_id AND r.student_id = %s
                  WHERE w.is_deleted = FALSE
                  """
            params = [now, student_id]
            cur.execute(sql,params)
            return dict(cur.fetchone())  # FIX: fetchall 返回列表，聚合查询只有一行，应 fetchone 返回单个 dict
    finally:
        conn.close()

def get_student(student_id):
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT student_id, name, class_name FROM student WHERE student_id = %s",
                        (student_id,))
            row = cur.fetchone()
            if row is None:
                return {"ok": False, "error": "student not found"}            
            return row
    finally:
        conn.close()

def list_students():
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT student_id, name, class_name FROM student ORDER BY student_id")
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def list_words():
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT word_id, cn_text, kor_text, extra_info, library_tag, version "
                        "FROM word_library WHERE is_deleted = FALSE ORDER BY word_id")
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def get_review_batch(student_id, new_limit=5, due_limit=10, now=None):
    due_word = fetch_due_review_words(student_id, limit=due_limit, now=now)
    new_word = fetch_new_words(student_id, limit=new_limit)

    result = []
    for w in due_word:
        result.append({
            "word_id":w["word_id"],
            "version":w["version"],
            "cn_text":w["cn_text"],
            "kor_text":w["kor_text"],
            "extra_info":w["extra_info"],
            "kind":"review",
        })

    for w in new_word:
        result.append({
            "word_id":w["word_id"],
            "version":w["version"],
            "cn_text":w["cn_text"],
            "kor_text":w["kor_text"],
            "extra_info":w["extra_info"],
            "kind":"new",
        })
    return result

def _cosine(a: list[float],b: list[float]) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0

def fetch_quiz_options(word_id, count=3):
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                        "SELECT word_id, cn_text, kor_text, embedding FROM word_library "
                        "WHERE word_id = %s AND is_deleted = FALSE ",
                        (word_id,),
                        )
            row = cur.fetchone()
            correct = dict(row) if row else None

            if correct is None:
                return []
            cur.execute(
                       "SELECT word_id, cn_text, kor_text, embedding FROM word_library "
                       "WHERE word_id != %s AND is_deleted = FALSE ",
                       (word_id,),
                       )
            candidates = [dict(r) for r in cur.fetchall()]

            if correct["embedding"] is not None:
                correct_vec = correct["embedding"]
                scored = []
                for w in candidates:
                    score = _cosine(correct_vec, w["embedding"]) if w["embedding"] else 0.0
                    scored.append((score, w))
                scored.sort(key=lambda x:x[0], reverse=True)
                top = [{
                    "word_id": w["word_id"],
                    "cn_text": w["cn_text"],
                    "kor_text": w["kor_text"]}
                    for score, w in scored[:count]]
            else:
                cur.execute(
                            "SELECT word_id, cn_text, kor_text, embedding FROM word_library "
                            "WHERE word_id != %s AND is_deleted = FALSE "
                            "ORDER BY random() LIMIT %s",
                            (word_id, count),
                            )
                top = [{
                        "word_id": row["word_id"],
                        "cn_text": row["cn_text"],
                        "kor_text": row["kor_text"]
                        }
                        for row in cur.fetchall()]
                
            correct = {"word_id": correct["word_id"],
                       "cn_text": correct["cn_text"],
                       "kor_text": correct["kor_text"]}
            return [correct] + top
    finally:
        conn.close()
        
def get_words_without_embedding():
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT word_id, cn_text, kor_text FROM word_library "
                "WHERE embedding IS NULL AND is_deleted = FALSE ORDER BY word_id"
            )
            return[dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def update_word_embedding(word_id, embedding):
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("UPDATE word_library SET embedding = %s WHERE word_id = %s",
                        (Json(embedding), word_id),
                        )
            conn.commit()
            return cur.rowcount
    finally:
        conn.close()

def update_word(word_id, cn_text, kor_text, extra_info):
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version, is_deleted FROM word_library WHERE word_id = %s ",
                        (word_id,))
            row = cur.fetchone()
            if row is None:
                return {"ok": False, "error": "word not found"}
            if row[1]:
                return {"ok":False, "error":"word deleted"}
            
            cur.execute(
                        "UPDATE word_library "
                        "SET cn_text=%s, kor_text=%s, extra_info=COALESCE(%s, extra_info), version=version+1, embedding=NULL "
                        "WHERE word_id=%s ",
                        (cn_text, kor_text, extra_info, word_id),
                        )
            conn.commit()
            return {"ok":True}      
        
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return {"ok":False, "error":"duplicate"}
    
    finally:
        conn.close()

def delete_word(word_id):
    conn = _get_connection()
    try:
        with conn.cursor() as cur:

            cur.execute("SELECT is_deleted FROM word_library WHERE word_id = %s", (word_id,))
            row = cur.fetchone()
            if row is None:
                return {"ok":False, "error":"word not found"}
            if row[0]:
                return {"ok":False, "error":"word deleted"}

            cur.execute("UPDATE word_library SET is_deleted = TRUE WHERE word_id = %s", (word_id,))
            conn.commit()
            return {"ok": True}
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    init_db()

    sid = add_student("测试员", "一班")
    import_word_library("苹果", "사과", "水果", "基础词汇")
    words = fetch_new_words(sid, limit=1)
    w = words[0]
    word_id, version = w["word_id"], w["version"]
    print("拿到词:", w["cn_text"], w["kor_text"], "word_id=", word_id, "version=", version)

    # 连续答对 4 次：温度 60→70→80→90，第 4 次达到归档线
    for i in range(4):
        r = record_answer(sid, word_id, True, version)
        print(f"第{i+1}次答对 ->", r)

    # 读回数据库，验证温度 + 归档落库
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT consecutive_correct, strength, mastered_at "
                "FROM student_word_record WHERE student_id = %s AND word_id = %s",
                (sid, word_id),
            )
            print("数据库里的记录:", cur.fetchone())
    finally:
        conn.close()

    # 答错测试：另一个学生第一次就答错，温度从 50 腰斩到 25
    sid2 = add_student("测试员2", "一班")
    print("新学生第一次答错 ->", record_answer(sid2, word_id, False, version))

    # 错版本：验证乐观锁
    print("错版本 ->", record_answer(sid, word_id, True, 999))

    # 到期复习测试：新建学生答对一次（温度 60，未归档，所以不会被 mastered_at 过滤掉）
    # 关键：用 now 参数「假装时间已经过去」，不用真的 sleep 7 天
    from datetime import timedelta
    sid3 = add_student("测试员3", "一班")
    record_answer(sid3, word_id, True, version)
    print("刚答完(温度60>30, 不该到期) ->", fetch_due_review_words(sid3))
    print("模拟7天后(60*0.9^7≈28.7<30, 该到期) ->",
          fetch_due_review_words(sid3, now=datetime.now(timezone.utc) + timedelta(days=7)))

    # 学情统计测试：库中只有 1 个词，三个学生各自不同的状态
    print("sid  学情(已掌握)      ->", get_student_stat(sid))
    print("sid2 学情(答错,立即到期) ->", get_student_stat(sid2))
    print("sid3 学情(学习中,未到期) ->", get_student_stat(sid3))

    #批量测试：学生批量作答获取作答后的状态
    import_word_library("香蕉", "바나나", "水果", "基础词汇")
    import_word_library("水", "물", "日常", "基础词汇")
    import_word_library("面包", "빵", "食物", "基础词汇")
    import_word_library("书", "책", "学习", "基础词汇")
    import_word_library("桌子", "책상", "家具", "基础词汇")
    import_word_library("太阳", "태양", "自然", "基础词汇")
    import_word_library("月亮", "달", "自然", "基础词汇")
    import_word_library("朋友", "친구", "人际", "基础词汇")
    import_word_library("学校", "학교", "学习", "基础词汇")
    words = fetch_new_words(sid)
    sid4 = add_student("测试员4", "一班")
    for w in words[:2]:
        record_answer(sid4, w["word_id"], False, w["version"])
    print("sid4 学情(答错两个,立即到期) ->", get_student_stat(sid4))
    batch = get_review_batch(sid4)
    print("批次总数:", len(batch))
    for w in batch:
        print(w["cn_text"], "->", w["kind"])

    #选项测试：拿到的选项是否是语义最相近的内容
    options = fetch_quiz_options(word_id=1, count=3)
    print("选项数:", len(options))
    for opt in options:
        print(opt["word_id"], opt["cn_text"], opt["kor_text"])