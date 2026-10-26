"""평가셋(eval/q30, eval/q10)으로 RAG를 실제 모델에 돌려 정확도와 지연을 잰다.

사용 (프로젝트 루트 .env의 키 · 인덱스를 그대로 사용):
    python scripts/run_eval.py [--retries 1] [--concurrency 4] [--lines 2] [--known-codes] [--out result.json]

--lines N        답변을 앞에서 N줄까지 보여 준다 (기본 2)
--known-codes    질문에 error_code_known이 있으면 그 값을 error_code로 쓴다 (백엔드가 실제 알람 코드를 아는 경우)
--deadline N     질문 하나의 전체 대기 시간 상한(초). 기본 120 (실제 서비스 기본값 20을 시험하려면 20)
--set FILE       입력 파일 (기본 eval/q30/inputs.json). 장비명 · 증상 · 코드만 담는다.
--answers FILE   정답지 파일. 기대 답변과 채점 기준을 따로 둔다. 같은 id끼리 합친다.
                 생략하면 --set 옆의 answers.json을 찾아 쓴다 (eval/q30/, eval/q10/).
                 예) eval/q10/inputs.json: 잘못 나와야 하는 질문(없는 장비 · 없는 주제 · 코드가 틀린 질문) 10개
--methods A,B    합격을 정하는 내용 평가: keywords(필수 단어) | embedding(기대 답변과 임베딩 유사도) | judge(LLM 채점)
                 기본은 .env의 EVAL_METHODS. 여러 개를 켜면 방법마다 따로 집계되어 나란히 비교된다.
--info-methods A 계산해서 보여 주기만 하고 합격에는 쓰지 않는 방법 (기본은 .env의 EVAL_INFO_METHODS).
                 여기서 떨어지면 합격 여부와 별개로 "확인 필요"로 표시한다. 예: 키워드로 합격을 정하고 judge는 경고로만.

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
from app.services.evaluation import (  # noqa: E402
    embedding_similarity,
    judge_answer,
    judge_passes,
    overall_pass,
    parse_methods,
)
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
    if "risk_level" in expect:
        checks["risk"] = outcome.get("risk_level") == expect["risk_level"]
    return checks


def merge_cases(inputs: list[dict], answers: list[dict]) -> list[dict]:
    """입력 파일과 정답지 파일을 id로 합친다. 정답이 없는 입력은 채점하지 않는 질문이 된다."""
    by_id: dict[str, dict] = {}
    for answer in answers:
        if answer["id"] in by_id:
            raise ValueError(f"정답지에 같은 id가 두 번 있습니다: {answer['id']}")
        by_id[answer["id"]] = answer
    input_ids = [case["id"] for case in inputs]
    if len(set(input_ids)) != len(input_ids):
        raise ValueError("입력 파일에 같은 id가 두 번 있습니다.")
    orphans = sorted(set(by_id) - set(input_ids))
    if orphans:
        raise ValueError(f"입력에 없는 id의 정답이 있습니다: {', '.join(orphans)}")
    return [{**case, **{k: v for k, v in by_id.get(case["id"], {}).items() if k != "id"}} for case in inputs]


def first_lines(text: str | None, count: int = 2) -> str:
    if not text:
        return "-"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n         ".join(lines[:count])


def error_outcome(exc: Exception) -> dict:
    """API 오류 등으로 한 건이 실패해도 전체 평가는 계속 진행하고, 그 건은 실패로 기록한다."""
    code = getattr(exc, "code", None) or type(exc).__name__
    return {"status": "error", "answer": None, "exact_match": None, "needs_review": False,
            "attempts": 0, "score": None, "reason": str(code), "sections": [], "evidence": [], "seconds": 0.0,
            "risk_level": None, "risk_reason": None}


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
        "evidence": [c.text for c in out.chunks],
        "risk_level": out.risk_level,
        "risk_reason": out.risk_reason,
        "seconds": round(took, 1),
    }
    return case, outcome


async def extra_checks(case, outcome, client, settings, methods, semaphore) -> dict:
    """키워드 말고 의미 기반 평가(임베딩 유사도 · LLM Judge). 답변이 없으면 하지 않는다."""
    extra: dict = {}
    answer = outcome["answer"]
    if not answer or outcome["status"] != "found" or not case.get("scored", True):
        return extra
    reference = case.get("expected_summary")
    timeout = settings.rag_llm_timeout_seconds
    async with semaphore:
        if "embedding" in methods and reference:
            try:
                score = await embedding_similarity(client, settings.embedding_model, answer, reference, timeout=timeout)
                extra["embedding"] = {"score": round(score, 4), "pass": score >= settings.eval_embed_threshold}
            except Exception as exc:  # noqa: BLE001
                extra["embedding"] = {"error": f"{type(exc).__name__}", "pass": False}
        if "judge" in methods:
            try:
                scores = await judge_answer(client, settings.eval_judge_model, case["symptom"] or case["equipment_name"],
                                            reference, outcome.get("evidence", []), answer, timeout=timeout)
                extra["judge"] = {"scores": scores, "pass": judge_passes(scores, settings.eval_judge_threshold)}
            except Exception as exc:  # noqa: BLE001
                extra["judge"] = {"error": getattr(exc, "code", None) or type(exc).__name__, "pass": False}
    return extra


async def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 평가셋 실행")
    parser.add_argument("--set", default=str(ROOT / "eval" / "q30" / "inputs.json"))
    parser.add_argument("--answers", default=None, help="정답지 파일 (입력과 정답을 나눠 둔 평가셋)")
    parser.add_argument("--retries", type=int, default=None, help="재시도 횟수 (기본: 설정값)")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--deadline", type=float, default=120, help="질문 하나의 전체 대기 시간 상한(초)")
    parser.add_argument("--lines", type=int, default=2, help="답변을 앞에서 몇 줄까지 보여 줄지")
    parser.add_argument("--known-codes", action="store_true", help="error_code_known이 있으면 그 값을 사용")
    parser.add_argument("--methods", default=None, help="합격을 정하는 내용 평가 방법 (기본: .env의 EVAL_METHODS)")
    parser.add_argument("--info-methods", default=None, help="보여 주기만 하는(합격에는 안 쓰는) 방법 (기본: .env의 EVAL_INFO_METHODS)")
    parser.add_argument("--out", default=None, help="결과를 JSON으로 저장할 경로")
    args = parser.parse_args()

    settings = get_settings().model_copy(update={"rag_deadline_seconds": args.deadline})
    if args.retries is not None:
        settings = settings.model_copy(update={"rag_max_retries": args.retries})
    methods = parse_methods(args.methods or settings.eval_methods)
    info_methods = [m for m in parse_methods(args.info_methods if args.info_methods is not None else settings.eval_info_methods,
                                              allow_empty=True) if m not in methods]
    computed = list(dict.fromkeys(methods + info_methods))
    client, index = get_llm_client(settings), load_index(settings.faiss_path)
    cases = json.loads(Path(args.set).read_text(encoding="utf-8"))
    answers_path = Path(args.answers) if args.answers else Path(args.set).with_name("answers.json")
    if args.answers or (Path(args.set).name == "inputs.json" and answers_path.exists()):
        cases = merge_cases(cases, json.loads(answers_path.read_text(encoding="utf-8")))

    print(f"평가셋 {len(cases)}건 | 인덱스 {len(index)}청크({settings.chunking}) | 최대 {1 + settings.rag_max_retries}번 시도 | 동시 {args.concurrency}건")
    print(f"내용 평가(합격 기준): {', '.join(methods)}" + (f" | 참고용(확인 필요 표시): {', '.join(info_methods)}" if info_methods else "")
          + (f" | 합격 규칙: {settings.eval_pass_rule}, Judge 모델: {settings.eval_judge_model}" if "judge" in computed else "") + "\n")
    semaphore = asyncio.Semaphore(args.concurrency)
    results = await asyncio.gather(*[run_case(c, client, settings, index, semaphore, args.known_codes) for c in cases])
    extras = await asyncio.gather(*[extra_checks(c, o, client, settings, computed, semaphore) for c, o in results])

    scored, passed, rows = 0, 0, []
    for (case, outcome), extra in zip(results, extras):
        expect = case.get("expect", {})
        checks = score_case(expect, outcome) if case.get("scored", True) and expect else {}
        keyword_result = checks.pop("keywords", None)
        if "keywords" not in computed:
            keyword_result = None
        content = {"keywords": keyword_result} if keyword_result is not None and "keywords" in methods else {}
        content.update({name: value["pass"] for name, value in extra.items() if name in methods and "pass" in value})
        # 합격에는 쓰지 않고 보여 주기만 하는 방법: 하나라도 떨어지면 "확인 필요"
        info = {"keywords": keyword_result} if keyword_result is not None and "keywords" in info_methods else {}
        info.update({name: value["pass"] for name, value in extra.items() if name in info_methods and "pass" in value})
        needs_check = [name for name, value in info.items() if not value]
        ok = overall_pass(checks, content, settings.eval_pass_rule) if (checks or content) and case.get("scored", True) else None
        if ok is not None:
            scored += 1
            passed += ok
        mark = "—" if ok is None else ("PASS" if ok else "FAIL")
        failed = [name for name, value in {**checks, **content}.items() if not value]
        print(f"[{case['id']}] {mark:4} {case['category']} | {case['equipment_name']} / {case['error_code'] or '(코드 없음)'} / {case.get('symptom') or '(없음)'}")
        print(f"       {outcome['status']} 시도={outcome['attempts']} 점수={outcome['score']} exact={outcome['exact_match']} "
              f"review={outcome['needs_review']} reason={outcome['reason']} {outcome['seconds']}초"
              + (f" | 위험도={outcome.get('risk_level')}" if outcome.get("risk_level") else "")
              + (f" | 실패 항목: {', '.join(failed)}" if failed else "")
              + (f" | ⚠ 확인 필요: {', '.join(needs_check)}" if needs_check else ""))
        if case.get("expected_summary"):
            print(f"       기대: {case['expected_summary']}")
        print(f"       답변: {first_lines(outcome['answer'], args.lines)}")
        absent = missing_groups(outcome["answer"], expect.get("must_contain", [])) if expect.get("must_contain") and "keywords" in computed else []
        if absent:
            print(f"       빠진 요소: {', '.join(absent)}")
        if "embedding" in extra:
            e = extra["embedding"]
            print(f"       임베딩 유사도: {e['score']:.2f} (기준 {settings.eval_embed_threshold}) {'통과' if e['pass'] else '미달'}" if "score" in e else f"       임베딩 유사도: {e.get('error')}")
        if "judge" in extra:
            j = extra["judge"]
            if "scores" in j:
                s_ = j["scores"]
                print(f"       Judge: 관련 {s_['relevance']} · 충실 {s_['faithfulness']} · 정확 {s_['correctness'] if s_['correctness'] is not None else '-'}"
                      f" {'통과' if j['pass'] else '미달'} — {s_['reason']}")
            else:
                print(f"       Judge: {j.get('error')}")
        print()
        rows.append({"case": case, "outcome": outcome, "checks": {**checks, **{k: v for k, v in {"keywords": keyword_result}.items() if v is not None}},
                     "extra": extra, "info": info, "needs_check": needs_check, "pass": ok})

    seconds = [o["seconds"] for _, o in results]
    found_seconds = [o["seconds"] for _, o in results if o["status"] == "found"]
    miss_seconds = [o["seconds"] for _, o in results if o["status"] != "found"]
    by_check: dict[str, list[bool]] = {}
    for row in rows:
        for name, value in row["checks"].items():
            by_check.setdefault(name, []).append(value)
        for name, value in row["extra"].items():
            if "pass" in value:
                by_check.setdefault(name, []).append(value["pass"])

    print("=" * 70)
    print(f"통과 {passed}/{scored} ({passed / scored:.0%})" if scored else "채점 대상 없음")
    if info_methods:
        flagged = [r for r in rows if r["needs_check"]]
        print(f"  ⚠ 확인 필요 {len(flagged)}건 ({', '.join(info_methods)} 기준, 합격에는 영향 없음): {[r['case']['id'] for r in flagged]}")
    for name, values in by_check.items():
        print(f"  {name:9} {sum(values)}/{len(values)}")
    sims = [r["extra"]["embedding"]["score"] for r in rows if "score" in r["extra"].get("embedding", {})]
    if sims:
        print(f"  임베딩 유사도 평균 {statistics.mean(sims):.2f} (최소 {min(sims):.2f})")
    judged = [r["extra"]["judge"]["scores"] for r in rows if "scores" in r["extra"].get("judge", {})]
    if judged:
        print(f"  Judge 평균: 관련 {statistics.mean(j['relevance'] for j in judged):.1f} · "
              f"충실 {statistics.mean(j['faithfulness'] for j in judged):.1f}")
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
