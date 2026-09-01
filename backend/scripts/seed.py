"""Seed the knowledge base with the bundled sample policies.

Usage (from the backend directory, with the virtualenv active):
    python -m scripts.seed
    python -m scripts.seed --reset
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.dependencies import build_container  # noqa: E402
from app.schemas.chat import AskRequest  # noqa: E402
from app.schemas.common import AnswerStatus, PolicyCategory  # noqa: E402
from app.schemas.documents import DocumentMetadataForm  # noqa: E402

SAMPLES: list[dict] = [
    {
        "file": "leave-and-time-off-policy.md",
        "title": "Leave and Time Off Policy",
        "category": PolicyCategory.LEAVE_AND_TIME_OFF,
        "owner": "People Operations",
        "version_label": "v3.1",
        "effective_date": date(2025, 1, 1),
        "summary": "Annual leave, sick leave, parental leave, bereavement and public holidays.",
    },
    {
        "file": "expense-and-travel-policy.md",
        "title": "Expense and Travel Policy",
        "category": PolicyCategory.EXPENSES_AND_TRAVEL,
        "owner": "Finance",
        "version_label": "v2.4",
        "effective_date": date(2025, 3, 1),
        "summary": "Approval thresholds, travel booking, accommodation caps and meal allowances.",
    },
    {
        "file": "information-security-policy.md",
        "title": "Information Security Policy",
        "category": PolicyCategory.SECURITY_AND_IT,
        "owner": "Information Security",
        "version_label": "v4.0",
        "effective_date": date(2025, 2, 1),
        "summary": "Account and device security, data classification, AI tool use and incident reporting.",
    },
    {
        "file": "compensation-policy.md",
        "title": "Compensation Policy",
        "category": PolicyCategory.COMPENSATION,
        "owner": "People Operations",
        "version_label": "v2.2",
        "effective_date": date(2025, 1, 1),
        "summary": "Pay bands, the annual review cycle, promotions, bonus targets and payroll.",
    },
    {
        "file": "benefits-policy.md",
        "title": "Employee Benefits Policy",
        "category": PolicyCategory.BENEFITS,
        "owner": "People Operations",
        "version_label": "v3.0",
        "effective_date": date(2025, 1, 1),
        "summary": "Medical, dental and vision cover, retirement matching, wellbeing and learning budgets.",
    },
    {
        "file": "code-of-conduct-policy.md",
        "title": "Code of Conduct and Compliance Policy",
        "category": PolicyCategory.CONDUCT_AND_COMPLIANCE,
        "owner": "Legal and Compliance",
        "version_label": "v5.1",
        "effective_date": date(2025, 4, 1),
        "summary": "Expected behaviour, harassment reporting, conflicts of interest, gifts and anti-bribery.",
    },
    {
        "file": "workplace-and-remote-work-policy.md",
        "title": "Workplace and Remote Work Policy",
        "category": PolicyCategory.WORKPLACE,
        "owner": "Workplace Operations",
        "version_label": "v2.6",
        "effective_date": date(2025, 5, 1),
        "summary": "Hybrid attendance, core hours, desk booking, remote workspace rules and health and safety.",
    },
]


# Realistic traffic used to populate the Insights dashboard. The last three are
# deliberately outside the policy set so the coverage-gap report has content.
DEMO_QUESTIONS: list[str] = [
    "How many annual leave days can I carry into next year?",
    "How many annual leave days can I carry into next year?",
    "How much parental leave does a secondary caregiver get?",
    "Do I need a medical certificate for a two-day sick absence?",
    "What is the nightly accommodation limit for London?",
    "Can I paste confidential customer data into a public AI tool?",
    "How quickly must I report a lost laptop?",
    "What is the home office allowance for a new joiner?",
    "When does the annual compensation review take effect?",
    "What is the target bonus percentage at level L5?",
    "How much does the company match on retirement contributions?",
    "Is dental cover included in the medical plan?",
    "What is the fitness allowance each month?",
    "What is the limit on accepting a gift from a supplier?",
    "Do I need to declare a relationship with a colleague?",
    "How many days a week do I need to be in the office?",
    "Can I work from another country for a few weeks?",
    "Do we offer a sabbatical after five years of service?",
    "Do we offer a sabbatical after five years of service?",
    "What is our company stock ticker symbol?",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed sample policy documents.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing index and registry before seeding.",
    )
    parser.add_argument(
        "--demo-queries",
        action="store_true",
        help="Also run sample questions so the Insights dashboard has data.",
    )
    args = parser.parse_args()

    configure_logging("INFO")
    settings = get_settings()

    if args.reset:
        if settings.chroma_dir.exists():
            shutil.rmtree(settings.chroma_dir, ignore_errors=True)
        if settings.registry_path.exists():
            settings.registry_path.unlink()
        settings.ensure_directories()
        print("Reset existing index and registry.")

    container = build_container(settings)
    existing = {
        str(record.get("title")) for record in container.registry.list_documents()
    }

    samples_dir = settings.data_dir / "samples"
    ingested = 0

    for sample in SAMPLES:
        if sample["title"] in existing:
            print(f"Skipping (already indexed): {sample['title']}")
            continue

        path = samples_dir / sample["file"]
        if not path.exists():
            print(f"Missing sample file: {path}")
            continue

        payload = path.read_bytes()
        result = container.documents.ingest(
            payload=payload,
            filename=sample["file"],
            content_type="text/markdown",
            metadata=DocumentMetadataForm(
                title=sample["title"],
                category=sample["category"],
                owner=sample["owner"],
                version_label=sample["version_label"],
                effective_date=sample["effective_date"],
                summary=sample["summary"],
            ),
        )
        ingested += 1
        print(
            f"Indexed {result.document.title}: "
            f"{result.chunks_indexed} chunks in {result.duration_ms} ms"
        )

    if args.demo_queries:
        print("\nRunning demo questions...")
        answered = 0
        for question in DEMO_QUESTIONS:
            response = container.rag.ask(
                AskRequest(question=question, asked_by="demo@company.com")
            )
            answered += response.status == AnswerStatus.ANSWERED
            marker = "answered" if response.status == AnswerStatus.ANSWERED else "declined"
            print(f"  [{marker:<8}] {response.top_score:.2f}  {question}")
        print(
            f"  {answered}/{len(DEMO_QUESTIONS)} answered, "
            f"{len(DEMO_QUESTIONS) - answered} logged as coverage gaps."
        )

    print(
        f"\nDone. {ingested} document(s) added. "
        f"Total chunks in index: {container.store.count()}"
    )
    print(f"Embedding backend: {container.embedder.name} ({container.embedder.model})")
    print(f"Generation mode:   {container.generator.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
