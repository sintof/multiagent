"""
Evaluation harness (F11): runs the fixed question set through the full multi-agent
graph, then scores each answer two ways:
  - RAGAS (faithfulness, answer_relevancy) — automated, reference-free metrics
  - LLM-as-judge — a 1-5 score against the reference answer, via our own proxy LLM

Run from `backend/`: python -m eval.run_eval
"""

from . import _ragas_compat  # noqa: F401 — must run before importing ragas, see that file

from pydantic import BaseModel, Field
from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, faithfulness

from app.graph import run as run_graph
from app.llm import get_embeddings, get_llm_lite

from .dataset import QUESTIONS


class JudgeScore(BaseModel):
    score: int = Field(description="1-5: how well the model answer matches the reference answer's meaning. 5 = fully correct, 1 = wrong/contradicts it.")
    reason: str = Field(description="One sentence justifying the score")


def llm_judge(question: str, answer: str, reference: str) -> JudgeScore:
    return get_llm_lite(temperature=0).with_structured_output(JudgeScore).invoke(
        f"Question: {question}\n"
        f"Reference answer: {reference}\n"
        f"Model answer: {answer}\n\n"
        "Score how well the model answer matches the reference answer's meaning, "
        "1 (wrong) to 5 (fully correct). Minor wording differences don't matter, "
        "factual differences do."
    )


def main():
    samples = []
    judge_scores = []

    for item in QUESTIONS:
        result = run_graph(
            item["question"], use_memory=False, tags=["eval"], environment="development"
        )

        contexts = list(result["documents"])
        if result.get("sql_result"):
            contexts.append(result["sql_result"])
        if result.get("code_result"):
            contexts.append(result["code_result"])
        if not contexts:
            contexts = ["(no context retrieved)"]

        samples.append(
            SingleTurnSample(
                user_input=item["question"],
                response=result["answer"],
                retrieved_contexts=contexts,
                reference=item["reference"],
            )
        )

        judge = llm_judge(item["question"], result["answer"], item["reference"])
        judge_scores.append(judge.score)
        print(f"[judge {judge.score}/5] {item['question']!r}")
        print(f"    answer: {result['answer'][:150]}")
        print(f"    reason: {judge.reason}\n")

    dataset = EvaluationDataset(samples=samples)

    llm_wrapper = LangchainLLMWrapper(get_llm_lite(temperature=0))
    emb_wrapper = LangchainEmbeddingsWrapper(get_embeddings())

    ragas_result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=llm_wrapper,
        embeddings=emb_wrapper,
    )

    print("=== RAGAS metrics (averaged over all questions) ===")
    print(ragas_result)

    avg_judge = sum(judge_scores) / len(judge_scores)
    print(f"\n=== LLM-judge average: {avg_judge:.2f} / 5 over {len(judge_scores)} questions ===")


if __name__ == "__main__":
    main()
