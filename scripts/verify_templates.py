"""Opt-in live-provider check of all nine generated templates using synthetic source text.

Uses the selected provider/key in .env and incurs its API costs. Outputs stay under data/.
This checks generation and schema validation; visual and factual review are still required.
Run: uv run python scripts/verify_templates.py
"""

import asyncio
import json
import time
from pathlib import Path

from neuropace.config import load_settings
from neuropace.llm.client import LLMClient

SPANS = {
    "analogy": "A GPS satellite broadcasts its position and current time. The receiver measures signal travel time and multiplies it by the speed of light to estimate distance. Four satellites let it solve for three coordinates and receiver clock error.",
    "diagram": "Evaporation turns liquid water into vapor. Condensation turns water vapor into droplets. Precipitation returns water to the surface. These changes form the water cycle.",
    "chart": "In our class survey, apples received 12 votes, bananas received 8 votes, and oranges received 5 votes. Apples received the most votes.",
    "plot": "The relationship is y equals x squared. At x equals zero, y equals zero. At x equals one, y equals one. At x equals two, y equals four. From zero to two the curve rises faster as x increases.",
    "timeline": "First, the seed absorbs water. Next, the root emerges. Then, the shoot grows upward. Finally, the first leaves unfold.",
    "compare": "A series circuit has one path for current; a parallel circuit has multiple paths. In series, one broken component interrupts the whole circuit. In parallel, the remaining paths can still carry current.",
    "steps": "To find the mean, add all the values and divide the sum by the number of values. For 2, 4, and 6 the sum is 12 and the count is 3, so the mean is 4.",
    "example": "To find the mean, add all the values and divide the sum by the number of values. For 2, 4, and 6 the sum is 12 and the count is 3, so the mean is 4.",
    "animation": "A pendulum swings left and right around its lowest point. It slows as it rises toward either end and moves fastest at the bottom. One complete oscillation returns it to the same position and direction.",
}


async def main():
    c = LLMClient(load_settings(), None)
    sem = asyncio.Semaphore(3)
    results = {}

    async def one(kind, span):
        async with sem:
            t = time.monotonic()
            obj, source = await c.gap_artifact(kind, span, "", {"key_term": kind, "definition": span})
            results[kind] = {
                "source": source,
                "seconds": round(time.monotonic() - t, 2),
                "content": obj.model_dump() if obj else None,
            }
            print(kind, source, results[kind]["seconds"], flush=True)

    await asyncio.gather(*(one(k, s) for k, s in SPANS.items()))
    output = Path("data/verification/templates.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2))
    print("OUTPUT", output, flush=True)
    print("STATS", c.stats, flush=True)
    assert all(v["content"] and v["source"] == "llm" for v in results.values())


if __name__ == "__main__":
    asyncio.run(main())
