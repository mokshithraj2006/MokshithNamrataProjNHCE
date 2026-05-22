# Flask Certificate Validator MVP

Working prototype for certificate authenticity validation using OCR, database checks, SHA-256 hashing, and linked-hash integrity.

## Tech Stack
- Python
- Flask
- SQLite
- Tesseract OCR (`pytesseract`)

## Features
- Upload certificate (`.pdf`, `.jpg`, `.jpeg`, `.png`, max `5MB`)
- OCR text extraction with preprocessing (grayscale + threshold)
- Regex extraction for `Name`, `USN`, `CGPA`, `Year`
- Student data validation from SQLite
- SHA-256 hash generation and linked-hash ledger (`hash_chain`)
- Final decision: `VALID` / `TAMPERED`
- Confidence score:
  - OCR success: +30
  - DB match: +40
  - Hash/chain check: +30
- Admin dashboard:
  - total verifications
  - valid count
  - tampered count
  - recent verification logs

## Setup (Windows)
1. Install Python 3.10+.
2. Install Tesseract OCR and add it to PATH.
   - Download: [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
3. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
4. Initialize database:
   ```bash
   python -c "import app; app.init_db(); print('db initialized')"
   ```
5. Run app:
   ```bash
   python app.py
   ```
6. Open:
   - `http://127.0.0.1:5000/`
   - Admin: `http://127.0.0.1:5000/admin`

## Seed Student Records
The app seeds demo records automatically on first DB init.

## Demo Runbook (Review 1)
1. Upload a valid certificate matching seeded student data.
2. Show:
   - `VALID`
   - high confidence
   - extracted fields
3. Upload a tampered certificate (edited CGPA/name/year).
4. Show:
   - `TAMPERED`
   - mismatch reasons
5. Open admin dashboard and show totals + recent activity.

## Suggested Demo Line
“We implemented a multi-layer authenticity validation pipeline combining OCR extraction, database cross-verification, cryptographic hashing, and blockchain-inspired linked-hash integrity checks.”
