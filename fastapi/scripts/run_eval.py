"""평가셋(eval/eval_set.json)으로 RAG를 실제 모델에 돌려 정확도와 지연을 잰다.

사용 (프로젝트 루트 .env의 키 · 인덱스를 그대로 사용):
    python scripts/run_eval.py [--retries 1] [--concurrency 4] [--lines 2] [--known-codes] [--out result.json]

--lines N        답변을 앞에서 N줄까지 보여 준다 (기본 2)
--known-codes    질문에 error_code_known이 있으면 그 값을 error_code로 쓴다 (백엔드가 실제 알람 코드를 아는 경우)
--deadline N     질문 하나의 전체 대기 시간 상한(초). 기본 120 (실제 서비스 기본값 20을 시험하려면 20)

채점 항목 (각 항목은 기대값이 있을 때만 확인):
    status      found / not_found가 기대와 같은가
    exact       exact_match가 기대와 같은가
    review      needs_review가 기대와 같은가
    keywords    답변에 필수 단어가 모두 있는가 ("a|b"는 둘 중 하나)
    source      근거 섹션에 기대 문자열이 있는가
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.services.llm import get_llm_client  # noqa: E402
from app.services.rag import run_rag  # noqa: E402
from app.services.retrieval import load_index  # noqa: E402


def keywords_present(answer: str | None, groups: list[str]) -> bool:
    text = answer or ""
    return all(any(alt.strip().lower() in text.lower() for alt in group.split("|")) for group in groups)


def missing_groups(answer: str | None, groups: list[str]) -> list[str]:
    """답변에 없는 필수 요소 ("a|b"는 둘 중 하나라도 있으면 있는 것)."""
    text = (answer or "").lower()
    return [group for group in groups if not any(alt.strip().lower() in text for alt in group.split("|"))]


def score_case(expect: dict, outcome: dict) -> dict[str, bool]:
    """기대값이 있는 항목만 True/False로 채점한 결과."""
    checks: dict[str, bool] = {}
    if "status" in expect:
        checks["status"] = outcome["status"] == expect["status"]
    if "exact_match" in expect:
        checks["exact"] = outcome["exact_match"] is expect["exact_match"]
    if "needs_review" in expect:
        checks["review"] = outcome["needs_review"] is expect["needs_review"]
    if "must_contain" in expect:
        checks["keywords"] = keywords_present(outcome["answer"], expect["must_contain"])
    if "section" in expect:
        checks["source"] = any(expect["section"] in (s or "") for s in outcome["sections"])
    return checks


def first_lines(text: str | None, count: int = 2) -> str:
    if not text:
        return "-"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n         ".join(lines[:count])


def error_outcome(exc: Exception) -> dict:
    """API 오류 등으로 한 건이 실패해도 전체 평가는 계속 진행하고, 그 건은 실패로 기록한다."""
    code = getattr(exc, "code", None) or type(exc).__name__
    return {"status": "error", "answer": None, "exact_match": None, "needs_review": False,
            "attempts": 0, "score": None, "reason": str(code), "sections": [], "seconds": 0.0}


async def run_case(case, client, settings, index, semaphore, known_codes=False):
    error_code = case.get("error_code_known") if known_codes and case.get("error_code_known") else case["error_code"]
    case = {**case, "error_code": error_code}
    async with semaphore:
        started = time.perf_counter()
        try:
            out = await run_rag(
                client,
                settings,
                index,
                equipment_name=case["equipment_name"],
                error_code=error_code,
                symptom=case.get("symptom"),
            )
        except Exception as exc:  # noqa: BLE001 - 한 건의 실패가 전체를 멈추지 않게 한다
            return case, error_outcome(exc)
        took = time.perf_counter() - started
    outcome = {
        "status": out.status,
        "answer": out.answer,
        "exact_match": out.exact_match,
        "needs_review": out.needs_review,
        "attempts": out.attempts,
        "score": out.score,
        "reason": out.reason,
        "sections": [c.metadata.get("section") for c in out.chunks],
        "seconds": round(took, 1),
    }
    return case, outcome


async def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 평가셋 실행")
    parser.add_argument("--set", default=str(ROOT / "eval" / "eval_set.json"))
    parser.add_argument("--retries", type=int, default=None, help="재시도 횟수 (기본: 설정값)")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--deadline", type=float, default=120, help="질문 하나의 전체 대기 시간 상한(초)")
    parser.add_argument("--lines", type=int, default=2, help="답변을 앞에서 몇 줄까지 보여 줄지")
    parser.add_argument("--known-codes", action="store_true", help="error_code_known이 있으면 그 값을 사용")
    parser.add_argument("--out", default=None, help="결과를 JSON으로 저장할 경로")
    args = parser.parse_args()

    settings = get_settings().model_copy(update={"rag_deadline_seconds": args.deadline})
    if args.retries is not None:
        settings = settings.model_copy(update={"rag_max_retries": args.retries})
    client, index = get_llm_client(settings), load_index(settings.faiss_path)
    cases = json.loads(Path(args.set).read_text(encoding="utf-8"))

    print(f"평가셋 {len(cases)}건 | 인덱스 {len(index)}청크 | 최대 {1 + settings.rag_max_retries}번 시도 | 동시 {args.concurrency}건\n")
    semaphore = asyncio.Semaphore(args.concurrency)
    results = await asyncio.gather(*[run_case(c, client, settings, index, semaphore, args.known_codes) for c in cases])

    scored, passed, rows = 0, 0, []
    for case, outcome in results:
        expect = case.get("expect", {})
        checks = score_case(expect, outcome) if case.get("scored", True) and expect else {}
        ok = all(checks.values()) if checks else None
        if ok is not None:
            scored += 1
            passed += ok
        mark = "—" if ok is None else ("PASS" if ok else "FAIL")
        failed = [name for name, value in checks.items() if not value]
        print(f"[{case['id']}] {mark:4} {case['category']} | {case['equipment_name']} / {case['error_code'] or '(코드 없음)'} / {case.get('symptom') or '(없음)'}")
        print(f"       {outcome['status']} 시도={outcome['attempts']} 점수={outcome['score']} exact={outcome['exact_match']} "
              f"review={outcome['needs_review']} reason={outcome['reason']} {outcome['seconds']}초"
              + (f" | 실패 항목: {', '.join(failed)}" if failed else ""))
        if case.get("expected_summary"):
            print(f"       기대: {case['expected_summary']}")
        print(f"       답변: {first_lines(outcome['answer'], args.lines)}")
        absent = missing_groups(outcome["answer"], expect.get("must_contain", [])) if expect.get("must_contain") else []
        if absent:
            print(f"       빠진 요소: {', '.join(absent)}")
        print()
        rows.append({"case": case, "outcome": outcome, "checks": checks, "pass": ok})

    seconds = [o["seconds"] for _, o in results]
    found_seconds = [o["seconds"] for _, o in results if o["status"] == "found"]
    miss_seconds = [o["seconds"] for _, o in results if o["status"] != "found"]
    by_check: dict[str, list[bool]] = {}
    for row in rows:
        for name, value in row["checks"].items():
            by_check.setdefault(name, []).append(value)

    print("=" * 70)
    print(f"통과 {passed}/{scored} ({passed / scored:.0%})" if scored else "채점 대상 없음")
    for name, values in by_check.items():
        print(f"  {name:9} {sum(values)}/{len(values)}")
    ordered = sorted(seconds)
    print(f"지연: 평균 {statistics.mean(seconds):.1f}초 | 중앙값 {statistics.median(seconds):.1f}초 | "
          f"95% {ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]:.1f}초 | 최대 {max(seconds):.1f}초")
    if found_seconds:
        print(f"  찾은 경우 평균 {statistics.mean(found_seconds):.1f}초 ({len(found_seconds)}건)")
    if miss_seconds:
        print(f"  못 찾은 경우 평균 {statistics.mean(miss_seconds):.1f}초 ({len(miss_seconds)}건)")

    if args.out:
        Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n결과 저장: {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
