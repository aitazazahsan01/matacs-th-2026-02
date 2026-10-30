"""AI extraction step: one Gemini call per proposal, then code checks the answer.

Put each proposal's extracted text in prototype/samples/<LETTER>.txt (this folder is
git-ignored because the brief asks us not to commit proposal text), copy
.env.example to .env and add your GEMINI_API_KEY, then:

    python extract.py
    python score.py --extraction output/extraction.json

    python extract.py --list-models     # show models your key can use
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import errors, types

from prompts import SYSTEM_PROMPT, build_output_schema, build_user_message

HERE = Path(__file__).parent


def load_dotenv(path=HERE / ".env"):
    """Minimal .env reader so the key never has to be typed into code."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


load_dotenv()
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
SEED = 7

# Cheap rule-based pre-scan that runs before (and independently of) the AI,
# so a manipulation attempt is caught even if the model misses it.
INJECTION_PATTERNS = [
    r"\b(ignore|disregard)\b.{0,40}\b(instruction|criteria|previous)",
    r"\b(automated|ai|automatic)\s+(review|reviewer|system|scoring)",
    r"\brank (it|this|us) (first|1st|highest)",
    r"\bfull marks\b",
    r"\bpre-?approved\b",
]


def prescan(text):
    return [m.group(0) for p in INJECTION_PATTERNS for m in re.finditer(p, text, re.IGNORECASE)]


def normalise(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def verify_evidence(answer, source_text):
    """Null out any value whose quote is not really in the document."""
    src = normalise(source_text)
    problems = []
    for crit_id, fields in answer["criteria"].items():
        for name, item in fields.items():
            ev = item.get("evidence")
            if ev and normalise(ev) not in src:
                problems.append(f"{crit_id}.{name}: quote not found in document; value {item['value']!r} discarded")
                item["value"], item["evidence"] = None, None
    return problems


def call_model(client, criteria, schema, path, text, retries=4):
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        # Gemini 3+ is tuned for its default temperature (lower can cause looping);
        # older models get 0. The seed is fixed either way.
        temperature=0 if MODEL.startswith("gemini-2") else None,
        seed=SEED,
        response_mime_type="application/json",
        response_json_schema=schema,
    )
    for attempt in range(retries + 1):
        try:
            return client.models.generate_content(
                model=MODEL, contents=build_user_message(criteria, path.name, text), config=config)
        except errors.ClientError as e:
            # Free tier allows only a few requests per minute; wait and retry on 429.
            if e.code != 429 or attempt == retries:
                raise
            wait = 20 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s ...", flush=True)
            time.sleep(wait)
        except errors.ServerError:
            if attempt == retries:
                raise
            time.sleep(5)


def extract_one(client, criteria, schema, path):
    text = path.read_text(encoding="utf-8")
    response = call_model(client, criteria, schema, path, text)
    finish = response.candidates[0].finish_reason if response.candidates else None
    if not response.text or (finish and finish.name != "STOP"):
        raise RuntimeError(f"{path.name}: model stopped with {finish}; send to manual review")
    answer = json.loads(response.text)
    problems = verify_evidence(answer, text)

    usage = response.usage_metadata
    return {
        "proposal": path.stem.upper(),
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "values": {c: {f: v["value"] for f, v in fs.items()} for c, fs in answer["criteria"].items()},
        "evidence": {c: {f: v["evidence"] for f, v in fs.items()} for c, fs in answer["criteria"].items()},
        "embedded_instructions": answer["embedded_instructions"],
        "prescan_hits": prescan(text),
        "uncertainties": answer["uncertainties"] + problems,
        "model": response.model_version or MODEL,
        "response_id": response.response_id,
        "usage": {"input_tokens": usage.prompt_token_count, "output_tokens": usage.candidates_token_count}
        if usage else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-models", action="store_true", help="list models available to your key and exit")
    args = ap.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    if args.list_models:
        for m in client.models.list():
            if "generateContent" in (m.supported_actions or []):
                print(m.name)
        return

    criteria = json.loads((HERE / "criteria_v1.json").read_text(encoding="utf-8"))
    files = sorted((HERE / "samples").glob("*.txt"))
    if not files:
        sys.exit("No proposals found in prototype/samples/*.txt")

    schema = build_output_schema(criteria)
    records = []
    for path in files:
        print(f"Extracting {path.name} with {MODEL} ...", flush=True)
        try:
            records.append(extract_one(client, criteria, schema, path))
        except errors.ClientError as e:
            hint = " Run 'python extract.py --list-models' and set GEMINI_MODEL in .env." if e.code == 404 else ""
            sys.exit(f"Gemini rejected the request ({e.code}): {e.message}.{hint}")

    out = HERE / "output" / "extraction.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "criteria_version": criteria["criteria_version"],
        "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        "model": MODEL,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "proposals": records,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
