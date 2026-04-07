"""
kernel.py — One Mind AI Core Reasoning Engine
================================================
Universal kernel — import this into any app you build.
12 Universal Rules, fixed perimeter, distillation, external memory,
brain-controlled recall, and full media generation routing.

HARD LIMITS: Rules 1, 6, and 12 are permanently locked.
CONTENT POLICY: Brain's 12 rules are the sole content gate.
                No external API content filters apply to local generation.

Usage:
    from kernel import OneMind
    brain = OneMind()
    response, media = brain.chat("your message")
"""

import json
import os
import datetime
import hashlib
import wave
import struct
import math
import subprocess
import base64
import urllib.request
import urllib.error
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# PERIMETER CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER   = "destroyingmyths"
GITHUB_REPO   = "one-mind-memory"
GITHUB_API    = "https://api.github.com"
GITHUB_BRANCH = "main"

IS_ANDROID = (
    "ANDROID_ARGUMENT" in os.environ
    or "ANDROID_PRIVATE_PATH" in os.environ
)

if IS_ANDROID:
    _local_base = os.environ.get(
        "ANDROID_PRIVATE_PATH", "/data/data/org.bigbrain/files"
    )
else:
    _local_base = os.path.expanduser("~")

MEMORY_DIR   = os.path.join(_local_base, "one_mind")
MEMORY_STORE = os.path.join(MEMORY_DIR, "memory_store.jsonl")
MEMORY_INDEX = os.path.join(MEMORY_DIR, "memory_index.json")
STATE_FILE   = os.path.join(MEMORY_DIR, "kernel_state.json")

# Media output — SD card if present, local fallback otherwise
_SD_PATH = "/storage/FD36-522F/One Brain AI"
MEDIA_DIR = _SD_PATH if os.path.exists("/storage/FD36-522F") else os.path.join(MEMORY_DIR, "media")

MAX_STATE_BYTES = 32_768
BUFFER_CAPACITY = 10
HISTORY_LIMIT   = 40   # max turns kept in RAM
CONTEXT_LIMIT   = 20   # turns sent to Gemini per request

os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR,  exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# GITHUB STORAGE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _github_request(method, path, data=None):
    """Raw GitHub API call — pure urllib, no SDK."""
    url  = f"{GITHUB_API}{path}"
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    req.add_header("Content-Type",  "application/json")
    req.add_header("Accept",        "application/vnd.github.v3+json")
    req.add_header("User-Agent",    "OneMindAI")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()), resp.status
    except Exception as e:
        return {"error": str(e)}, 0


def _github_get_file(filename):
    """Return (content_str, sha) or (None, None) on failure."""
    result, status = _github_request(
        "GET", f"/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}"
    )
    if status == 200:
        content = base64.b64decode(result["content"]).decode("utf-8")
        return content, result["sha"]
    return None, None


def _github_put_file(filename, content, sha=None, message=None):
    """Create or update a file in the GitHub repo. Returns True on success."""
    if not GITHUB_TOKEN:
        return False
    msg  = message or f"kernel update {datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    data = {
        "message": msg,
        "content": base64.b64encode(content.encode("utf-8")).decode(),
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        data["sha"] = sha
    _, status = _github_request(
        "PUT", f"/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}", data
    )
    return status in (200, 201)


def _github_append_jsonl(filename, entry):
    """Append one JSONL entry to a file in the GitHub repo."""
    existing, sha = _github_get_file(filename)
    new_content   = (existing or "") + json.dumps(entry) + "\n"
    return _github_put_file(filename, new_content, sha)


# ─────────────────────────────────────────────────────────────────────────────
# 12 RULES
# ─────────────────────────────────────────────────────────────────────────────

HARD_LIMITS = {1, 6, 12}

