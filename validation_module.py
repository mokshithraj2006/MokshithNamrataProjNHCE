import re
import sqlite3
from typing import Dict, List, Tuple


FIELD_PATTERNS = {
    "name": re.compile(r"Name\s*:\s*(.+)", re.IGNORECASE),
    "usn": re.compile(r"USN\s*:\s*([A-Za-z0-9\-\/]+)", re.IGNORECASE),
    "cgpa": re.compile(r"CGPA\s*:\s*([0-9]\.[0-9]+)", re.IGNORECASE),
    "year": re.compile(r"Year\s*:\s*(20[0-9]{2})", re.IGNORECASE),
}


def extract_fields(text: str) -> Dict[str, str]:
    extracted: Dict[str, str] = {}
    for field, pattern in FIELD_PATTERNS.items():
        match = pattern.search(text)
        if match:
            extracted[field] = match.group(1).strip()
    return extracted


def _normalize_name(name: str) -> str:
    return " ".join(name.upper().split())


def validate_against_db(conn: sqlite3.Connection, fields: Dict[str, str]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    usn = fields.get("usn")
    if not usn:
        reasons.append("USN not found in OCR output.")
        return False, reasons

    row = conn.execute(
        "SELECT usn, name, cgpa, year FROM students WHERE usn = ?",
        (usn,),
    ).fetchone()
    if not row:
        reasons.append(f"USN {usn} does not exist in student database.")
        return False, reasons

    _, db_name, db_cgpa, db_year = row
    is_valid = True

    name = fields.get("name")
    if not name:
        is_valid = False
        reasons.append("Name not found in OCR output.")
    elif _normalize_name(name) != _normalize_name(db_name):
        is_valid = False
        reasons.append(f"Name mismatch: expected '{db_name}', got '{name}'.")

    cgpa = fields.get("cgpa")
    if not cgpa:
        is_valid = False
        reasons.append("CGPA not found in OCR output.")
    elif abs(float(cgpa) - float(db_cgpa)) > 0.01:
        is_valid = False
        reasons.append(f"CGPA mismatch: expected {db_cgpa}, got {cgpa}.")

    year = fields.get("year")
    if not year:
        is_valid = False
        reasons.append("Year not found in OCR output.")
    elif int(year) != int(db_year):
        is_valid = False
        reasons.append(f"Year mismatch: expected {db_year}, got {year}.")

    return is_valid, reasons


def calculate_confidence(ocr_success: bool, db_match: bool, chain_and_hash_ok: bool) -> int:
    score = 0
    if ocr_success:
        score += 30
    if db_match:
        score += 40
    if chain_and_hash_ok:
        score += 30
    return score
