"""CLI entry point for the Extract Pipeline."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path


def _ensure_utf8() -> None:
    """Fix UTF-8 output on Windows."""
    if sys.platform == "win32":
        for stream in ("stdout", "stderr"):
            current = getattr(sys, stream)
            if hasattr(current, "buffer"):
                wrapped = io.TextIOWrapper(
                    current.buffer, encoding="utf-8", errors="replace"
                )
                setattr(sys, stream, wrapped)


def _build_pipeline():
    """Build and return a PipelineRunner with configured components."""
    from dotenv import load_dotenv

    load_dotenv()

    import anthropic

    from src.config import get_settings
    from src.extract.schema_registry import SchemaRegistry
    from src.pipeline.runner import PipelineRunner

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
    registry = SchemaRegistry(settings.pipeline.schemas_dir)

    return PipelineRunner(
        client=client,
        schema_registry=registry,
        classification_model=settings.classification.model,
        extraction_model=settings.extraction.model,
        confidence_threshold=settings.classification.confidence_threshold,
        max_input_length=settings.guardrails.max_input_length,
        injection_patterns=settings.guardrails.injection_patterns,
    )


def cmd_classify(args: argparse.Namespace) -> int:
    """Classify a single document."""
    from dotenv import load_dotenv

    load_dotenv()

    import anthropic

    from src.classify.classifier import Classifier
    from src.config import get_settings

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
    classifier = Classifier(
        client=client,
        model=settings.classification.model,
        doc_types=settings.classification.doc_types,
    )

    text = Path(args.file).read_text(encoding="utf-8")
    result = classifier.classify(text)

    if args.json:
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    else:
        print(f"Type:       {result.doc_type}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Reasoning:  {result.reasoning}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """Run full pipeline on a single document."""
    pipeline = _build_pipeline()
    text = Path(args.file).read_text(encoding="utf-8")
    result = pipeline.run(text, source=args.file)

    if args.json:
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    else:
        print(f"Source:      {result.source}")
        if result.classification:
            print(f"Type:        {result.classification.doc_type}")
            print(f"Confidence:  {result.classification.confidence:.2f}")
        print(f"Route:       {result.route_action}")
        if result.validation:
            print(f"Valid:       {result.validation.is_valid}")
        if result.extraction:
            print("\nExtracted fields:")
            for k, v in result.extraction.fields.items():
                print(f"  {k}: {v}")
        if result.guardrail_flags:
            print(f"\nFlags: {result.guardrail_flags}")
        print(f"\n--- {result.duration_seconds:.2f}s ---")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """Run pipeline on all documents in a directory."""
    pipeline = _build_pipeline()
    samples_dir = Path(args.directory)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for path in sorted(samples_dir.glob("*.txt")):
        print(f"Processing: {path.name} ... ", end="", flush=True)
        text = path.read_text(encoding="utf-8")
        result = pipeline.run(text, source=str(path))
        results.append(result.model_dump())

        if result.classification:
            print(
                f"{result.classification.doc_type} "
                f"({result.classification.confidence:.2f}) "
                f"→ {result.route_action}"
            )
        else:
            print(f"→ {result.route_action}")

    output_path = output_dir / "batch_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {output_path}")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Run evaluation against golden test cases."""
    from src.config import get_settings
    from src.evaluation.evaluator import Evaluator

    settings = get_settings()
    pipeline = _build_pipeline()
    evaluator = Evaluator(settings.pipeline.golden_path)

    eval_results = []
    for case in evaluator.test_cases:
        case_id = case["case_id"]
        print(f"Evaluating: {case_id} ... ", end="", flush=True)

        text = Path(case["input_file"]).read_text(encoding="utf-8")
        pipeline_result = pipeline.run(text, source=case["input_file"])

        actual = {}
        if pipeline_result.extraction:
            actual = pipeline_result.extraction.fields

        eval_result = evaluator.evaluate_single(
            case_id=case_id,
            doc_type=case["doc_type"],
            expected=case["expected"],
            actual=actual,
        )
        eval_results.append(eval_result)
        print(f"F1={eval_result.f1:.2f}")

    summary = evaluator.aggregate(eval_results)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "summary": summary,
        "details": [r.model_dump() for r in eval_results],
    }
    output_path = output_dir / "eval_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*40}")
    print(f"Total cases:    {summary['total']}")
    print(f"Avg Precision:  {summary['avg_precision']:.4f}")
    print(f"Avg Recall:     {summary['avg_recall']:.4f}")
    print(f"Avg F1:         {summary['avg_f1']:.4f}")
    if "per_type" in summary:
        for dtype, stats in summary["per_type"].items():
            print(f"  {dtype}: F1={stats['avg_f1']:.4f} (n={stats['count']})")
    print(f"\nReport saved to {output_path}")
    return 0


def cmd_schemas(args: argparse.Namespace) -> int:
    """List available extraction schemas."""
    from src.config import get_settings
    from src.extract.schema_registry import SchemaRegistry

    settings = get_settings()
    registry = SchemaRegistry(settings.pipeline.schemas_dir)

    schemas = registry.list_schemas()
    if not schemas:
        print("No schemas found.")
        return 1

    for schema in schemas:
        print(f"\n{schema['doc_type']}")
        print(f"  {schema['description']}")
        print(f"  Required: {', '.join(schema['required_fields'])}")
        if schema["optional_fields"]:
            print(f"  Optional: {', '.join(schema['optional_fields'])}")
    print()
    return 0


_COMMANDS = {
    "classify": cmd_classify,
    "extract": cmd_extract,
    "batch": cmd_batch,
    "evaluate": cmd_evaluate,
    "schemas": cmd_schemas,
}


def main() -> int:
    _ensure_utf8()

    parser = argparse.ArgumentParser(
        prog="extract-pipeline",
        description=(
            "Extract Pipeline -- structured data extraction "
            "from unstructured documents"
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # classify
    p_classify = sub.add_parser("classify", help="Classify a single document")
    p_classify.add_argument("file", help="Path to the document file")
    p_classify.add_argument("--json", action="store_true", help="Output as JSON")

    # extract
    p_extract = sub.add_parser("extract", help="Extract fields from a document")
    p_extract.add_argument("file", help="Path to the document file")
    p_extract.add_argument("--json", action="store_true", help="Output as JSON")

    # batch
    p_batch = sub.add_parser("batch", help="Batch process documents in a directory")
    p_batch.add_argument("directory", help="Directory containing .txt documents")
    p_batch.add_argument("--output", default="results", help="Output directory")

    # evaluate
    p_eval = sub.add_parser("evaluate", help="Run evaluation against golden test set")
    p_eval.add_argument("--output", default="results", help="Output directory")

    # schemas
    sub.add_parser("schemas", help="List available extraction schemas")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    return _COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
