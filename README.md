# Gen AI Customer Service Bot

An AI-powered customer service support system developed as an internship extension project. The system combines Retrieval-Augmented Generation (RAG), multimodal document analysis, automated ticket management, sentiment analysis, escalation workflows, multilingual language processing, and an automated knowledge-base update pipeline.

## Project Status

| Module | Implementation Status |
|---|---|
| Knowledge-Base Update Pipeline | Implemented |
| Multimodal Document Analysis | Implemented |
| Automated Ticket Management | Implemented |
| RAG Knowledge Assistant | Implemented |
| Sentiment Analysis and Escalation | Implemented |
| Language Detection and Session Management | Implemented |
| Translation Support | Implemented with an injectable translation engine |
| Scheduling and Deployment | Implemented |

**Automated Testing:** 96 tests collected and passing successfully.

## Key Features

### 1. Knowledge-Base Update Pipeline
- Detects new and modified documents.
- Identifies duplicate documents.
- Supports document versioning.
- Validates updates through a quality gate.
- Supports rollback to previous versions.
- Evaluates retrieval accuracy and grounding before activating updates.

### 2. Multimodal Document Analysis
- Processes invoice images and PDF documents.
- Extracts relevant invoice information using OCR.
- Detects mismatched values and missing information.
- Validates file types, sizes, and image quality.
- Detects hidden instructions in uploaded documents.
- Protects sensitive information in logs and storage.
- Supports background processing and configurable file retention.

### 3. Automated Ticket Management
- Extracts ticket information from customer conversations.
- Detects duplicate issues.
- Assigns ticket priorities.
- Routes tickets to appropriate teams.
- Handles after-hours requests.
- Calculates SLA deadlines and warnings.
- Supports escalation and secure agent handoffs.
- Groups related issues while keeping unrelated orders separate.

### 4. RAG Knowledge Assistant
- Retrieves relevant knowledge-base documents.
- Applies role-based access control and policy-date filtering.
- Supports historical policy queries.
- Provides source citations.
- Detects unsupported claims.
- Protects against prompt injection.
- Requests clarification when historical information is ambiguous.

### 5. Sentiment Analysis and Escalation
- Supports six sentiment labels.
- Uses conversation history for contextual analysis.
- Handles sarcasm and multilingual inputs.
- Detects high-risk customer conversations.
- Escalates repeated or unresolved negative conversations.
- Adjusts response tone based on sentiment without changing policy decisions.
- Supports business-hours and after-hours routing.

### 6. Language Processing and Session Management
- Detects English, Hindi, Kannada, Tamil, Hinglish, and mixed-language inputs.
- Handles empty and invalid messages.
- Supports language switching.

## Additional Modules

### 7. Translation Support
- Injectable translation engine.
- Protected order IDs and custom terms.
- Translation output validation.

### 8. Monitoring
- Monitors sentiment and ticket services.
- Handles individual service failures.
- Supports daemon execution.

### 9. Scheduling and Deployment
- Maintenance window validation.
- Retry handling and health checks.
- Rollback on deployment failure.

### 10. Chatbot Integration
- Coordinates the major application services.
- Supports file attachments.
- Handles service failures.

## Installation

Install dependencies using:

`pip install -r requirements.txt`

## Testing

Run the test suite using:

`python -m pytest -v`

Check Python compilation using:

`python -m compileall -q src tests`

## Test Results

- Automated tests: 96 passed.
- Python compilation: Successful.
