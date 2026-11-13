# Gen AI Customer Service Bot

An AI-powered customer service support system developed as an internship extension project. It combines Retrieval-Augmented Generation (RAG), multimodal document analysis, automated ticket management, sentiment analysis, escalation workflows, multilingual language processing, and an automated knowledge-base update pipeline.

## Project Overview

The system is designed to improve customer support by automating common support operations, retrieving relevant knowledge-base information, analyzing customer sentiment, processing documents, and managing support tickets.

## Project Status

| Module | Status |
|---|---|
| Knowledge-Base Update Pipeline | Implemented |
| Multimodal Document Analysis | Implemented |
| Automated Ticket Management | Implemented |
| RAG Knowledge Assistant | Implemented |
| Sentiment Analysis and Escalation | Implemented |
| Language Detection and Session Management | Implemented |
| Translation Support | Implemented |
| Monitoring | Implemented |
| Scheduling and Deployment | Implemented |
| Chatbot Integration | Implemented |

**Automated Testing:** 96 tests passed successfully.

## Key Features

### 1. Knowledge-Base Update Pipeline
- Detects new and modified documents.
- Identifies duplicate documents.
- Supports document versioning.
- Validates updates using a quality gate.
- Supports rollback to previous versions.
- Evaluates retrieval accuracy and grounding before activating updates.

### 2. Multimodal Document Analysis
- Processes invoice images and PDF documents.
- Extracts information using OCR.
- Detects mismatched values and missing information.
- Validates file types, sizes, and image quality.
- Detects hidden instructions in uploaded documents.
- Protects sensitive information in logs and storage.
- Supports background processing and configurable file retention.

### 3. Automated Ticket Management
- Extracts ticket information from conversations.
- Detects duplicate issues.
- Assigns ticket priorities.
- Routes tickets to appropriate teams.
- Handles after-hours requests.
- Calculates SLA deadlines and warnings.
- Supports escalation and agent handoffs.

### 4. RAG Knowledge Assistant
- Retrieves relevant knowledge-base documents.
- Supports role-based access control.
- Applies policy-date filtering.
- Supports historical policy queries.
- Provides source citations.
- Detects unsupported claims.
- Protects against prompt injection.

### 5. Sentiment Analysis and Escalation
- Supports six sentiment labels.
- Analyzes conversation history.
- Handles sarcasm and multilingual inputs.
- Detects high-risk conversations.
- Escalates repeated or unresolved negative conversations.
- Adjusts response tone based on customer sentiment.

### 6. Language Processing and Session Management
- Detects English, Hindi, Kannada, Tamil, Hinglish, and mixed-language inputs.
- Supports language switching.
- Manages customer sessions.
- Handles inactivity timeouts and session restoration.
- Maintains limited conversation history.

### 7. Translation Support
- Uses an injectable translation engine.
- Protects order IDs and custom terms.
- Validates translation output.

### 8. Monitoring
- Monitors sentiment and ticket services.
- Handles individual service failures.
- Supports daemon execution.

### 9. Scheduling and Deployment
- Validates maintenance windows.
- Supports retry handling and health checks.
- Supports rollback on deployment failure.

### 10. Chatbot Integration
- Coordinates the major application services.
- Supports file attachments.
- Handles service failures.

## Technology Stack

**Programming Language**
- Python

**Libraries and Dependencies**
- PyYAML – Configuration management
- Schema – Data validation
- Scikit-learn – Machine learning functionality
- Pillow – Image processing
- Pytest – Automated testing

**Other Technologies**
- Retrieval-Augmented Generation (RAG)
- Optical Character Recognition (OCR)
- Natural Language Processing (NLP)
- JSON-based data storage
- YAML configuration

## Project Structure

```text
gen-ai-support-bot/
│
├── config/
│   └── config.yaml
│
├── data/
│   ├── conversations.json
│   └── sessions/
│
├── reports/
├── report_ss/
│
├── src/
│   ├── chatbot.py
│   ├── ingestion/
│   ├── language/
│   ├── monitoring/
│   ├── multimodal/
│   ├── pipeline/
│   ├── rag/
│   ├── security/
│   ├── sentiment/
│   └── tickets/
│
├── tests/
│
├── requirements.txt
├── README.md
└── .gitignore
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

### 2. Navigate to the project directory

```bash
cd gen-ai-support-bot
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Check configuration

Review the configuration file:

```text
config/config.yaml
```

Update the settings according to your environment.

## Running the Chatbot

Run a sample chatbot interaction using:

```bash
python -c "from src.chatbot import CustomerServiceBot; bot=CustomerServiceBot(); print(bot.process_message('demo-001','How long does shipping take?'))"
```

This initializes the customer service bot and processes a sample customer query.

## Running Tests

Run all automated tests:

```bash
python -m pytest -q
```

Run tests with detailed output:

```bash
python -m pytest -v
```

Check Python compilation:

```bash
python -m compileall -q src tests
```

## Test Results

| Test Metric | Result |
|---|---|
| Total Tests | 96 |
| Passed | 96 |
| Failed | 0 |
| Success Rate | 100% |

All 96 automated tests passed successfully.

## Future Scope

- Integration with live customer support platforms.
- Improved multilingual translation capabilities.
- Advanced conversational analytics.
- Integration with external ticketing systems.
- Enhanced knowledge-base automation.
- Deployment through a cloud-based environment.

## Conclusion

The Gen AI Customer Service Bot demonstrates the integration of AI-driven customer support capabilities, including document intelligence, knowledge retrieval, sentiment analysis, multilingual processing, and automated ticket management.

The project aims to improve support efficiency, enhance customer experience, and reduce repetitive manual support operations.

---

**Project:** Gen AI Customer Service Bot
**Category:** Artificial Intelligence / Generative AI
**Purpose:** Internship Extension Project

## Limitations
- Sentiment analysis and language detection are rule-based (lexicons and regex), not trained ML models.
- Image OCR needs the Tesseract program installed; without it the bot reports that it cannot read the file, and tests use a fake OCR engine.
- Translation needs a translation engine to be plugged in (tests use a mock engine).
- Customer sessions are kept in memory, so they do not survive a restart.
