"""
Fixed eval set (F11) — covers all four specialist agent types against the seeded
company data (data/company.db, data/sample_company_notes.txt) plus two general-knowledge
questions that need the web agent. Reference answers are used both by the LLM-judge and
(where present) ragas' reference-based metrics.
"""

QUESTIONS = [
    {
        "question": "Why did customer churn rise in Q3?",
        "reference": (
            "Churn rose because Starter-tier support response time averaged 36 hours, "
            "well above the 12-hour SLA target, and exit interviews cited slow support "
            "and missing export features as the top two reasons."
        ),
    },
    {
        "question": "What drove the Enterprise tier's revenue growth in Q3?",
        "reference": (
            "Three renewals with expanded seat counts drove 18% quarter-over-quarter "
            "revenue growth, with zero enterprise churn."
        ),
    },
    {
        "question": "Did the new CSV export feature reduce churn in Q3?",
        "reference": (
            "No — it shipped in late September, after most of the Q3 churn had already "
            "happened, so its effect on retention won't be visible until Q4."
        ),
    },
    {
        "question": "How many people are on the support team after the Q3 hiring?",
        "reference": "6, up from 4, hired specifically to close the response-time gap.",
    },
    {
        "question": "How many starter-tier customers churned in Q3?",
        "reference": "4",
    },
    {
        "question": "How many starter-tier customers churned in Q2?",
        "reference": "3",
    },
    {
        "question": "What percent of starter-tier customers churned in Q3?",
        "reference": "Approximately 4%",
    },
    {
        "question": "What is the average of 34, 55, 21, and 90?",
        "reference": "50",
    },
    {
        "question": "What is 128 divided by 8?",
        "reference": "16",
    },
    {
        "question": "What is LangGraph used for?",
        "reference": (
            "LangGraph is a framework for building stateful, multi-agent LLM "
            "applications/orchestration graphs."
        ),
    },
    {
        "question": "What is Qdrant?",
        "reference": (
            "Qdrant is an open-source vector database/search engine used for "
            "similarity search over embeddings."
        ),
    },
]
