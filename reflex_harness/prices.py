"""Pinned per-token prices, USD. Source: OpenRouter GET /api/v1/models on 2026-09-26.

Cost = tokens × pinned price. OpenRouter's usage.cost is logged alongside but not trusted:
BYOK routing bills the user's OpenAI key and reports 0.
"""
PER_TOKEN = {  # model: (input, output)
    "openai/gpt-6-luna-20260922": (0.10e-6, 0.50e-6),
    "google/gemini-3.8-flash-20260902": (0.75e-6, 3.75e-6),
}
VOYAGE_4_PER_TOKEN = 0.06e-6  # Automated Embedding query estimate (SPEC §13.2)


def cost(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = PER_TOKEN[model]  # unpinned model -> KeyError, on purpose
    return input_tokens * inp + output_tokens * out
