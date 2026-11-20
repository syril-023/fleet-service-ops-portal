# Admin tool — set portal user passwords (bcrypt)
#
#   py set_password.py <username>     → asks for a new password (hidden typing)
#   py set_password.py --init-all     → gives every user WITHOUT a real password
#                                       a random temporary one, saved to
#                                       initial_passwords.txt (gitignored).
#                                       Hand them out, then DELETE that file.

import sys
import secrets
import getpass
import bcrypt
import psycopg2
from db_config import DB_CONFIG


def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()


def is_real_hash(h):
    # real bcrypt hashes are 60 chars: $2b$12$...
    return bool(h) and len(h) == 60 and h.startswith("$2")


def set_one(username):
    pw = getpass.getpass(f"New password for '{username}': ")
    if len(pw) < 8:
        print("Password must be at least 8 characters.")
        return
    if pw != getpass.getpass("Repeat password: "):
        print("Passwords do not match.")
        return
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""UPDATE users SET password_hash=%s, must_change_password=FALSE,
                   updated_at=NOW() WHERE LOWER(username)=LOWER(%s)""", (hash_pw(pw), username))
    conn.commit()
    print("Password updated." if cur.rowcount else f"No user named '{username}'.")
    conn.close()


def init_all():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, password_hash FROM users ORDER BY user_id")
    lines = []
    for uid, uname, h in cur.fetchall():
        if is_real_hash(h):
            continue
        pw = secrets.token_urlsafe(9)
        cur.execute("""UPDATE users SET password_hash=%s, must_change_password=TRUE,
                       updated_at=NOW() WHERE user_id=%s""", (hash_pw(pw), uid))
        lines.append(f"{uname:<12} {pw}")
    conn.commit()
    conn.close()
    if not lines:
        print("All users already have real passwords.")
        return
    with open("initial_passwords.txt", "w") as f:
        f.write("Temporary portal passwords — hand out, then DELETE this file\n\n")
        f.write("\n".join(lines) + "\n")
    print(f"Set {len(lines)} temporary passwords → initial_passwords.txt")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__ or "Usage: py set_password.py <username> | --init-all")
    elif sys.argv[1] == "--init-all":
        init_all()
    else:
        set_one(sys.argv[1])
