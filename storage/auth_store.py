from storage.wordbook_store import _get_connection
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets, string

def create_account(username, password, role, student_id=None):
    conn = _get_connection()
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    password_hash = hashed.decode("utf-8")
    try:
        with conn.cursor() as cur:
                cur.execute("""
                INSERT INTO account(username, password_hash, role, student_id)
                VALUES(%s, %s, %s, %s) 
                RETURNING account_id
                """,
                (username, password_hash, role, student_id),)
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id
    finally:
         conn.close()

def get_account_by_username(username):
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT password_hash, role, student_id, account_id FROM account WHERE username = %s",
            (username,))
            row = cur.fetchone()       
            return row
    finally:
        conn.close()

def create_student_account(name, class_name, username):
     conn = _get_connection()
     try:
          with conn.cursor() as cur:
               cur.execute( """
                            INSERT INTO student(name, class_name)
                            VALUES(%s, %s)
                            RETURNING student_id
                            """,
                            (name, class_name))
               sid = cur.fetchone()[0]
               alphabet = string.ascii_letters + string.digits
               password = "".join(secrets.choice(alphabet) for _ in range(8))
               password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
               cur.execute( """
                            INSERT INTO accountusername, password_hash, role, student_id)
                            VALUES(%s, %s, 'user', %s)
                            RETURNING account_id
                            """,
                            (username, password_hash, sid))
               aid = cur.fetchone()[0]
               conn.commit()
               return {"ok": True, "student_id": sid, "account_id": aid, "password":password}
     except psycopg2.errors.UniqueViolation: 
          conn.rollback()
          return {"ok": False, "error": "username exists"}
     finally:
          conn.close()

def get_account_by_id(account_id):
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT password_hash, role, student_id, account_id FROM account WHERE account_id = %s",
            (account_id,))
            row = cur.fetchone()
            return row
    finally:
        conn.close()

def update_password(account_id, new_password_hash):
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE account SET password_hash = %s WHERE account_id = %s",
                       (new_password_hash, account_id))
            conn.commit()
            return {"ok":True}
    finally:
        conn.close()