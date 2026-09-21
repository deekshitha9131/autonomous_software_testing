# Agentic GenAI Framework for Autonomous Software Testing

## Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
    - Windows: `venv\Scripts\activate`
    - Unix/Linux/macOS: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Create a `.env` file (see `.env.example`)

## Run

```bash
uvicorn main:app --reload
```

## Test

```bash
pytest
```

## Project Structure

```
.
├── app
│   ├── api
│   │   ├── v1
│   │   │   ├── health.py
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── core
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── __init__.py
│   ├── __init__.py
│   └── main.py
├── tests
│   ├── __init__.py
│   └── test_health.py
├── requirements.txt
├── README.md
└── pytest.ini
```

## License

MIT
