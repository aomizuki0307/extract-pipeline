# Extract Pipeline

**Structured data extraction from unstructured documents** — classify, route, extract, validate.

Takes raw text (invoices, support tickets, emails) and produces validated structured JSON through a multi-stage pipeline.

## Architecture

```
Input Document (raw text)
        │
        ▼
┌──────────────────┐
│ Input Sanitizer  │  Prompt injection detection
└──────────────────┘
        │
        ▼
┌──────────────────┐
│   Classifier     │  → doc_type + confidence score
└──────────────────┘
        │
        ▼
┌──────────────────┐
│     Router       │  confidence threshold → extract / fallback / reject
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Schema Registry  │  YAML schema lookup by doc_type
└──────────────────┘
        │
        ▼
┌──────────────────┐
│    Extractor     │  Claude + schema prompt → raw JSON
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Output Validator │  Dynamic Pydantic model → type-checked result
└──────────────────┘
        │
        ▼
┌──────────────────┐
│  Output Guard    │  Schema conformance + hallucination detection
└──────────────────┘
        │
        ▼
PipelineResult (validated structured JSON)
```

## Design Decisions

1. **YAML Schema Registry** — New document types require only a YAML file, no code changes. Clients can self-serve.
2. **2-stage LLM calls** (classify → extract) — Each prompt is short and focused. More accurate and cheaper than a single monolithic prompt.
3. **Confidence-based routing** — Low-confidence documents are rejected or sent to fallback, not blindly extracted. Production-grade quality control.
4. **Dynamic Pydantic validation** — YAML schemas are compiled into Pydantic models at runtime for type-safe LLM output validation.
5. **Golden set evaluation** — Deterministic field-level F1 scoring against known-correct outputs. Reproducible, zero-cost, no LLM-as-judge needed.
6. **No frameworks** — Direct Claude API usage. No LangChain, no Instructor. Full control over prompts and parsing.
7. **OWASP-aware** — Input documents are untrusted user content. Prompt injection patterns are detected before LLM calls.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# List available schemas
python main.py schemas

# Classify a document
python main.py classify data/samples/invoice_01.txt

# Extract (full pipeline: classify → route → extract → validate)
python main.py extract data/samples/invoice_01.txt
python main.py extract data/samples/invoice_01.txt --json

# Batch process all samples
python main.py batch data/samples/ --output results/

# Evaluate against golden test set
python main.py evaluate

# Run tests
pytest tests/ -v

# Lint
ruff check .
```

## Adding a New Document Type

1. Create `data/schemas/your_type.yaml`:
```yaml
doc_type: your_type
description: "Description of this document type"
fields:
  field_name:
    type: string    # string | number | integer | boolean | list
    required: true
    description: "What this field contains"
```

2. Add the type to `config.yaml` under `classification.doc_types`.

3. Add sample documents and golden test cases as needed.

No code changes required.

## Evaluation

The evaluator compares extraction results against golden test cases at the field level:

- **Exact match** — Values are identical (type-flexible for numbers)
- **Fuzzy match** — String similarity ≥ 0.85 (handles minor LLM variations)
- **Precision** — Correct fields / total extracted fields
- **Recall** — Correct fields / total expected fields
- **F1** — Harmonic mean of precision and recall

```bash
python main.py evaluate
# → results/eval_report.json
```

## Tech Stack

| Role | Technology |
|------|-----------|
| LLM | Claude API (Anthropic) |
| Validation | Pydantic v2 |
| Config | PyYAML + pydantic-settings |
| CLI | argparse |
| Tests | pytest |
| Lint | ruff |
