# FPT_FAP_CHAT — Intent-Aware Academic Retrieval System

## Overview

FPT_FAP_CHAT is an applied AI project for retrieving academic information from FPT University data sources. It combines semantic retrieval with query-intent and metadata processing so that questions about curricula, course materials, assessments, learning outcomes, schedules, grades, and attendance can be routed to relevant records.

The repository contains two related workflows:

- a Flask API for querying processed curriculum data in Qdrant; and
- a command-line pipeline for collecting student-authorized FAP data, synchronizing it with MySQL, embedding it with BGE-M3, and searching it through Qdrant.

The project is a research and prototyping artifact. It is not presented as a production-ready student information system, and generated student data is intentionally excluded from the public repository.

![Web retrieval demo](static/demo.JPG)

## Key Features

- Semantic retrieval using `BAAI/bge-m3` embeddings and Qdrant vector search
- Query-type, subject, semester, and time-range processing for metadata-aware retrieval
- Optional Gemini-based intent extraction, result reranking, and answer synthesis
- Fallback query translation and embedding-based classification in the Flask workflow
- Selenium-based FAP and FLM data collection utilities
- MySQL synchronization for student-authorized FAP records
- Data-preparation and evaluation experiments preserved in Jupyter notebooks

## System Architecture

The Flask curriculum-retrieval path follows this flow:

```text
User query
    ↓
Gemini intent analysis (or local fallback)
    ↓
Type / subject / semester metadata
    ↓
BGE-M3 query embedding
    ↓
Filtered Qdrant retrieval
    ↓
Gemini answer synthesis
    ↓
JSON API response
```

The CLI pipeline additionally supports authorized FAP scraping, MySQL synchronization, payload construction, and ingestion into a student-data collection before retrieval.

## Evaluation

The repository includes exploratory intent-analysis and retrieval-evaluation notebooks under `notebook/`. No consolidated, reproducible benchmark report is currently included, so this README does not claim verified F1 or latency results.

## Tech Stack

- Python, pandas, NumPy, and scikit-learn
- Flask and Flask-CORS
- Sentence Transformers with BGE-M3
- Qdrant
- Gemini API (`google-generativeai` and REST calls)
- Hugging Face Transformers
- MySQL with PyMySQL and SQLAlchemy
- Selenium, Beautiful Soup, and webdriver-manager
- Jupyter notebooks for data preparation and experiments

## Repository Structure

```text
FPT_FAP_CHAT/
├── app.py                      # Flask curriculum-retrieval API
├── code1/
│   ├── main.py                 # Interactive FAP ingestion and search pipeline
│   ├── FAP/                    # FAP scraper, embedding, retrieval, and LLM helpers
│   ├── FLM/                    # Curriculum/syllabus scraper and parsers
│   └── Cloud/                  # MySQL utilities and examples
├── data/
│   ├── Chunk_JSON/             # Processed public curriculum chunks
│   ├── DATA cố định/FLM/       # Curriculum and syllabus research data
│   └── FAP/                    # Local-only student data directory (ignored by Git)
├── notebook/                   # Research and preprocessing notebooks
├── static/                     # Portfolio demo image
├── templates/                  # Web UI prototypes
├── .env.example                # Configuration template
└── requirements.txt
```

## Configuration

Create a local environment file from the provided template:

```bash
cp .env.example .env
```

| Variable | Purpose | Required |
| --- | --- | --- |
| `QDRANT_URL` | Qdrant endpoint | Yes |
| `QDRANT_API_KEY` | Qdrant credential | Yes for secured deployments |
| `QDRANT_WEB_COLLECTION` | Curriculum collection used by `app.py` | No; defaults to `flm_fap` |
| `QDRANT_COLLECTION` | Student-data collection used by the CLI | No; defaults to `Fap_data_testing` |
| `GEMINI_API_KEY` | Gemini intent analysis and response synthesis | Optional |
| `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB` | MySQL connection used by the CLI | Required for cloud synchronization |
| `EDGE_USER_DATA_DIR` | Local Edge profile used by the FLM scraper | Required only for that scraper |

Never commit `.env`, credentials, browser profiles, or exported student records.

## Installation

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\activate`.

## Usage

### Flask retrieval API

After configuring Qdrant and, optionally, Gemini:

```bash
python app.py
```

Submit a JSON request to `POST /api/search`:

```json
{
  "query": "What are the learning outcomes for CPV301?"
}
```

The application loads BGE-M3 and translation models at startup, so the first launch can require model downloads and substantial memory.

### Interactive FAP pipeline

Student records are deliberately not included. Place your own authorized CSV exports in `data/FAP/` or configure the MySQL synchronization used by the pipeline, then run:

```bash
cd code1
python main.py
```

The expected local filenames are `student_profile.csv`, `attendance_reports.csv`, `grade_details.csv`, and `course_summaries.csv`. Treat these files as private; Git ignores them by default.

## Project Scope and Data Ethics

This repository demonstrates intent-aware retrieval and RAG techniques over academic information. The scraping utilities should only be used with accounts and records the operator is authorized to access. Real student profiles, identifiers, contact details, attendance, grades, schedules, database checkpoints, and derived vector payloads are excluded from version control.

The large FLM files are retained as research inputs for curriculum retrieval. Review their provenance and redistribution permissions before publishing or redistributing the dataset outside this project.

## Supporting Documentation

- [Query Classification Guide](QUERY_CLASSIFICATION_GUIDE.md)
- [Query Pattern Analysis](QUERY_PATTERNS_ANALYSIS.md)
- [User Guide](USER_GUIDE.md)
