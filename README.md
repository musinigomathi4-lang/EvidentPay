# EvidentPay

EvidentPay helps event organisers review UPI payment claims by extracting details from participant screenshots and, when available, comparing those claims with credits in the recipient-side bank statement.

## How it works

1. Create an event with its name, registration fee and expected participant count.
2. Upload one or more UPI payment screenshots.
3. Tesseract OCR reads the screenshot. The Python parser extracts amount, UTR/reference, transaction date/time, sender label, payment status and receipt-app clues.
4. Import the recipient-side bank statement as CSV or text-based PDF when available.
5. The deterministic reconciliation service compares screenshot claims with incoming bank credits and reports matches, duplicates, discrepancies and items needing review.
6. If no bank statement is available, run screenshot-only evidence analysis. This reports metadata and image indicators; it does **not** confirm that money was received or prove that a screenshot is genuine.

## Architecture

- **Frontend:** React 19 + Vite
- **API:** FastAPI
- **Database:** SQLite via SQLAlchemy
- **OCR:** Tesseract via pytesseract, with OpenCV preprocessing
- **Statement parsing:** pandas for CSV and pdfplumber for text-based PDF
- **Image evidence:** metadata inspection, ELA and noise measurements

The screenshot dataset is used for evaluation and testing. Runtime OCR does not look up a screenshot in the dataset. Tesseract is a pre-trained general OCR engine; EvidentPay applies Python rules to interpret common UPI receipt labels. Common formats from Google Pay, PhonePe, Paytm and BHIM are targeted, but heavily blurred, cropped, obscured or unfamiliar layouts can still require manual review.

## Requirements

- Python 3.10 or newer (Python 3.11 is a good default)
- Node.js 20.19+ (for the current Vite version)
- Tesseract OCR installed separately
- Windows, macOS or Linux

### Install Tesseract on Windows

1. Install the Tesseract OCR Windows package.
2. Confirm the executable exists, commonly at `C:\Program Files\Tesseract-OCR\tesseract.exe`.
3. If it is installed elsewhere, set `TESSERACT_CMD` to the full executable path before starting the backend.

Tesseract is a system dependency; installing `pytesseract` with pip alone does not install the OCR executable.

## Run locally (Windows PowerShell)

### 1. Backend

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
uvicorn main:app --reload
```

The API runs at http://localhost:8000. Interactive API documentation is at http://localhost:8000/docs. SQLite is created automatically at `backend/evidentpay.db`.

If Tesseract is already on PATH, the `TESSERACT_CMD` line can be omitted.

### 2. Frontend (a second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally http://localhost:5173). The frontend defaults to the API at http://localhost:8000. To use a different API URL, create `frontend/.env.local` with:

```env
VITE_API_URL=http://localhost:8000
```

Restart Vite after changing environment variables.

## Tests

Run from the repository root after installing backend dependencies:

```powershell
python -m pytest tests/test_ocr_parsers.py tests/test_matching.py
```

The OCR evaluation report can be run against the labelled screenshot set with:

```powershell
python tests/test_ocr.py
```

For an unlabelled folder of screenshots (including screenshots from other apps or themes):

```powershell
python tests/test_ocr.py --survey "path\to\screenshots"
```

Review the extracted values against the original images. A low OCR confidence or missing field should be manually checked.

## Important interpretation notes

- A screenshot is a **claim**, not proof of receipt.
- Only a matching recipient-side incoming bank credit can be reported as a confirmed payment.
- Screenshot-only analysis is an evidence review, not a fake/genuine classifier. ELA, metadata and noise can change because of normal compression, resizing or sharing.
- Missing metadata is common and is not evidence that an image is genuine. Editor metadata is an indicator for review, not proof of fraud.
- OCR never should invent missing sender names, amounts, dates or UTRs. Missing or conflicting fields must remain empty and be flagged for review.
- Do not commit real payment screenshots, bank statements, database files, API keys or other personal financial data to a public repository. Use synthetic or explicitly consented, redacted test data.
