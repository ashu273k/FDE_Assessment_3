# Student submission checklist

Before submitting, confirm that:

- [X] `python verify_setup.py` passes in your project environment.
- [X] The product can process a request end-to-end.
- [X] Architecture A is a working single-agent baseline.
- [X] Architecture B is a lightweight staged / 2-agent variant.
- [X] At least 3 tools are used; at least 1 tool/check is deterministic.
- [X] Recommendations are returned in the `ProcurementDecision` structure.
- [X] Important evidence is visible to the user.
- [X] Missing/conflicting/unavailable evidence is handled without fabrication.
- [X] Human approval is preserved for sensitive decisions.
- [X] Prompt injection inside business data does not override system behavior.
- [X] Date-based checks use the policy's data snapshot / reference date.
- [X] The same evaluation cases were run on both architectures.
- [X] Latency and LLM/tool-call counts are reported.
- [X] The decision memo is <= 500 words and supported by evaluation evidence.
- [X] Setup instructions work from a clean environment. (Verified in `.venv` with `python3 verify_setup.py`.)
- [X] Any LLM/provider SDK you added is present in `requirements.txt`. (`google-genai` is declared for optional Gemini reviewer context.)
- [X] `.env`, API keys, and other secrets are not committed.
