# SoToxa Drug Fluid Test Result Management System

A comprehensive system for managing and processing drug test results using OCR technology.

## Features

- Upload and process drug test scan results
- OCR-based data extraction
- Secure data storage with MongoDB
- Role-based access control
- Dashboard for result analysis
- Export capabilities

## Tech Stack

- Backend: FastAPI (Python 3.10+)
- Database: MongoDB
- OCR Engine: Tesseract
- Authentication: JWT/OAuth2
- File Storage: Local/S3

## Getting Started

### Prerequisites

- Python 3.10+
- MongoDB
- Tesseract OCR

### Installation

1. Clone the repository:
```bash
git clone https://github.com/nk1947-sudo/SoToxa-Drug-Fluid-Test-Result-Management-System.git
cd SoToxa-Drug-Fluid-Test-Result-Management-System
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create .env file:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run the application:
```bash
uvicorn app.main:app --reload
```

## API Documentation

Once running, access the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

[MIT License](LICENSE)
