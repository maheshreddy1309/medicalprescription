# MedScript AI — Medical Prescription Detection System

A deep learning + OCR powered web application that detects and extracts text from medical prescriptions.

---

## Features
- Upload handwritten or printed prescription images
- AI image preprocessing pipeline (grayscale, contrast, binarization, scaling)
- Multi-pass Tesseract OCR for maximum text extraction
- OCR confidence scoring
- Medical keyword detection
- Symptom-based disease prediction (SVM model)
- Medicine, diet, workout recommendations

---

## Tech Stack
- **Backend**: Python, Flask
- **OCR Engine**: Tesseract OCR (via pytesseract)
- **Image Processing**: Pillow (PIL)
- **ML Model**: Support Vector Machine (SVM / scikit-learn)
- **Frontend**: HTML5, CSS3, Vanilla JS

---

## Setup & Run (Mac)

### 1. Install Tesseract
```bash
brew install tesseract
```

### 2. Activate virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the app
```bash
python app.py
```

### 5. Open in browser
```
http://127.0.0.1:5000
```

---

## Project Structure
```
MedPrescription/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── dataset/                # CSV datasets
├── models/
│   └── svc.pkl             # Trained SVM model
├── static/
│   └── uploads/            # Uploaded images
└── templates/
    ├── index.html          # Main dashboard
    └── prescriptions.html  # History page
```

---

## How OCR Pipeline Works
1. Image uploaded by user
2. Converted to grayscale
3. Proportionally scaled to high resolution
4. Contrast enhanced (2x)
5. Double sharpening filter applied
6. Binarized (black/white threshold)
7. Three Tesseract configs tried — best result selected
8. Confidence score computed per-word
9. Medical keywords extracted from result
