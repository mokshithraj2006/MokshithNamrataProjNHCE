import sqlite3
from datetime import datetime
from typing import Optional


def _utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def get_last_hash(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute(
        "SELECT cert_hash FROM hash_chain ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def hash_exists(conn: sqlite3.Connection, cert_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM hash_chain WHERE cert_hash = ? LIMIT 1", (cert_hash,)
    ).fetchone()
    return bool(row)


def get_latest_hash_for_usn(conn: sqlite3.Connection, usn: str) -> Optional[str]:
    row = conn.execute(
        "SELECT cert_hash FROM hash_chain WHERE usn = ? ORDER BY id DESC LIMIT 1",
        (usn,),
    ).fetchone()
    return row[0] if row else None


def add_hash_record(conn: sqlite3.Connection, cert_hash: str, usn: Optional[str] = None) -> None:
    prev_hash = get_last_hash(conn)
    conn.execute(
        "INSERT INTO hash_chain (cert_hash, prev_hash, timestamp, usn) VALUES (?, ?, ?, ?)",
        (cert_hash, prev_hash, _utc_now(), usn),
    )
    conn.commit()


def verify_chain_integrity(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        "SELECT id, cert_hash, prev_hash FROM hash_chain ORDER BY id ASC"
    ).fetchall()
    previous = None
    for _, cert_hash, prev_hash in rows:
        if prev_hash != previous:
            return False
        previous = cert_hash
    return True
