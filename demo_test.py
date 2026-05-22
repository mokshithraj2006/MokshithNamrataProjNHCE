from pathlib import Path

from PIL import Image, ImageDraw

import app
from blockchain_module import add_hash_record, hash_exists, verify_chain_integrity
from hash_module import sha256_bytes
from ocr_module import extract_text
from validation_module import calculate_confidence, extract_fields, validate_against_db


def create_sample(path: Path, name: str, usn: str, cgpa: str, year: str) -> None:
    img = Image.new("RGB", (900, 450), "white")
    draw = ImageDraw.Draw(img)
    content = f"Name: {name}\nUSN: {usn}\nCGPA: {cgpa}\nYear: {year}\n"
    draw.text((40, 40), content, fill="black")
    img.save(path)


def run_case(file_path: Path):
    conn = app.get_db_connection()
    cert_hash = sha256_bytes(file_path.read_bytes())
    ocr_result = extract_text(str(file_path))
    fields = extract_fields(ocr_result["text"])
    db_match, reasons = validate_against_db(conn, fields)
    chain_ok = verify_chain_integrity(conn)
    if not hash_exists(conn, cert_hash):
        add_hash_record(conn, cert_hash)
    conn.close()
    confidence = calculate_confidence(bool(ocr_result["ocr_success"]), db_match, chain_ok)
    status = "VALID" if (ocr_result["ocr_success"] and db_match and chain_ok) else "TAMPERED"
    return status, confidence, reasons


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    samples_dir = base / "uploads"
    samples_dir.mkdir(exist_ok=True)

    app.init_db()
    valid_file = samples_dir / "sample_valid.png"
    tampered_file = samples_dir / "sample_tampered.png"

    create_sample(valid_file, "Aarav Sharma", "1RV21CS001", "8.9", "2024")
    create_sample(tampered_file, "Aarav Sharma", "1RV21CS001", "7.1", "2024")

    try:
        valid_result = run_case(valid_file)
        tampered_result = run_case(tampered_file)
    except RuntimeError as exc:
        print(f"Demo test blocked: {exc}")
        raise SystemExit(1)

    print("VALID CASE:", valid_result)
    print("TAMPERED CASE:", tampered_result)
