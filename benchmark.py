# FILE: benchmark.py
# VERSION: 1.0.0
# START_MODULE_CONTRACT
#   PURPOSE: Benchmark all free OpenRouter models for speed and extraction quality
#   SCOPE: Send test batch to each model, measure response time and contact count, recommend best model
#   DEPENDS: src.config (FREE_MODELS, load_config), src.extractor (OPENROUTER_URL, load_prompt, DEFAULT_PROMPT_NAME, _parse_llm_response)
#   LINKS: M-BENCHMARK
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   BenchmarkResult — dataclass holding per-model benchmark metrics
#   bench_one_model — send test batch to one model and measure performance
#   run_benchmark — iterate all FREE_MODELS and collect results
#   print_summary — render results table and recommend best model
#   main — CLI entry point
# END_MODULE_MAP

"""
Benchmark: test speed and quality of all free OpenRouter models.

Usage:
    python benchmark.py --api-key sk-or-...
    python benchmark.py                      (uses saved config)

Sends the same test batch to each model and reports:
  - Response time
  - Contacts extracted count
  - Whether JSON was valid
"""

from __future__ import annotations

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import argparse
import asyncio
import json
import time
from dataclasses import dataclass

import httpx

from src.config import FREE_MODELS, load_config
from src.extractor import OPENROUTER_URL, load_prompt, DEFAULT_PROMPT_NAME, _parse_llm_response

# A realistic test batch with known contacts embedded
TEST_MESSAGES = """
[ID:101] Анна (2026-03-15 10:15:00): Привет всем! Вот контакты курьера: Иванов Пётр Сергеевич, +7 999 123-45-67, telegram @ivanov_petr

[ID:102] Олег (2026-03-15 10:20:00): Скидываю реквизиты поставщика: ООО "Ромашка", ИНН 7712345678, email info@romashka.ru, сайт romashka.ru

[ID:103] Катя (2026-03-15 10:25:00): Адрес склада для самовывоза: Москва, ул. Ленина 15, стр. 2. Режим работы: пн-пт 9:00-18:00

[ID:104] Дима (2026-03-15 10:30:00): Ребят, у кого есть контакт электрика? Нужен срочно

[ID:105] Марина (2026-03-15 10:35:00): @dima вот: Сидоров Алексей, WhatsApp +7 916 555-00-11, работает по всей Москве

[ID:106] Анна (2026-03-15 10:40:00): Спасибо! А ещё нашла бухгалтера — Елена Викторовна Козлова, email kozlova.ev@mail.ru, телефон 8-495-777-88-99
""".strip()

# Expected: at least 4 contacts (Иванов, Ромашка, Сидоров, Козлова + possibly address)
EXPECTED_MIN_CONTACTS = 3


@dataclass
class BenchmarkResult:
    model_id: str
    model_name: str
    response_time_s: float
    contacts_found: int
    valid_json: bool
    error: str | None = None
    contact_types: list[str] | None = None


# START_CONTRACT: bench_one_model
#   PURPOSE: Send test batch to one model and measure response time, contact count, JSON validity
#   INPUTS: { client: httpx.AsyncClient, api_key: str, model_id: str, model_name: str }
#   OUTPUTS: { BenchmarkResult — metrics for this model }
# END_CONTRACT
async def bench_one_model(
    client: httpx.AsyncClient,
    api_key: str,
    model_id: str,
    model_name: str,
) -> BenchmarkResult:
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": load_prompt(DEFAULT_PROMPT_NAME)},
            {"role": "user", "content": TEST_MESSAGES},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    start = time.perf_counter()
    try:
        resp = await client.post(
            OPENROUTER_URL,
            json=payload,
            headers=headers,
            timeout=60.0,
        )
        elapsed = time.perf_counter() - start

        resp.raise_for_status()
        body = resp.json()
        content = body["choices"][0]["message"]["content"]

        records = _parse_llm_response(content)
        all_types = []
        for r in records:
            for f in r.extracted:
                if f.type not in all_types:
                    all_types.append(f.type)

        return BenchmarkResult(
            model_id=model_id,
            model_name=model_name,
            response_time_s=elapsed,
            contacts_found=len(records),
            valid_json=True,
            contact_types=all_types,
        )

    except json.JSONDecodeError:
        elapsed = time.perf_counter() - start
        return BenchmarkResult(
            model_id=model_id,
            model_name=model_name,
            response_time_s=elapsed,
            contacts_found=0,
            valid_json=False,
            error="Invalid JSON response",
        )

    except Exception as exc:
        elapsed = time.perf_counter() - start
        return BenchmarkResult(
            model_id=model_id,
            model_name=model_name,
            response_time_s=elapsed,
            contacts_found=0,
            valid_json=False,
            error=str(exc)[:80],
        )


