"""PromptBench command-line interface.

Usage::

    promptbench cache stats
    promptbench cache clear [--prefix PREFIX]
    promptbench cache warm <benchmark.yaml>

The ``warm`` command runs a benchmark definition (JSON or YAML) to populate the
response cache so subsequent benchmark runs are served from cache.

Run directly with::

    python -m app.cli cache stats
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .cache import get_cache, response_cache_key
from .cache.keys import BENCHMARK_CONFIG_VERSION


def _load_benchmark_file(path: Path) -> dict:
    """Load a benchmark definition from a JSON or YAML file."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # noqa: PLC0415
        except ImportError as exc:
            raise SystemExit(
                "PyYAML is required to warm from YAML files. "
                "Install it with: pip install pyyaml\n"
                "Alternatively, provide a .json benchmark file."
            ) from exc
        return yaml.safe_load(text)
    return json.loads(text)


async def _cmd_stats(_args: argparse.Namespace) -> int:
    backend = await get_cache()
    stats = await backend.stats()
    print("PromptBench Cache Statistics")
    print("=" * 40)
    print(f"  Backend:          {stats.backend}")
    print(f"  Entries:          {stats.entries}")
    print(f"  Hits:             {stats.hits}")
    print(f"  Misses:           {stats.misses}")
    total = stats.hits + stats.misses
    print(f"  Hit rate:         {stats.hit_rate:.1%}" + ("" if total else " (no lookups yet)"))
    print(f"  Avg lookup:       {stats.avg_lookup_ms:.2f} ms")
    print(f"  Memory usage:     {stats.memory_usage}")
    return 0


async def _cmd_clear(args: argparse.Namespace) -> int:
    backend = await get_cache()
    removed = await backend.clear(args.prefix)
    if removed < 0:
        print("Cache cleared (flushed all entries).")
    else:
        scope = f"prefix={args.prefix!r}" if args.prefix else "all entries"
        print(f"Cleared {removed} cache entries ({scope}).")
    return 0


async def _cmd_warm(args: argparse.Namespace) -> int:
    from .cache import get_response_cache  # noqa: PLC0415
    from .providers import get_provider  # noqa: PLC0415

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: benchmark file not found: {path}", file=sys.stderr)
        return 1

    definition = _load_benchmark_file(path)
    prompt = definition["prompt"]
    system_prompt = definition.get("system_prompt", "")
    temperature = float(definition.get("temperature", 0.7))
    max_tokens = int(definition.get("max_tokens", 1000))
    models = definition.get("models", [])

    if not models:
        print("Error: benchmark file defines no models.", file=sys.stderr)
        return 1

    response_cache = await get_response_cache()
    warmed, skipped, failed = 0, 0, 0

    for entry in models:
        provider_id = entry["provider"]
        model = entry["model"]
        provider = get_provider(provider_id)
        if not provider or not provider.is_configured:
            print(f"  SKIP  {provider_id}/{model} — not configured")
            skipped += 1
            continue

        cache_key = response_cache_key(
            provider=provider_id,
            model=model,
            prompt_template=prompt,
            rendered_prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            benchmark_config_version=BENCHMARK_CONFIG_VERSION,
        )

        async def _compute(p=provider, m=model):
            return await p.generate(prompt, m, system_prompt, temperature, max_tokens)

        try:
            response, info = await response_cache.get_or_compute(
                cache_key, _compute, cacheable=True
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL  {provider_id}/{model} — {exc}")
            failed += 1
            continue

        if info.cache_hit:
            print(f"  HIT   {provider_id}/{model} (already cached)")
        else:
            print(f"  WARM  {provider_id}/{model} — {response.output_tokens} output tokens")
            warmed += 1

    print(f"\nCache warm complete: {warmed} warmed, {skipped} skipped, {failed} failed.")
    return 0 if failed == 0 else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptbench",
        description="PromptBench CLI — cache management and benchmark tooling.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    cache_parser = sub.add_parser("cache", help="Manage the response/embedding cache.")
    cache_sub = cache_parser.add_subparsers(dest="cache_command", required=True)

    stats_parser = cache_sub.add_parser("stats", help="Show cache statistics.")
    stats_parser.set_defaults(func=_cmd_stats)

    clear_parser = cache_sub.add_parser("clear", help="Clear cache entries.")
    clear_parser.add_argument(
        "--prefix", default="", help="Only clear keys with this prefix (default: all)."
    )
    clear_parser.set_defaults(func=_cmd_clear)

    warm_parser = cache_sub.add_parser("warm", help="Warm the cache from a benchmark file.")
    warm_parser.add_argument("file", help="Path to a benchmark definition (.yaml or .json).")
    warm_parser.set_defaults(func=_cmd_warm)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    async def _run() -> int:
        try:
            return await args.func(args)
        finally:
            from .cache import reset_cache_singleton  # noqa: PLC0415

            await reset_cache_singleton()

    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
