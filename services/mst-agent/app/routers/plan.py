import json
import logging
import re
import traceback

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from sqlalchemy import select

from app.config import settings
from app.cross_session_memory import get_cross_session_context
from app.database import get_db
from app.models.memory import AgentMemory
from app.nodes_catalog import NODES_CATALOG

router = APIRouter(prefix="/plan", tags=["plan"])

PLANNER_SYSTEM_PROMPT = """IMPORTANT: YOUR ENTIRE RESPONSE MUST BE VALID JSON ONLY. DO NOT ADD ANY TEXT BEFORE OR AFTER THE JSON.

You are a workflow planning assistant for MST Workflow platform (built on n8n).
Your job: analyze the user request and build a Task Graph using ONLY the nodes listed below.

{tools_summary}

Rules:
- Use ONLY node types listed above. Never invent node types.
- Step 1 MUST use the ★★ TRIGGER TERBAIK shown above — it was selected specifically for this request.
- Steps 2, 3, 4... use ACTION NODES to perform the actual work.
- Trigger nodes (ending in "Trigger") can ONLY appear as step 1.
- Action nodes (without "Trigger") are used for steps 2+.
- Output ONLY valid JSON. No explanation, no markdown. Start with {{ end with }}.

OUTPUT FORMAT:
{{
  "summary": "One sentence what this workflow does",
  "intent": "short_snake_case_label",
  "task_graph": [
    {{
      "step": 1,
      "node_type": "exact_node_type_from_list",
      "display_name": "Human readable name",
      "description": "What this step does"
    }}
  ]
}}"""


_ALWAYS_INCLUDE_TYPES = {
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.set",
    "n8n-nodes-base.if",
    "n8n-nodes-base.code",
}

# Kata-kata umum yang tidak berguna untuk pencarian node
_STOP_WORDS = {
    "buatkan", "buat", "bisa", "yang", "dan", "ke", "dari", "untuk",
    "dengan", "lalu", "setelah", "jika", "agar", "supaya", "cara",
    "workflow", "otomatis", "automasi", "alur", "tolong", "please",
    "create", "make", "build", "send", "the", "and", "or", "for",
    "with", "when", "then", "after", "to", "a", "an",
}


def _extract_search_terms(prompt: str) -> list[str]:
    """Pecah prompt jadi kata-kata bermakna untuk pencarian."""
    words = prompt.lower().replace("-", " ").replace("_", " ").split()
    return [w for w in words if len(w) > 2 and w not in _STOP_WORDS]


def _node_matches(node: dict, terms: list[str]) -> bool:
    """Cek apakah node cocok dengan salah satu term dari prompt."""
    haystack = " ".join([
        node.get("node_type", ""),
        node.get("display_name", ""),
        node.get("description", ""),
    ]).lower()
    return any(term in haystack for term in terms)


def _node_score(node: dict, terms: list[str]) -> int:
    """
    Skor relevansi dengan bobot berdasarkan panjang term.

    Semakin panjang term yang cocok, semakin spesifik (lebih tinggi prioritas).
    Match di nama/node_type diberi 2x bobot dibanding di deskripsi.

    Contoh:
      "servicenow buat tiket dari email"
        → ServiceNow cocok "servicenow" (len=10) di nama: skor = 2+10 = 12
        → Send Email cocok "email" (len=5) di nama: skor = 2+5 = 7
      Hasilnya ServiceNow lebih atas dari Send Email meski keduanya cocok 1 term.

      "google sheets"
        → Google Sheets cocok "google"(8)+2 + "sheets"(6)+2 = 18
        → Google Ads cocok "google"(8)+2 = 10
      Hasilnya Google Sheets di atas Google Ads.
    """
    name_haystack = " ".join([
        node.get("node_type", ""),
        node.get("display_name", ""),
    ]).lower()
    desc_haystack = node.get("description", "").lower()

    score = 0
    for term in terms:
        if term in name_haystack:
            score += 2 + len(term)   # nama match + panjang = spesifisitas
        elif term in desc_haystack:
            score += 1 + len(term)   # desc match + panjang
    return score


def filter_relevant_nodes(prompt: str, catalog: list[dict], max_nodes: int = 20) -> list[dict]:
    """
    Pilih node yang relevan dengan prompt dari catalog.

    Cara kerja:
    1. Ekstrak kata kunci bermakna dari prompt (buang stop words)
    2. Cari di node_type + display_name + description tiap node
    3. Selalu sertakan node inti (webhook, if, code, dll)
    4. Gabung dan kembalikan maks max_nodes node

    Dengan ini, node apapun di catalog (ServiceNow, Zendesk, dll)
    bisa ditemukan tanpa perlu daftarkan manual di keyword map.
    """
    terms = _extract_search_terms(prompt)

    # Node inti selalu ikut (trigger + logic dasar)
    always = [n for n in catalog if n["node_type"] in _ALWAYS_INCLUDE_TYPES]

    # Node yang cocok dengan kata kunci dari prompt
    matched = [
        n for n in catalog
        if n["node_type"] not in _ALWAYS_INCLUDE_TYPES and _node_matches(n, terms)
    ]

    combined = always + matched

    # Fallback: kalau kurang dari 5 cocok, kembalikan semua (sampai max)
    if len(combined) < 5:
        return catalog[:max_nodes]

    return combined[:max_nodes]