# START_CONTRACT: run_benchmark
#   PURPOSE: Iterate all FREE_MODELS, benchmark each, and collect results
#   INPUTS: { api_key: str — OpenRouter API key }
#   OUTPUTS: { list[BenchmarkResult] — one entry per model }
# END_CONTRACT
async def run_benchmark(api_key: str) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []

    async with httpx.AsyncClient() as client:
        for model in FREE_MODELS:
            model_id = model["id"]
            model_name = model["name"]

            print(f"\n  Testing: {model_name} ({model_id})")
            print(f"  {'-' * 50}")

            result = await bench_one_model(client, api_key, model_id, model_name)
            results.append(result)

            if result.error:
                print(f"  ERROR: {result.error}")
            else:
                print(f"  Time:     {result.response_time_s:.2f}s")
                print(f"  Contacts: {result.contacts_found}")
                print(f"  Types:    {', '.join(result.contact_types or [])}")

            # Small delay between models to avoid rate limiting
            await asyncio.sleep(1)

    return results


# START_CONTRACT: print_summary
#   PURPOSE: Render results table with rankings and recommend best model
#   INPUTS: { results: list[BenchmarkResult] }
#   OUTPUTS: None (prints to stdout)
# END_CONTRACT
def print_summary(results: list[BenchmarkResult]) -> None:
    print("\n")
    print("=" * 72)
    print("  BENCHMARK RESULTS")
    print("=" * 72)

    # Header
    print(f"\n  {'Model':<30} {'Time':>8} {'Contacts':>10} {'JSON':>6} {'Status':>10}")
    print(f"  {'-' * 30} {'-' * 8} {'-' * 10} {'-' * 6} {'-' * 10}")

    # Sort by time (successful first)
    ok = [r for r in results if not r.error]
    failed = [r for r in results if r.error]
    ok.sort(key=lambda r: r.response_time_s)

    for r in ok:
        quality = "OK" if r.contacts_found >= EXPECTED_MIN_CONTACTS else "LOW"
        print(
            f"  {r.model_name:<30} {r.response_time_s:>7.2f}s {r.contacts_found:>10} {'OK':>6} {quality:>10}"
        )

    for r in failed:
        print(
            f"  {r.model_name:<30} {r.response_time_s:>7.2f}s {'—':>10} {'FAIL':>6} {'ERROR':>10}"
        )

    # Winner
    if ok:
        fastest = ok[0]
        best_quality = max(ok, key=lambda r: r.contacts_found)

        print(f"\n  Fastest:      {fastest.model_name} ({fastest.response_time_s:.2f}s)")
        print(f"  Most thorough: {best_quality.model_name} ({best_quality.contacts_found} contacts)")

        # Recommend: best balance of speed + quality
        scored = [(r, r.contacts_found / max(r.response_time_s, 0.1)) for r in ok]
        scored.sort(key=lambda x: x[1], reverse=True)
        recommended = scored[0][0]
        print(f"\n  >>> Recommended: {recommended.model_name}")
        print(f"      {recommended.contacts_found} contacts in {recommended.response_time_s:.2f}s")
        print(f"      ID: {recommended.model_id}")

    print()


# START_CONTRACT: main
#   PURPOSE: CLI entry point — parse args, resolve API key, run benchmark, print summary
#   INPUTS: None (reads sys.argv)
#   OUTPUTS: None
# END_CONTRACT
def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark free OpenRouter models")
    parser.add_argument("--api-key", help="OpenRouter API key (or uses saved config)")
    args = parser.parse_args()

    api_key = args.api_key
    if not api_key:
        config = load_config()
        api_key = config.openrouter_api_key

    if not api_key:
        print("ERROR: No API key. Use --api-key or save it via the app first.")
        return

    print("=" * 72)
    print("  TG Contact Extractor — Model Benchmark")
    print(f"  Testing {len(FREE_MODELS)} free models on {TEST_MESSAGES.count('[ID:')}-message sample")
    print("=" * 72)

    results = asyncio.run(run_benchmark(api_key))
    print_summary(results)


if __name__ == "__main__":
    main()


# START_CHANGE_SUMMARY
#   LAST_CHANGE: [v1.0.0 — Replace removed SYSTEM_PROMPT import with load_prompt/DEFAULT_PROMPT_NAME;
#     add full GRACE semantic markup (module contract, module map, function contracts)]
# END_CHANGE_SUMMARY
