import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from blockchain_module import add_hash_record, get_latest_hash_for_usn, verify_chain_integrity
from hash_module import sha256_bytes
from ocr_module import extract_text
from validation_module import calculate_confidence, extract_fields, validate_against_db


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "database.db"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_SIZE_MB = 5


app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key"
app.config["MAX_CONTENT_LENGTH"] = MAX_SIZE_MB * 1024 * 1024


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def init_db() -> None:
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            usn TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            cgpa REAL NOT NULL,
            year INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hash_chain (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_hash TEXT NOT NULL,
            prev_hash TEXT,
            timestamp TEXT NOT NULL,
            usn TEXT
        )
        """
    )
    hash_chain_columns = [
        row["name"] for row in conn.execute("PRAGMA table_info(hash_chain)").fetchall()
    ]
    if "usn" not in hash_chain_columns:
        conn.execute("ALTER TABLE hash_chain ADD COLUMN usn TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence INTEGER NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    existing = conn.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
    if existing == 0:
        conn.executemany(
            "INSERT INTO students (usn, name, cgpa, year) VALUES (?, ?, ?, ?)",
            [
                ("1RV21CS001", "Aarav Sharma", 8.9, 2024),
                ("1RV21CS002", "Diya Rao", 9.2, 2024),
                ("1RV21CS003", "Neel Verma", 8.4, 2023),
                ("1RV21CS004", "Ishita Nair", 9.5, 2025),
                ("1RV21CS005", "Karan Mehta", 8.1, 2024),
            ],
        )
    conn.execute(
        "INSERT OR REPLACE INTO students (usn, name, cgpa, year) VALUES (?, ?, ?, ?)",
        ("1NZ24CS114", "Mokshith Raj", 8.75, 2025),
    )
    conn.commit()
    conn.close()


def log_verification(filename: str, status: str, confidence: int, reason: str) -> None:
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO verification_logs (filename, status, confidence, reason, created_at) VALUES (?, ?, ?, ?, ?)",
        (filename, status, confidence, reason, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


@app.errorhandler(413)
def request_entity_too_large(_error):
    flash(f"File too large. Maximum allowed size is {MAX_SIZE_MB}MB.")
    return redirect(url_for("index"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/verify", methods=["POST"])
def verify():
    if "certificate" not in request.files:
        flash("No file part in request.")
        return redirect(url_for("index"))

    file = request.files["certificate"]
    if file.filename == "":
        flash("No file selected.")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Unsupported file type. Allowed: PDF, JPG, JPEG, PNG.")
        return redirect(url_for("index"))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(file.filename)
    file_path = UPLOAD_DIR / filename
    file.save(file_path)

    file_bytes = file_path.read_bytes()
    cert_hash = sha256_bytes(file_bytes)

    try:
        ocr_result = extract_text(str(file_path))
    except Exception as exc:
        flash(f"OCR processing failed: {exc}")
        return redirect(url_for("index"))
    fields = extract_fields(ocr_result["text"])

    conn = get_db_connection()
    db_match, reasons = validate_against_db(conn, fields)
    extracted_usn = fields.get("usn")

    chain_integrity = verify_chain_integrity(conn)
    hash_rule_ok = False
    already_seen = False

    if extracted_usn:
        existing_usn_hash = get_latest_hash_for_usn(conn, extracted_usn)
        if existing_usn_hash is None:
            add_hash_record(conn, cert_hash, extracted_usn)
            hash_rule_ok = True
        elif existing_usn_hash == cert_hash:
            hash_rule_ok = True
            already_seen = True
        else:
            hash_rule_ok = False
            reasons.append(
                "Certificate hash mismatch for this USN. Possible tampering detected."
            )
    else:
        reasons.append("USN missing in extracted fields, cannot enforce hash integrity.")

    chain_and_hash_ok = chain_integrity and hash_rule_ok
    conn.close()

    confidence = calculate_confidence(bool(ocr_result["ocr_success"]), db_match, chain_and_hash_ok)
    status = "VALID" if (ocr_result["ocr_success"] and db_match and chain_and_hash_ok) else "TAMPERED"

    if not ocr_result["ocr_success"]:
        reasons.append("OCR extraction quality is low.")
    if not chain_integrity:
        reasons.append("Hash chain integrity check failed.")

    reason_text = " | ".join(reasons) if reasons else "All checks passed."
    log_verification(filename, status, confidence, reason_text)

    return render_template(
        "result.html",
        status=status,
        confidence=confidence,
        fields=fields,
        reasons=reasons,
        hash_value=cert_hash,
        ocr_source=ocr_result["source"],
        seen_before=already_seen,
    )


@app.route("/admin")
def admin():
    conn = get_db_connection()
    total = conn.execute("SELECT COUNT(*) AS count FROM verification_logs").fetchone()["count"]
    valid = conn.execute(
        "SELECT COUNT(*) AS count FROM verification_logs WHERE status = 'VALID'"
    ).fetchone()["count"]
    tampered = conn.execute(
        "SELECT COUNT(*) AS count FROM verification_logs WHERE status = 'TAMPERED'"
    ).fetchone()["count"]
    recent = conn.execute(
        """
        SELECT filename, status, confidence, reason, created_at
        FROM verification_logs
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()
    conn.close()
    return render_template(
        "admin.html",
        total=total,
        valid=valid,
        tampered=tampered,
        recent=recent,
    )


if __name__ == "__main__":
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    init_db()
    app.run(debug=True)



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)