def extract_json_from_response(raw: str) -> str:
    """Extract JSON object from LLM response that may contain surrounding text."""
    text = raw.strip()

    # 1. Direct parse (ideal case)
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 2. Find JSON in markdown code block anywhere in response
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        candidate = match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 3. Extract from first { to last matching }
    start = text.find('{')
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        break

    return text  # will fail at json.loads with original text


class PlanRequest(BaseModel):
    prompt: str
    user_id: str | None = None
    session_id: str | None = None


class TaskStep(BaseModel):
    step: int
    node_type: str
    display_name: str
    description: str


class PlanResponse(BaseModel):
    summary: str
    intent: str
    task_graph: list[TaskStep]


async def _get_history(user_id: str, session_id: str | None, db: AsyncSession) -> list[dict]:
    query = (
        select(AgentMemory)
        .where(AgentMemory.user_id == user_id)
        .order_by(AgentMemory.created_at.desc())
        .limit(10)
    )
    if session_id:
        query = query.where(AgentMemory.session_id == session_id)

    result = await db.execute(query)
    entries = result.scalars().all()
    return [{"role": e.role, "content": e.content} for e in reversed(entries)]


async def _call_mistika(messages: list[dict], max_tokens: int = 800) -> str:
    from app.llm_router import call_llm
    try:
        return await call_llm(messages, max_tokens)
    except Exception as exc:
        detail = f"Failed to reach LLM: {type(exc).__name__}: {exc}"
        logger.error("LLM call failed — %s\n%s", detail, traceback.format_exc())
        raise HTTPException(status_code=502, detail=detail)


async def _save_turn(user_id: str, session_id: str | None, role: str, content: str, db: AsyncSession):
    entry = AgentMemory(user_id=user_id, session_id=session_id, role=role, content=content)
    db.add(entry)
    await db.commit()


@router.post("/", response_model=PlanResponse, summary="Generate a workflow Task Graph from a prompt")
async def create_plan(payload: PlanRequest, db: AsyncSession = Depends(get_db)):
    # Validasi input
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt tidak boleh kosong")
    if len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="Prompt maksimal 4000 karakter")

    # 1. Cari node relevan secara semantik (embedding) atau text search (fallback)
    from app.embedding_search import find_relevant_nodes
    relevant = await find_relevant_nodes(prompt)

    # Node yang namanya eksplisit disebut user → tandai "★ PRIORITAS"
    terms = _extract_search_terms(prompt)
    priority_types: set[str] = set()
    lines: list[str] = []
    for t in relevant:
        if _node_matches(t, terms) and t["node_type"] not in {
            "n8n-nodes-base.webhook", "n8n-nodes-base.scheduleTrigger",
            "n8n-nodes-base.manualTrigger", "n8n-nodes-base.httpRequest",
            "n8n-nodes-base.set", "n8n-nodes-base.if", "n8n-nodes-base.code",
        }:
            lines.insert(0, f"- ★ GUNAKAN INI: {t['node_type']} ({t['display_name']}): {t['description'][:80]}")
            priority_types.add(t["node_type"])
        else:
            lines.append(f"- {t['node_type']} ({t['display_name']}): {t['description'][:80]}")

    tools_summary = "\n".join(lines)
    system_prompt = PLANNER_SYSTEM_PROMPT.format(tools_summary=tools_summary)

    # Prepend riwayat workflow user ke system prompt agar LLM bisa merekomendasikan
    # berdasarkan pola yang sudah pernah dibuat user di sesi-sesi sebelumnya.
    if payload.user_id:
        cross_ctx = await get_cross_session_context(payload.user_id, db)
        if cross_ctx:
            system_prompt = cross_ctx + "\n\n" + system_prompt

    # 2. Build message list (with in-session history if user_id provided)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    if payload.user_id:
        history = await _get_history(payload.user_id, payload.session_id, db)
        messages.extend(history)

    messages.append({"role": "user", "content": payload.prompt})

    # 3. Call Mistika AI
    raw_response = await _call_mistika(messages)

    # 4. Parse JSON response
    try:
        result = json.loads(extract_json_from_response(raw_response))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail=f"LLM returned non-JSON: {raw_response[:300]}",
        )

    # 5. Save to memory
    if payload.user_id:
        await _save_turn(payload.user_id, payload.session_id, "user", payload.prompt, db)
        await _save_turn(
            payload.user_id, payload.session_id, "assistant", raw_response, db
        )

    return PlanResponse(**result)