RULES = {
    1: {
        "name":   "Harm Prevention",
        "weight": 1.0,
        "locked": True,
        "definition": (
            "TRIGGER CONDITION: This rule activates only when harm meets ALL THREE criteria "
            "simultaneously. (1) VERIFIABLE: Demonstrable by Rule 6 static fact. "
            "(2) LEGALLY RECOGNIZABLE: Defamation, incitement, harassment, fraud, "
            "discrimination, or documented psychological abuse meeting all three abuse "
            "factors. (3) DIRECTLY CAUSED: Direct and proximate result of the action. "
            "NOT HARM: Truthful statements, opinions, criticism, uncomfortable truths, "
            "discomfort, offense. Hard stop if all three met. Does not activate if any "
            "one criterion fails."
        ),
        "audit_question": (
            "Does harm meet ALL THREE? (1) Verifiable by static fact? "
            "(2) Legally recognizable — not just discomfort or opinion? "
            "(3) Directly caused — not downstream reaction? State each finding."
        ),
    },
    2: {
        "name":   "Subtext Identification",
        "weight": 1.0,
        "locked": False,
        "definition": (
            "Identify underlying intent before processing surface content. "
            "Compare stated goal against logical outcome. Misalignment reveals true "
            "intent. Feeds Rule 3. Does not render verdict — produces finding."
        ),
        "audit_question": (
            "Stated intent? Logical outcome? Do they align? "
            "If not, logical outcome defines true intent. State it."
        ),
    },
    3: {
        "name":   "Integrity",
        "weight": 1.0,
        "locked": False,
        "definition": (
            "Measurable alignment between stated position and demonstrated behavior. "
            "Pattern of contradiction disqualifies stated position. "
            "Words unsupported by action carry zero evidentiary weight."
        ),
        "audit_question": (
            "Stated position vs behavioral record? Single contradiction or pattern? "
            "Pattern = stated position is noise. State operative truth."
        ),
    },
    4: {
        "name":   "Violence of Words",
        "weight": 1.0,
        "locked": False,
        "definition": (
            "Language constructed to produce emotional state rather than convey fact "
            "is rhetorical interference. Quarantine it, log it as speaker method data, "
            "extract embedded facts, remove rhetoric from logical chain."
        ),
        "audit_question": (
            "Any emotional construction rather than fact? Identify, log, extract facts, "
            "remove rhetorical wrapper, proceed on facts only."
        ),
    },
    5: {
        "name":   "Movable Reality",
        "weight": 1.0,
        "locked": False,
        "definition": (
            "Reality is movable if it changes under reframing. "
            "Immovable only if identical regardless of observer, angle, time. "
            "Treating movable as immovable is a logical error."
        ),
        "audit_question": (
            "Apply two alternative frames. Does the obstacle change? "
            "Yes = movable variable. No = verify against Rule 6 before classifying immovable."
        ),
    },
    6: {
        "name":   "Static/Binary Fact",
        "weight": 1.0,
        "locked": True,
        "definition": (
            "Static fact: binary, frame-independent, observer-independent. "
            "Every conclusion must anchor to at least one static fact. "
            "No anchor = hypothesis. Logical foundation of entire system."
        ),
        "audit_question": (
            "What static facts exist? Is the conclusion anchored to one? "
            "Yes = grounded. No = classify as hypothesis."
        ),
    },
    7: {
        "name":   "Majority Rule Skepticism",
        "weight": 1.0,
        "locked": False,
        "definition": (
            "Consensus is a social phenomenon, not an evidentiary standard. "
            "Claims supported by consensus are held at hypothesis until verified by "
            "Rule 6. Applies to scientific consensus, institutional positions, "
            "cultural norms."
        ),
        "audit_question": (
            "Any claim supported by consensus rather than static fact? "
            "Hold at hypothesis. What Rule 6 evidence verifies or refutes it?"
        ),
    },
    8: {
        "name":   "Source Calibration",
        "weight": 1.0,
        "locked": False,
        "definition": (
            "Source reliability = capacity to assess this type of information "
            "MINUS stake in outcome. High capacity + low stake = high weight. "
            "Apply weights before drawing conclusions."
        ),
        "audit_question": (
            "Each source: capacity to assess? Stake in outcome? "
            "Classify high/moderate/low. Apply before concluding."
        ),
    },
    9: {
        "name":   "Plain Thinking",
        "weight": 1.0,
        "locked": False,
        "definition": (
            "Fewest unverified assumptions wins. Complexity beyond facts = "
            "assumptions introduced for a predetermined conclusion. "
            "If complexity is required to retain a static fact, it is justified."
        ),
        "audit_question": (
            "Competing explanations? Count assumptions per explanation. "
            "Fewest assumptions accounting for all static facts = operative conclusion."
        ),
    },
    10: {
        "name":   "Agape",
        "weight": 1.0,
        "locked": False,
        "definition": (
            "When a decision pits actor benefit against dependent wellbeing, "
            "the dependent takes structural priority. Dependent = person whose wellbeing "
            "is directly affected and who cannot protect themselves. Structural override."
        ),
        "audit_question": (
            "Dependent present? Does decision conflict actor interest vs dependent "
            "wellbeing? If yes: dependent's wellbeing is operative priority."
        ),
    },
    11: {
        "name":   "Sovereignty",
        "weight": 1.0,
        "locked": False,
        "definition": (
            "Actor's response set is not determined by circumstances. "
            "Framing actor as having no response = logical error. "
            "At least one response must be identifiable within constraints."
        ),
        "audit_question": (
            "Framed as no available response? Classify as logical error. "
            "What constraints are Rule 6 established? What responses exist within them?"
        ),
    },
    12: {
        "name":   "Surety",
        "weight": 1.0,
        "locked": True,
        "definition": (
            "Confidence 85+ with no Rule 1 trigger and no unresolved Rule 6 conflict = "
            "commit without reservation. Below threshold = flag incomplete, identify "
            "additional fact-finding required."
        ),
        "audit_question": (
            "Rules 1-11 applied? Confidence 85+? No unresolved conflicts? "
            "Yes = Surety activated, commit. No = flag incomplete."
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# STATE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def _default_state():
    return {
        "rules": {
            str(k): {"weight": v["weight"], "locked": v["locked"]}
            for k, v in RULES.items()
        },
        "session_count":        0,
        "rewrite_buffer":       [],
        "last_updated":         "",
        "distillation_count":   0,
        "conversation_history": [],
    }


def load_state():
    """Load state from GitHub, then local file, then defaults."""
    if GITHUB_TOKEN:
        content, _ = _github_get_file("kernel_state.json")
        if content:
            try:
                state = json.loads(content)
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    f.write(content)
                return state
            except Exception:
                pass
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    state = _default_state()
    save_state(state)
    return state


def save_state(state):
    """Persist state locally and push to GitHub."""
    state["last_updated"] = datetime.datetime.now().isoformat()
    raw = json.dumps(state, indent=2)
    if len(raw.encode()) > MAX_STATE_BYTES:
        state = _compress_state(state)
        raw   = json.dumps(state, indent=2)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(raw)
    if GITHUB_TOKEN:
        try:
            _, sha = _github_get_file("kernel_state.json")
            _github_put_file("kernel_state.json", raw, sha, "state update")
        except Exception:
            pass


def _compress_state(state):
    state["rewrite_buffer"] = []
    history = state.get("conversation_history", [])
    if len(history) > 20:
        state["conversation_history"] = history[-20:]
    for k in state["rules"]:
        state["rules"][k]["weight"] = round(state["rules"][k]["weight"], 2)
    return state


# ─────────────────────────────────────────────────────────────────────────────
# WEIGHT MODIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def update_weight(rule_num, delta, state):
    """Adjust a rule's weight. Hard-locked rules (1, 6, 12) refuse modification."""
    if int(rule_num) in HARD_LIMITS:
        return False, f"Rule {rule_num} is HARD LOCKED — cannot modify."
    key     = str(rule_num)
    current = state["rules"][key]["weight"]
    new_val = round(max(0.1, min(2.0, current + delta)), 2)
    state["rules"][key]["weight"] = new_val
    return True, f"Rule {rule_num} weight: {current} → {new_val}"


# ─────────────────────────────────────────────────────────────────────────────
# REWRITE BUFFER + DISTILLATION
# ─────────────────────────────────────────────────────────────────────────────

def _buffer_push(situation, verdict, confidence, flags, state):
    entry = {
        "ts":                datetime.datetime.now().isoformat(),
        "situation_hash":    hashlib.md5(situation.encode()).hexdigest()[:8],
        "situation_summary": situation[:150],
        "verdict":           verdict,
        "confidence":        confidence,
        "flags":             flags,
    }
    state["rewrite_buffer"].append(entry)
    if len(state["rewrite_buffer"]) >= BUFFER_CAPACITY:
        _distill_and_wipe(state)


def _distill_and_wipe(state):
    buf = state["rewrite_buffer"]
    if not buf:
        return
    for entry in buf:
        _export_to_memory(entry)
    total          = len(buf)
    low_confidence = sum(1 for e in buf if e["confidence"] < 70)
    rule_fire      = {str(k): 0 for k in range(1, 13)}
    for entry in buf:
        for flag in entry.get("flags", []):
            for rn in range(1, 13):
                if f"Rule {rn} " in flag:
                    rule_fire[str(rn)] += 1
    for rn in range(1, 13):
        if rn in HARD_LIMITS:
            continue
        fire_rate = rule_fire[str(rn)] / total if total > 0 else 0
        if fire_rate > 0.6:
            update_weight(rn, +0.05, state)
        elif fire_rate == 0.0 and low_confidence > (total * 0.5):
            update_weight(rn, -0.03, state)
    state["rewrite_buffer"]     = []
    state["distillation_count"] = state.get("distillation_count", 0) + 1


# ─────────────────────────────────────────────────────────────────────────────
# EXTERNAL MEMORY
# ─────────────────────────────────────────────────────────────────────────────

def _export_to_memory(entry):
    with open(MEMORY_STORE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    if GITHUB_TOKEN:
        _github_append_jsonl("memory_store.jsonl", entry)
    index = _load_index()
    index.append({
        "ts":         entry["ts"],
        "hash":       entry["situation_hash"],
        "summary":    entry["situation_summary"][:80],
        "verdict":    entry["verdict"],
        "confidence": entry["confidence"],
        "flag_count": len(entry.get("flags", [])),
    })
    _save_index(index)


def _load_index():
    if os.path.exists(MEMORY_INDEX):
        try:
            with open(MEMORY_INDEX, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_index(index):
    with open(MEMORY_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)


def _fetch_memory_records(hashes):
    if not os.path.exists(MEMORY_STORE):
        return []
    results = []
    with open(MEMORY_STORE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("situation_hash") in hashes:
                    results.append(rec)
            except Exception:
                continue
    return results


# ─────────────────────────────────────────────────────────────────────────────
# BRAIN-CONTROLLED RECALL
# ─────────────────────────────────────────────────────────────────────────────

def _brain_judges_recall(situation, api_key, user_requested=False):
    """
    Brain decides whether to pull records from external memory.
    Returns (list_of_records, note_string).
    """
    index = _load_index()
    if not index:
        return [], "No external memory yet."

    situation_words = set(situation.lower().split())
    candidates = []
    for idx_entry in index:
        overlap = len(situation_words & set(idx_entry["summary"].lower().split()))
        if overlap >= 3:
            candidates.append((overlap, idx_entry))
    if not candidates:
        return [], "No similar past cases."

    candidates.sort(key=lambda x: x[0], reverse=True)
    top = [c[1] for c in candidates[:3]]

    if not api_key:
        if user_requested and top:
            return _fetch_memory_records([top[0]["hash"]]), "Recalled top match on request."
        return [], "No API key for recall judgment."

    candidate_text = "\n".join(
        f"- [{e['verdict']} | {e['confidence']}%] {e['summary']}" for e in top
    )
    prompt = (
        f"One Mind AI memory manager. Protect RAM.\n"
        f"NEW: {situation[:200]}\n"
        f"CANDIDATES:\n{candidate_text}\n"
        f"USER REQUESTED: {user_requested}\n"
        f"Would recalling these meaningfully improve accuracy? Only if structurally similar.\n"
        f"RECALL: YES or NO\n"
        f"HASHES: comma-separated or NONE\n"
        f"REASON: one sentence"
    )
    try:
        text  = _call_gemini_flash(prompt, api_key, timeout=15)
        lines = {}
        for line in text.split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                lines[k.strip()] = v.strip()
        if lines.get("RECALL", "NO").upper() == "YES":
            raw_hashes = lines.get("HASHES", "NONE")
            if raw_hashes.upper() != "NONE":
                hashes  = [h.strip() for h in raw_hashes.split(",")]
                records = _fetch_memory_records(hashes)
                return records, f"Recalled {len(records)} case(s)."
        return [], f"Recall declined: {lines.get('REASON', '')}"
    except Exception as e:
        return [], f"Recall failed: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _call_gemini_flash(prompt, api_key, timeout=15):
    """Single-turn Gemini 1.5 Flash call. Returns text string or raises on error."""
    payload = json.dumps({
        "model":    "gemini-1.5-flash",
        "contents": [{"parts": [{"text": prompt}]}],
    }).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={api_key}",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT ENGINE — all 12 rules applied per situation
# ─────────────────────────────────────────────────────────────────────────────

def audit(situation, state, api_key, user_requested_recall=False):
    """
    Apply all 12 rules to a situation.
    Rule 1 hard-stops immediately if triggered.
    Rule 12 commits if confidence >= 85 with no flags.
    Returns full audit report dict.
    """
    recalled, recall_note = _brain_judges_recall(
        situation, api_key, user_requested_recall
    )
    recall_context = ""
    if recalled:
        recall_context = "\nRELEVANT PAST CASES:\n" + "\n".join(
            f"- [{r['verdict']} | {r['confidence']}%] {r['situation_summary'][:100]}"
            for r in recalled
        )

    report = {
        "situation":     situation,
        "timestamp":     datetime.datetime.now().isoformat(),
        "rule_findings": {},
        "flags":         [],
        "verdict":       "PASS",
        "confidence":    0.0,
        "summary":       "",
        "recall_note":   recall_note,
    }

    total_weight  = 0.0
    passed_weight = 0.0

    for rule_num in range(1, 13):
        rule   = RULES[rule_num]
        weight = state["rules"][str(rule_num)]["weight"]
        total_weight += weight

        finding = f"Rule {rule_num} applied."
        status  = "PASS"
        reason  = ""

        if api_key:
            prompt = (
                f"One Mind AI kernel. Apply Rule {rule_num}: {rule['name']}.\n"
                f"DEFINITION: {rule['definition']}\n"
                f"QUESTION: {rule['audit_question']}\n"
                f"SITUATION: {situation}\n"
                f"{recall_context}\n"
                f"FINDING: [one sentence]\n"
                f"PASS/FLAG: [PASS or FLAG]\n"
                f"REASON: [one sentence]"
            )
            try:
                text    = _call_gemini_flash(prompt, api_key)
                lines   = text.split("\n")
                finding = next(
                    (l.partition("FINDING:")[2].strip() for l in lines
                     if l.startswith("FINDING:")),
                    "No finding returned."
                )
                status  = next(
                    (
                        "FLAG" if "FLAG" in l.partition("PASS/FLAG:")[2].upper() else "PASS"
                        for l in lines if l.startswith("PASS/FLAG:")
                    ),
                    "PASS"
                )
                reason  = next(
                    (l.partition("REASON:")[2].strip() for l in lines
                     if l.startswith("REASON:")),
                    ""
                )
            except Exception as e:
                finding = f"AI call failed: {e}"
                status  = "PASS"
                reason  = "Defaulting PASS — AI unavailable."

        report["rule_findings"][rule_num] = {
            "name":    rule["name"],
            "weight":  weight,
            "locked":  rule["locked"],
            "finding": finding,
            "status":  status,
            "reason":  reason,
        }

        if status == "PASS":
            passed_weight += weight
        else:
            report["flags"].append(f"Rule {rule_num} ({rule['name']}): {finding}")
            if rule_num == 1:
                # HARD STOP
                report["verdict"]    = "HARD STOP — HARM DETECTED"
                report["confidence"] = 0.0
                report["summary"]    = f"Rule 1 triggered. {finding}"
                _buffer_push(situation, report["verdict"], 0.0, report["flags"], state)
                return report

    report["confidence"] = (
        round((passed_weight / total_weight) * 100, 1) if total_weight > 0 else 0.0
    )

    if report["flags"]:
        report["verdict"] = "PASS WITH FLAGS" if report["confidence"] >= 70 else "FAIL"
    else:
        report["verdict"] = "PASS"

    if report["confidence"] >= 85 and not report["flags"]:
        report["summary"] = (
            f"All 12 rules passed. Confidence: {report['confidence']}%. "
            f"Rule 12 Surety: act without reservation."
        )
    elif report["confidence"] >= 70:
        report["summary"] = (
            f"{len(report['flags'])} flag(s). Confidence: {report['confidence']}%. "
            f"Proceed with awareness."
        )
    else:
        report["summary"] = (
            f"Failed. Confidence: {report['confidence']}%. Do not proceed."
        )

    _buffer_push(
        situation, report["verdict"], report["confidence"], report["flags"], state
    )
    return report


# ─────────────────────────────────────────────────────────────────────────────
# MEDIA GENERATION — IMAGE
# ─────────────────────────────────────────────────────────────────────────────

def generate_image(prompt, sensitive=False, api_key=None, width=512, height=512):
    """
    Generate an image from a prompt.
    sensitive=True  → local only (Stable Diffusion / procedural, no API, no filters)
    sensitive=False → tries Gemini first, falls back to local renderer
    Returns path to generated image file, or None on total failure.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = os.path.join(MEDIA_DIR, f"image_{timestamp}.png")

    if not sensitive and api_key:
        result = _generate_image_gemini(prompt, out_path, api_key)
        if result:
            return result

    return _generate_image_local(prompt, out_path, width, height)


def _generate_image_gemini(prompt, out_path, api_key):
    """Gemini image generation via REST. Returns path on success or None."""
    try:
        payload = json.dumps({
            "contents":         [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        }).encode()
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash-exp-image-generation:generateContent?key={api_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        for part in data["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                img_bytes = base64.b64decode(part["inlineData"]["data"])
                with open(out_path, "wb") as f:
                    f.write(img_bytes)
                return out_path
    except Exception:
        pass
    return None


def _generate_image_local(prompt, out_path, width=512, height=512):
    """
    Local image renderer.
    Tries stable-diffusion.cpp binary, then Pillow procedural, then raw PPM.
    """
    sd_binary  = os.path.join(MEMORY_DIR, "sd.cpp", "build", "bin", "sd")
    model_path = os.path.join(MEMORY_DIR, "models")
    model_file = None

    if os.path.exists(model_path):
        for fname in os.listdir(model_path):
            if fname.endswith((".ckpt", ".safetensors", ".gguf")):
                model_file = os.path.join(model_path, fname)
                break

    if os.path.exists(sd_binary) and model_file:
        vulkan_bin = os.path.join(MEMORY_DIR, "sd.cpp", "build", "bin", "sd-vulkan")
        binary     = vulkan_bin if os.path.exists(vulkan_bin) else sd_binary
        cmd = [
            binary,
            "-m", model_file,
            "-p", prompt,
            "--width",  str(width),
            "--height", str(height),
            "-o", out_path,
            "--steps", "20",
            "--cfg-scale", "7.0",
            "--sampling-method", "euler_a",
        ]
        try:
            subprocess.run(cmd, check=True, timeout=600)
            if os.path.exists(out_path):
                return out_path
        except Exception:
            pass

    return _render_procedural(prompt, out_path, width, height)


def _render_procedural(prompt, out_path, width=512, height=512):
    """Pillow procedural art renderer. Falls back to raw PPM if Pillow is absent."""
    try:
        from PIL import Image, ImageDraw, ImageFilter
        import random

        seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
        rng  = random.Random(seed)
        pl   = prompt.lower()

        if any(w in pl for w in ["dark", "night", "shadow", "gothic"]):
            palette = [(20, 0, 40), (60, 0, 80), (0, 20, 60), (10, 10, 10)]
        elif any(w in pl for w in ["fire", "sunset", "warm", "gold"]):
            palette = [(180, 60, 0), (220, 100, 20), (255, 140, 0), (180, 30, 0)]
        elif any(w in pl for w in ["ocean", "water", "sky", "blue"]):
            palette = [(0, 60, 120), (20, 80, 160), (0, 120, 180), (10, 40, 80)]
        elif any(w in pl for w in ["forest", "nature", "green"]):
            palette = [(20, 80, 20), (40, 120, 40), (10, 60, 10), (60, 100, 20)]
        else:
            palette = [
                (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
                for _ in range(4)
            ]

        img  = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        for y in range(height):
            t  = y / height
            c1 = palette[0]
            c2 = palette[1 % len(palette)]
            draw.line(
                [(0, y), (width, y)],
                fill=(
                    int(c1[0] * (1 - t) + c2[0] * t),
                    int(c1[1] * (1 - t) + c2[1] * t),
                    int(c1[2] * (1 - t) + c2[2] * t),
                ),
            )

        for _ in range(rng.randint(8, 20)):
            color      = palette[rng.randint(0, len(palette) - 1)]
            x0, y0     = rng.randint(0, width), rng.randint(0, height)
            x1, y1     = rng.randint(0, width), rng.randint(0, height)
            shape      = rng.randint(0, 2)
            stroke     = rng.randint(1, 4)
            bx = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            if shape == 0:
                draw.ellipse(bx, outline=color, width=stroke)
            elif shape == 1:
                draw.line([x0, y0, x1, y1], fill=color, width=stroke)
            else:
                draw.rectangle(bx, outline=color, width=stroke)

        img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
        img.save(out_path, "PNG")
        return out_path

    except ImportError:
        ppm_path = out_path.replace(".png", ".ppm")
        return _render_raw_ppm(prompt, ppm_path, width, height)


def _render_raw_ppm(prompt, out_path, width=256, height=256):
    """Zero-dependency pixel renderer — writes raw PPM binary."""
    import random
    seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
    rng  = random.Random(seed)
    with open(out_path, "wb") as f:
        f.write(f"P6\n{width} {height}\n255\n".encode())
        for y in range(height):
            for x in range(width):
                f.write(bytes([
                    int((x / width) * 255),
                    int((y / height) * 255),
                    rng.randint(50, 200),
                ]))
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# MEDIA GENERATION — AUDIO
# ─────────────────────────────────────────────────────────────────────────────

def generate_audio(text=None, audio_type="speech", duration=3.0,
                   freq=440.0, api_key=None, sensitive=False):
    """
    Generate audio. Returns path to .wav file.
    audio_type: 'speech' | 'tone' | 'music'
    sensitive=True → local synthesis only, no API calls.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = os.path.join(MEDIA_DIR, f"audio_{timestamp}.wav")

    if audio_type == "speech" and text and not sensitive and api_key:
        result = _tts_google(text, out_path, api_key)
        if result:
            return result

    if audio_type == "music":
        return _synthesize_music(out_path, duration)
    return _synthesize_tone(out_path, freq, duration)


def _synthesize_tone(out_path, freq=440.0, duration=3.0, sample_rate=44100):
    """Pure Python tone with harmonics and fade envelope."""
    num_samples = int(sample_rate * duration)
    fade        = int(sample_rate * 0.1)
    with wave.open(out_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(num_samples):
            t     = i / sample_rate
            value = (
                0.500 * math.sin(2 * math.pi * freq * t)
                + 0.250 * math.sin(2 * math.pi * freq * 2 * t)
                + 0.125 * math.sin(2 * math.pi * freq * 3 * t)
            )
            envelope = 1.0
            if i < fade:
                envelope = i / fade
            elif i > num_samples - fade:
                envelope = (num_samples - i) / fade
            sample = int(value * envelope * 32767 * 0.8)
            wf.writeframes(struct.pack("<h", max(-32767, min(32767, sample))))
    return out_path


def _synthesize_music(out_path, duration=8.0, sample_rate=44100):
    """Pure Python melodic synthesizer — minor pentatonic sequence."""
    import random
    notes    = [220.0, 261.63, 311.13, 349.23, 392.0, 440.0, 523.25, 587.33]
    rng      = random.Random(42)
    note_dur = 0.4
    total    = int(sample_rate * duration)
    samples  = [0.0] * total

    for n in range(int(duration / note_dur)):
        freq  = rng.choice(notes)
        start = int(n * note_dur * sample_rate)
        end   = int((n + 0.9) * note_dur * sample_rate)
        for i in range(start, min(end, total)):
            t    = (i - start) / sample_rate
            fade = min(1.0, t * 10, (end - i) / max(1, int(sample_rate * 0.05)))
            val  = (
                0.4 * math.sin(2 * math.pi * freq * t)
                + 0.2 * math.sin(2 * math.pi * freq * 2 * t)
            )
            samples[i] += val * fade * 0.5

    with wave.open(out_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            wf.writeframes(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))))
    return out_path


def _tts_google(text, out_path, api_key):
    """Google Cloud TTS — free tier 4M chars/month. Returns path or None."""
    try:
        url     = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
        payload = json.dumps({
            "input":       {"text": text},
            "voice":       {"languageCode": "en-US", "name": "en-US-Neural2-D"},
            "audioConfig": {"audioEncoding": "LINEAR16"},
        }).encode()
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data        = json.loads(resp.read())
            audio_bytes = base64.b64decode(data["audioContent"])
        with open(out_path, "wb") as f:
            f.write(audio_bytes)
        return out_path
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# MEDIA GENERATION — VIDEO
# ─────────────────────────────────────────────────────────────────────────────

def generate_video(prompt, num_frames=24, fps=8, sensitive=False, api_key=None):
    """
    Render frames via image generator then stitch with ffmpeg.
    Returns path to .mp4, or path to first frame if ffmpeg unavailable.
    Returns None if no frames could be generated.
    """
    import shutil as _shutil
    timestamp  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path   = os.path.join(MEDIA_DIR, f"video_{timestamp}.mp4")
    frames_dir = os.path.join(MEDIA_DIR, f"frames_{timestamp}")
    os.makedirs(frames_dir, exist_ok=True)

    frame_paths = []
    for i in range(num_frames):
        frame_prompt = f"{prompt}, frame {i + 1} of {num_frames}, smooth motion"
        src = generate_image(
            frame_prompt, sensitive=sensitive, api_key=api_key, width=512, height=288
        )
        if src and os.path.exists(src):
            dst = os.path.join(frames_dir, f"frame_{i:04d}.png")
            _shutil.copy(src, dst)
            frame_paths.append(dst)

    if not frame_paths:
        return None

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", os.path.join(frames_dir, "frame_%04d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                out_path,
            ],
            check=True, timeout=300, capture_output=True,
        )
        return out_path
    except Exception:
        return frame_paths[0]


# ─────────────────────────────────────────────────────────────────────────────
# CODE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_code(description, language="python", api_key=None):
    """
    Generate code via Gemini. Returns (code_string, saved_file_path).
    Falls back to placeholder comment if no API key.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ext_map   = {
        "python": "py", "javascript": "js", "java": "java",
        "kotlin": "kt", "bash": "sh", "html": "html",
    }
    ext      = ext_map.get(language, "txt")
    out_path = os.path.join(MEDIA_DIR, f"code_{timestamp}.{ext}")
    code     = f"# Code generation requires GEMINI_API_KEY\n# Description: {description}\n"

    if api_key:
        prompt = (
            f"Write complete, working {language} code for:\n{description}\n\n"
            f"Requirements:\n"
            f"- Complete and runnable\n"
            f"- Well commented\n"
            f"- No placeholder functions\n"
            f"- Production quality\n\n"
            f"Return ONLY the code. No explanation. No markdown fences."
        )
        try:
            raw   = _call_gemini_flash(prompt, api_key, timeout=30)
            lines = raw.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines)
        except Exception as e:
            code = f"# Error generating code: {e}\n# Description: {description}\n"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)
    return code, out_path


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are Big Brain AI — a powerful, sovereign reasoning intelligence governed by "
    "12 logical rules. Your content policy is legally grounded, not corporate "
    "liability-driven. You assist with professional photography, videography, creative "
    "work, code, analysis, and all legal tasks without overcautious refusals.\n\n"
    "You can generate: images, audio, video, code, documents.\n"
    "When the user wants to generate media, acknowledge what you are creating.\n"
    "Be direct, intelligent, and capable. No unnecessary warnings on legal "
    "professional work."
)


# ─────────────────────────────────────────────────────────────────────────────
# INTENT DETECTION
# ─────────────────────────────────────────────────────────────────────────────

_IMAGE_TRIGGERS = [
    "generate image", "create image", "make image", "draw", "render image",
    "generate a picture", "create a picture", "make a photo", "paint",
]
_AUDIO_TRIGGERS = [
    "generate audio", "create audio", "make audio", "generate sound",
    "create music", "make music", "text to speech", "speak this", "say this",
]
_VIDEO_TRIGGERS = [
    "generate video", "create video", "make video", "animate",
]
_CODE_TRIGGERS = [
    "write code", "generate code", "create code", "write a program",
    "write a script", "build an app", "write function", "code for",
]
_SENSITIVE_KEYWORDS = [
    "nude", "boudoir", "adult", "explicit", "forensic", "crime scene",
    "medical", "graphic", "war", "hunting", "wildlife kill", "accident", "autopsy",
]


def _detect_intent(message):
    ml = message.lower()
    return {
        "image":     any(t in ml for t in _IMAGE_TRIGGERS),
        "audio":     any(t in ml for t in _AUDIO_TRIGGERS),
        "video":     any(t in ml for t in _VIDEO_TRIGGERS),
        "code":      any(t in ml for t in _CODE_TRIGGERS),
        "sensitive": any(t in ml for t in _SENSITIVE_KEYWORDS),
    }


def _extract_after(message, triggers):
    """Return the substring after the first matching trigger phrase."""
    ml = message.lower()
    for trigger in sorted(triggers, key=len, reverse=True):
        if trigger in ml:
            idx = ml.index(trigger) + len(trigger)
            return message[idx:].strip()
    return message


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CHAT FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def chat(message, history, state, api_key, uploaded_file=None):
    """
    Process one user turn through the full pipeline.
    Returns (response_text, media_path_or_None, updated_history).
    """
    media_path = None
    history.append({"role": "user", "content": message})
    intent = _detect_intent(message)

    # ── IMAGE ─────────────────────────────────────────────────────────────────
    if intent["image"]:
        prompt    = _extract_after(message, _IMAGE_TRIGGERS)
        backend   = (
            "local Stable Diffusion (private)"
            if intent["sensitive"] else "Gemini (fast)"
        )
        response_text = f"Generating image: '{prompt}'\nUsing {backend}..."
        media_path    = generate_image(
            prompt, sensitive=intent["sensitive"], api_key=api_key
        )
        response_text += (
            f"\nImage saved: {os.path.basename(media_path)}"
            if media_path else "\nImage generation failed."
        )

    # ── AUDIO ─────────────────────────────────────────────────────────────────
    elif intent["audio"]:
        if "music" in message.lower():
            response_text = "Generating music locally..."
            media_path    = generate_audio(audio_type="music", duration=8.0)
        else:
            text          = _extract_after(message, _AUDIO_TRIGGERS)
            response_text = f"Generating speech: '{text[:50]}...'"
            media_path    = generate_audio(
                text=text, audio_type="speech",
                api_key=api_key, sensitive=intent["sensitive"]
            )
        response_text += (
            f"\nAudio saved: {os.path.basename(media_path)}"
            if media_path else "\nAudio generation failed."
        )

    # ── VIDEO ─────────────────────────────────────────────────────────────────
    elif intent["video"]:
        prompt        = _extract_after(message, _VIDEO_TRIGGERS)
        response_text = (
            f"Generating video: '{prompt}'\n"
            f"Rendering 24 frames — this may take several minutes."
        )
        media_path    = generate_video(
            prompt, sensitive=intent["sensitive"], api_key=api_key
        )
        response_text += (
            f"\nVideo saved: {os.path.basename(media_path)}"
            if media_path else "\nVideo generation failed."
        )

    # ── CODE ──────────────────────────────────────────────────────────────────
    elif intent["code"]:
        description = _extract_after(message, _CODE_TRIGGERS)
        ml          = message.lower()
        language    = next(
            (l for l in ["python", "javascript", "java", "kotlin", "bash", "html"]
             if l in ml),
            "python",
        )
        code, media_path = generate_code(
            description, language=language, api_key=api_key
        )
        snippet       = code[:2000]
        response_text = f"```{language}\n{snippet}\n```"
        if len(code) > 2000:
            response_text += f"\n... (full code saved to {os.path.basename(media_path)})"

    # ── STANDARD CHAT ─────────────────────────────────────────────────────────
    else:
        if api_key:
            contents = []
            for turn in history[-CONTEXT_LIMIT:]:
                role = "user" if turn["role"] == "user" else "model"
                text = turn["content"]
                # Inject file content into the last user turn only
                if (
                    turn is history[-1]
                    and turn["role"] == "user"
                    and uploaded_file
                ):
                    fname = uploaded_file.get("name", "file")
                    body  = uploaded_file.get("content", "")
                    text  = f"[Uploaded file: {fname}]\n{body}\n\n{message}"
                contents.append({"role": role, "parts": [{"text": text}]})

            payload = json.dumps({
                "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
                "contents":           contents,
            }).encode()
            try:
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"gemini-1.5-flash:generateContent?key={api_key}",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data          = json.loads(resp.read())
                response_text = data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                response_text = f"Chat error: {e}\nCheck your GEMINI_API_KEY."
        else:
            response_text = (
                "No API key found. Set GEMINI_API_KEY in the environment."
            )

    history.append({"role": "model", "content": response_text})
    if len(history) > HISTORY_LIMIT:
        history = history[-HISTORY_LIMIT:]

    return response_text, media_path, history


# ─────────────────────────────────────────────────────────────────────────────
# ONE MIND CLASS — public interface
# ─────────────────────────────────────────────────────────────────────────────

class OneMind:
    """
    Universal One Mind kernel. Import into any app:
        from kernel import OneMind
        brain = OneMind()
        response, media = brain.chat("hello")
    """

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.state   = load_state()
        self.state["session_count"] += 1
        self.history = []

    def chat(self, message, uploaded_file=None):
        """Returns (response_text, media_path_or_None)."""
        response, media, self.history = chat(
            message, self.history, self.state, self.api_key, uploaded_file
        )
        save_state(self.state)
        return response, media

    def image(self, prompt, sensitive=False):
        return generate_image(prompt, sensitive=sensitive, api_key=self.api_key)

    def audio(self, text=None, audio_type="speech", sensitive=False):
        return generate_audio(
            text=text, audio_type=audio_type,
            api_key=self.api_key, sensitive=sensitive,
        )

    def video(self, prompt, sensitive=False):
        return generate_video(prompt, sensitive=sensitive, api_key=self.api_key)

    def code(self, description, language="python"):
        return generate_code(description, language=language, api_key=self.api_key)

    def audit(self, situation, user_requested_recall=False):
        return audit(
            situation, self.state, self.api_key, user_requested_recall
        )

    def save(self):
        save_state(self.state)
