"""1:1 통화를 흉내 내서 /translate를 순서대로 호출하고 번역 결과와 지연을 보여 준다.

사용 (서버가 켜져 있어야 함):
    python scripts/simulate_call.py [--repeat 3] [--base-url http://127.0.0.1:8001]

각 발화는 직전 발화 최대 5개를 context로 함께 보낸다 (실제 백엔드가 할 일과 같음).
"""

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

EQUIPMENT = "Brooks GF40"
ERROR_CODE = "AL40"

# (화자, 원문 언어, 번역할 언어, 발화). ADMIN(본사 상담원)은 한국어, USER(지부 담당자)는 영어로 말한다.
DIALOGUE = [
    ("ADMIN", "ko", "en", "안녕하세요, 어떤 장비에 문제가 있나요?"),
    ("USER", "en", "ko", "Hello. It's the Brooks GF40 in chamber 4. It shows AL40."),
    ("ADMIN", "ko", "en", "AL40은 유량이 범위를 초과했다는 알람입니다. 가스 유량이 출렁거리는지 확인해 주시겠어요?"),
    ("USER", "en", "ko", "Yes, the flow keeps oscillating around the setpoint."),
    ("ADMIN", "ko", "en", "인렛 압력을 2 psig씩 조정해 보시겠어요?"),
    ("USER", "en", "ko", "I raised it by 2 psig and the oscillation stopped."),
    ("ADMIN", "ko", "en", "좋습니다. 그럼 영점 보정 버튼을 5초 이상 눌러 주세요."),
    ("USER", "en", "ko", "Done. The flow is stable now. Thank you."),
]

SLOW_MS = 3000  # 이보다 느리면 "느림"으로 센다


def run_once(client: httpx.Client, base_url: str, round_no: int, verbose: bool) -> list[float]:
    history: list[dict] = []
    latencies: list[float] = []

    for turn, (speaker, src, tgt, text) in enumerate(DIALOGUE, start=1):
        body = {
            "session_id": f"sim-{round_no}",
            "utterance_id": f"u-{turn:04d}",
            "text": text,
            "source_lang": src,
            "target_lang": tgt,
            "speaker": speaker,
            "context": history[-5:] or None,
        }
        if turn >= 2:
            body["equipment_name"], body["error_code"] = EQUIPMENT, ERROR_CODE
        body = {k: v for k, v in body.items() if v is not None}

        started = time.perf_counter()
        try:
            res = client.post(f"{base_url}/translate", json=body)
        except httpx.HTTPError as exc:
            print(f"  [{turn}] {speaker:6} 연결 실패: {type(exc).__name__}")
            continue
        elapsed_ms = (time.perf_counter() - started) * 1000

        if res.status_code != 200:
            error = res.json().get("error", {}) if res.headers.get("content-type", "").startswith("application/json") else {}
            print(f"  [{turn}] {speaker:6} {res.status_code} {error.get('code', '')} {error.get('message', '')}")
            continue

        data = res.json()
        latencies.append(elapsed_ms)
        history.append({"speaker": speaker, "text": text})
        if verbose:
            print(f"  [{turn}] {speaker:6} {src}→{tgt}  {elapsed_ms:6.0f}ms (서버 {data['latency_ms']}ms, "
                  f"토큰 {data['usage']['in_tok']}/{data['usage']['out_tok']})")
            print(f"        원문: {text}")
            print(f"        번역: {data['translated_text']}")
    return latencies


def main() -> None:
    parser = argparse.ArgumentParser(description="1:1 통화 번역 시뮬레이션")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--repeat", type=int, default=1, help="전체 대화를 몇 번 반복할지 (지연 통계용)")
    args = parser.parse_args()

    all_latencies: list[float] = []
    with httpx.Client(timeout=30) as client:
        for round_no in range(1, args.repeat + 1):
            print(f"== 통화 {round_no}/{args.repeat} ==")
            all_latencies += run_once(client, args.base_url, round_no, verbose=round_no == 1)

    if not all_latencies:
        print("\n성공한 호출이 없습니다.")
        return

    ordered = sorted(all_latencies)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    slow = sum(1 for ms in all_latencies if ms >= SLOW_MS)
    total = args.repeat * len(DIALOGUE)
    print(f"\n성공 {len(all_latencies)}/{total}건 | 평균 {statistics.mean(all_latencies):.0f}ms | "
          f"중앙값 {statistics.median(all_latencies):.0f}ms | 95% {p95:.0f}ms | "
          f"최대 {max(all_latencies):.0f}ms | {SLOW_MS}ms 이상 {slow}건")


if __name__ == "__main__":
    main()
