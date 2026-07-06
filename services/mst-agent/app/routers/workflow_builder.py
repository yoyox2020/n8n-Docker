import json
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.cross_session_memory import get_cross_session_context
from app.database import get_db
from app.models.workflow_history import WorkflowHistory
from app.routers.plan import _call_mistika, _save_turn, PLANNER_SYSTEM_PROMPT, extract_json_from_response, filter_relevant_nodes
from app.nodes_registry import get_catalog

router = APIRouter(prefix="/workflow", tags=["workflow"])

# Default typeVersion per node type — must match n8n's defaultVersion for each node.
# Agent node: defaultVersion=3.1 (AgentV3 with sub-node architecture for tools/memory/model).
# Using typeVersion=1 causes "Cannot read properties of undefined (reading 'supplyData')" error.
NODE_VERSIONS: dict[str, float] = {
    "n8n-nodes-base.webhook": 2,
    "n8n-nodes-base.httpRequest": 4,
    "n8n-nodes-base.emailSend": 2.1,
    "n8n-nodes-base.gmail": 2,
    "n8n-nodes-base.slack": 2,
    "n8n-nodes-base.googleSheets": 4,
    "n8n-nodes-base.postgres": 2,
    "n8n-nodes-base.set": 3,
    "n8n-nodes-base.if": 2,
    "n8n-nodes-base.code": 2,
    "n8n-nodes-base.merge": 3,
    "@n8n/n8n-nodes-langchain.agent": 3.1,
}


# Node types yang butuh mistikaAiApi credential
MISTIKA_AI_NODE_TYPES = {
    "@n8n/n8n-nodes-langchain.lmChatMistikaAi",
    "@n8n/n8n-nodes-langchain.agent",
}


def _task_graph_to_workflow_json(
    name: str, task_graph: list[dict], mistika_credential: dict | None = None
) -> dict:
    """Convert a task_graph list into a valid n8n workflow JSON."""
    nodes = []
    connections: dict = {}
    used_names: dict[str, int] = {}

    # Deduplicate display_name agar tidak ada node dengan nama sama
    deduped: list[dict] = []
    for step in task_graph:
        base = step["display_name"]
        if base in used_names:
            used_names[base] += 1
            step = {**step, "display_name": f"{base} {used_names[base]}"}
        else:
            used_names[base] = 1
        deduped.append(step)
    task_graph = deduped

    for i, step in enumerate(task_graph):
        node_type = step["node_type"]
        node_name = step["display_name"]
        node_id = str(uuid.uuid4())

        # Auto-assign credential Mistika ke node AI jika tersedia
        credentials: dict = {}
        if mistika_credential and node_type in MISTIKA_AI_NODE_TYPES:
            credentials = {"mistikaAiApi": mistika_credential}

        nodes.append({
            "id": node_id,
            "name": node_name,
            "type": node_type,
            "typeVersion": NODE_VERSIONS.get(node_type, 1),
            "position": [250 + i * 250, 300],
            "parameters": {},
            "credentials": credentials,
        })

        # Connect this node to the next one (linear chain)
        if i < len(task_graph) - 1:
            next_name = task_graph[i + 1]["display_name"]
            connections[node_name] = {
                "main": [[{"node": next_name, "type": "main", "index": 0}]]
            }

    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "staticData": None,
    }


async def _get_mistika_credential_id() -> dict | None:
    """Ambil credential mistikaAiApi pertama dari n8n — dipakai untuk auto-assign ke workflow nodes."""
    url = f"{settings.n8n_base_url}/api/v1/credentials"
    headers = {"X-N8N-API-KEY": settings.n8n_api_key}

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            credentials = resp.json().get("data", [])
            # Cari credential pertama bertipe mistikaAiApi
            for cred in credentials:
                if cred.get("type") == "mistikaAiApi":
                    return {"id": cred["id"], "name": cred["name"]}
        except Exception:
            pass
    return None


async def _create_workflow_in_n8n(workflow_json: dict) -> dict:
    """POST workflow JSON ke n8n public API dan kembalikan workflow yang dibuat."""
    url = f"{settings.n8n_base_url}/api/v1/workflows"
    headers = {
        "X-N8N-API-KEY": settings.n8n_api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, headers=headers, json=workflow_json)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"n8n API error: {exc.response.text}")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to reach n8n: {exc}")


class SuggestToolsRequest(BaseModel):
    prompt: str


class ToolSuggestion(BaseModel):
    node_type: str
    display_name: str
    description: str
    category: str  # "trigger" | "action" | "logic"


class SuggestToolsResponse(BaseModel):
    triggers: list[ToolSuggestion]
    actions: list[ToolSuggestion]
    logic: list[ToolSuggestion]
    total: int


_LOGIC_NODE_TYPES = {
    "n8n-nodes-base.if", "n8n-nodes-base.code", "n8n-nodes-base.set",
    "n8n-nodes-base.merge", "n8n-nodes-base.splitInBatches",
    "n8n-nodes-base.noOp", "n8n-nodes-base.wait", "n8n-nodes-base.switch",
    "n8n-nodes-base.filter", "n8n-nodes-base.aggregate",
}


@router.post("/tools", response_model=SuggestToolsResponse, summary="Temukan node relevan untuk sebuah prompt")
async def suggest_tools(payload: SuggestToolsRequest):
    """
    Dipanggil sebelum build_workflow — mengembalikan node yang relevan
    dengan permintaan user, dikelompokkan per kategori (trigger/action/logic).
    Tidak memanggil LLM, hanya embedding search.
    """
    from app.embedding_search import find_relevant_nodes

    prompt = payload.prompt.strip()
    if not prompt:
        return SuggestToolsResponse(triggers=[], actions=[], logic=[], total=0)

    relevant = await find_relevant_nodes(prompt)

    triggers: list[ToolSuggestion] = []
    actions: list[ToolSuggestion] = []
    logic: list[ToolSuggestion] = []

    for n in relevant:
        nt = n["node_type"]
        desc = n.get("description", "")[:100]

        if nt.lower().endswith("trigger"):
            category = "trigger"
        elif nt in _LOGIC_NODE_TYPES:
            category = "logic"
        else:
            category = "action"

        suggestion = ToolSuggestion(
            node_type=nt,
            display_name=n["display_name"],
            description=desc,
            category=category,
        )

        if category == "trigger":
            triggers.append(suggestion)
        elif category == "logic":
            logic.append(suggestion)
        else:
            actions.append(suggestion)

    return SuggestToolsResponse(
        triggers=triggers,
        actions=actions,
        logic=logic,
        total=len(triggers) + len(actions) + len(logic),
    )


class BuildWorkflowRequest(BaseModel):
    prompt: str
    user_id: str | None = None
    session_id: str | None = None

    def validate_prompt(self) -> str:
        text = self.prompt.strip()
        if not text:
            raise ValueError("Prompt tidak boleh kosong")
        if len(text) > 4000:
            raise ValueError("Prompt maksimal 4000 karakter")
        return text


class BuildWorkflowResponse(BaseModel):
    message: str
    workflow_name: str
    workflow_id: str
    workflow_url: str
    steps: list[dict]


@router.post("/build", response_model=BuildWorkflowResponse, summary="Build and create an n8n workflow from a prompt")
async def build_workflow(payload: BuildWorkflowRequest, db: AsyncSession = Depends(get_db)):
    # Validasi input
    try:
        prompt = payload.validate_prompt()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Routing: agent request → build_agent_workflow(), regular → lanjut di bawah
    if is_agent_request(prompt):
        return await build_agent_workflow(prompt, payload.user_id, payload.session_id, db)

    # 1. Cari trigger TERBAIK dan tools TERBAIK secara TERPISAH
    #    → Category-aware search: trigger tidak campur dengan tools
    from app.embedding_search import find_best_trigger, find_best_tools
    catalog = get_catalog()

    best_triggers = await find_best_trigger(prompt, top_k=4)
    best_tools = await find_best_tools(
        prompt, top_k=14,
        exclude_trigger=best_triggers[0]["node_type"] if best_triggers else None,
    )

    # Format context: trigger section TERATAS dengan ★★ (sinyal kuat ke LLM)
    trigger_lines: list[str] = []
    if best_triggers:
        trigger_lines.append(f"★★ TRIGGER TERBAIK (gunakan sebagai step 1):")
        trigger_lines.append(
            f"  {best_triggers[0]['node_type']} ({best_triggers[0]['display_name']}): "
            f"{best_triggers[0].get('description', '')[:80]}"
        )
        if len(best_triggers) > 1:
            trigger_lines.append("   Alternatif trigger (jika lebih sesuai):")
            for t in best_triggers[1:3]:
                trigger_lines.append(
                    f"  - {t['node_type']} ({t['display_name']}): {t.get('description', '')[:60]}"
                )

    tool_lines: list[str] = []
    tool_lines.append("ACTION NODES (gunakan untuk step 2, 3, 4...):")
    for t in best_tools:
        tool_lines.append(f"- {t['node_type']} ({t['display_name']}): {t.get('description', '')[:80]}")

    tools_summary = "\n".join(trigger_lines + [""] + tool_lines)
    system_prompt = PLANNER_SYSTEM_PROMPT.format(tools_summary=tools_summary)

    # Prepend riwayat workflow user ke system prompt agar LLM punya konteks lintas-sesi.
    # Diletakkan di awal agar terbaca sebagai latar belakang, bukan instruksi utama.
    if payload.user_id:
        cross_ctx = await get_cross_session_context(payload.user_id, db)
        if cross_ctx:
            system_prompt = cross_ctx + "\n\n" + system_prompt

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    # 2. Call LLM to get task_graph
    raw_response = await _call_mistika(messages)

    # 3. Parse JSON response
    try:
        plan = json.loads(extract_json_from_response(raw_response))
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail=f"LLM returned non-JSON: {raw_response[:300]}")

    task_graph: list[dict] = plan.get("task_graph", [])
    workflow_name: str = plan.get("summary", prompt)[:60]

    if not task_graph:
        raise HTTPException(status_code=422, detail="LLM returned empty task_graph")

    # Koreksi dan validasi node_type secara cerdas
    known_types = {n["node_type"] for n in catalog}

    # Buat lookup cepat: display_name lowercase → node_type (untuk koreksi fuzzy)
    display_to_type: dict[str, str] = {}
    for n in catalog:
        display_to_type[n["display_name"].lower()] = n["node_type"]

    # Buat lookup: suffix pendek → node_type (untuk koreksi "WhatsAppTrigger" → full type)
    suffix_to_type: dict[str, str] = {}
    for nt in known_types:
        # "n8n-nodes-base.whatsAppTrigger" → "whatsAppTrigger"
        suffix = nt.split(".")[-1].lower()
        suffix_to_type[suffix] = nt

    for i, step in enumerate(task_graph):
        nt = step.get("node_type", "")
        if nt in known_types:
            continue  # sudah valid

        # Coba koreksi: LLM sering tulis suffix saja tanpa prefix
        nt_lower = nt.lower()
        if nt_lower in suffix_to_type:
            step["node_type"] = suffix_to_type[nt_lower]
            continue

        # Coba koreksi via display_name
        if step.get("display_name", "").lower() in display_to_type:
            step["node_type"] = display_to_type[step["display_name"].lower()]
            continue

        # Step 1 dengan node tidak dikenal → paksa pakai trigger terbaik dari embedding
        if i == 0 and best_triggers:
            step["node_type"] = best_triggers[0]["node_type"]
            step["display_name"] = best_triggers[0]["display_name"]
            continue

        # Step lainnya dengan trigger yang salah posisi → cari versi action-nya
        if nt.endswith("Trigger"):
            action_suffix = nt[:-len("Trigger")].lower()
            if action_suffix in suffix_to_type:
                step["node_type"] = suffix_to_type[action_suffix]
                continue

        # Fallback step lain: pakai httpRequest agar workflow tetap bisa dibuat
        step["node_type"] = "n8n-nodes-base.httpRequest"

    # Verifikasi final — setelah semua koreksi semua harus valid
    still_invalid = [
        step for step in task_graph
        if step.get("node_type", "") not in known_types
    ]
    if still_invalid:
        names = ", ".join(s.get("display_name", s.get("node_type", "?")) for s in still_invalid)
        raise HTTPException(status_code=422, detail=f"Node tidak dikenali setelah koreksi: {names}")

    # 4. Ambil credential mistikaAiApi dari n8n lalu buat workflow
    # Credential ini otomatis di-assign ke node AI — user tidak perlu pilih manual
    mistika_credential = await _get_mistika_credential_id()
    workflow_json = _task_graph_to_workflow_json(workflow_name, task_graph, mistika_credential)
    created = await _create_workflow_in_n8n(workflow_json)

    workflow_id = str(created.get("id", ""))

    # 5. Simpan ke workflow_history dan memory
    if payload.user_id:
        # Simpan ke tabel workflow_history agar bisa ditampilkan sebagai "aktivitas terakhir"
        history_entry = WorkflowHistory(
            user_id=payload.user_id,
            session_id=payload.session_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            workflow_url=f"{settings.n8n_base_url}/workflow/{workflow_id}",
            steps=task_graph,
            original_prompt=payload.prompt,
        )
        db.add(history_entry)
        await db.commit()

        # Simpan ringkasan ke chat memory untuk konteks percakapan
        await _save_turn(payload.user_id, payload.session_id, "user", payload.prompt, db)
        summary_text = (
            f"Workflow '{workflow_name}' dibuat dengan {len(task_graph)} langkah: "
            + ", ".join(s["display_name"] for s in task_graph)
        )
        await _save_turn(payload.user_id, payload.session_id, "assistant", summary_text, db)

    # 6. Format human-readable step list
    steps = [
        {"step": s["step"], "node": s["display_name"], "description": s["description"]}
        for s in task_graph
    ]

    return BuildWorkflowResponse(
        message=f"Workflow berhasil dibuat! Berisi {len(task_graph)} langkah.",
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        workflow_url=f"{settings.n8n_base_url}/workflow/{workflow_id}",
        steps=steps,
    )


# ─────────────────────────────────────────────────────────────────────────────
# AI AGENT WORKFLOW BUILDER
# Dibuat terpisah agar tidak mengganggu logika build_workflow() di atas.
# Dipanggil dari build_workflow() ketika prompt terdeteksi sebagai agent request.
# ─────────────────────────────────────────────────────────────────────────────

_AGENT_KEYWORDS = {
    "buatkan agent", "buat agent", "buatkan ai agent", "buat ai agent",
    "create agent", "build agent", "buatkan agen", "buat agen",
}

# Node default yang selalu dipakai untuk AI Agent — tidak bisa diubah user
_AGENT_FIXED = {
    "chat_model": {
        "node_type": "@n8n/n8n-nodes-langchain.lmChatMistikaAi",
        "display_name": "Mistika-AI Chat Model",
        "description": "LLM Mistika AI untuk AI Agent",
    },
    "memory": {
        "node_type": "@n8n/n8n-nodes-langchain.memoryBufferWindow",
        "display_name": "Simple Memory",
        "description": "Memori percakapan untuk AI Agent",
    },
}

AGENT_ANALYZER_PROMPT = """IMPORTANT: YOUR ENTIRE RESPONSE MUST BE VALID JSON ONLY.

You are an AI workflow component analyzer for n8n AI Agent workflows.

{trigger_summary}

Available TOOL nodes (choose tools the agent needs, can be multiple):
{tool_summary}

Available OUTPUT nodes (choose ONE or more for the final result):
{output_summary}

Rules:
- TRIGGER: Use EXACTLY the ★★ TRIGGER TERBAIK node shown above as the trigger field — copy the node_type exactly.
- TOOLS: what the AI agent can USE to accomplish tasks (API calls, databases, services)
- OUTPUT: what happens with the agent's result (send email, post to Slack, save to DB, etc.)
- If user mentions branching/conditions (if X then Y else Z), add if_node: true
- Use ONLY node types from the lists above

Output ONLY this JSON:
{{
  "summary": "one sentence what this agent workflow does",
  "trigger": {{
    "node_type": "exact_node_type",
    "display_name": "Trigger Name",
    "description": "what triggers this workflow"
  }},
  "tools": [
    {{
      "node_type": "exact_node_type",
      "display_name": "Tool Name",
      "description": "what this tool does in context of this workflow"
    }}
  ],
  "output": {{
    "node_type": "exact_node_type",
    "display_name": "Output Name",
    "description": "what to do with the agent result"
  }},
  "has_branch": false
}}"""


def is_agent_request(prompt: str) -> bool:
    """Cek apakah prompt meminta pembuatan AI Agent workflow."""
    lower = prompt.lower()
    return any(kw in lower for kw in _AGENT_KEYWORDS)


def _build_agent_workflow_json(
    name: str,
    trigger: dict,
    tools: list[dict],
    output: dict,
    has_branch: bool,
    mistika_credential: dict | None = None,
) -> dict:
    """
    Bangun n8n workflow JSON untuk AI Agent dengan koneksi yang benar.

    Struktur:
      Trigger → AI Agent → Output
      AI Agent ←── Mistika Chat Model  (ai_languageModel)
               ←── Simple Memory       (ai_memory)
               ←── Tool 1, Tool 2...   (ai_tool)
    """
    nodes = []
    connections: dict = {}

    # Posisi canvas
    X_TRIGGER  = 250
    X_AGENT    = 550
    X_OUTPUT   = 900
    Y_MAIN     = 300
    Y_SUB      = 540   # baris sub-node di bawah AI Agent
    X_SUBSTART = 350   # mulai dari kiri bawah AI Agent

    def _make_node(node_type: str, name_: str, desc: str, x: int, y: int, cred: dict | None = None) -> dict:
        n = {
            "id": str(uuid.uuid4()),
            "name": name_,
            "type": node_type,
            "typeVersion": NODE_VERSIONS.get(node_type, 1),
            "position": [x, y],
            "parameters": {},
            "credentials": {},
        }
        if cred and node_type in MISTIKA_AI_NODE_TYPES:
            n["credentials"] = {"mistikaAiApi": cred}
        return n

    # 1. Trigger node
    trigger_node = _make_node(trigger["node_type"], trigger["display_name"], trigger["description"], X_TRIGGER, Y_MAIN)
    nodes.append(trigger_node)

    # 2. AI Agent node
    agent_node = _make_node("@n8n/n8n-nodes-langchain.agent", "AI Agent", "AI Agent utama", X_AGENT, Y_MAIN, mistika_credential)
    nodes.append(agent_node)

    # Trigger → AI Agent (koneksi main)
    connections[trigger["display_name"]] = {
        "main": [[{"node": "AI Agent", "type": "main", "index": 0}]]
    }

    # 3. Sub-node: Mistika Chat Model (koneksi ai_languageModel)
    cm = _AGENT_FIXED["chat_model"]
    cm_node = _make_node(cm["node_type"], cm["display_name"], cm["description"], X_SUBSTART, Y_SUB, mistika_credential)
    nodes.append(cm_node)
    connections[cm["display_name"]] = {
        "ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]
    }

    # 4. Sub-node: Simple Memory (koneksi ai_memory)
    mem = _AGENT_FIXED["memory"]
    mem_node = _make_node(mem["node_type"], mem["display_name"], mem["description"], X_SUBSTART + 200, Y_SUB)
    nodes.append(mem_node)
    connections[mem["display_name"]] = {
        "ai_memory": [[{"node": "AI Agent", "type": "ai_memory", "index": 0}]]
    }

    # 5. Tool nodes (koneksi ai_tool)
    for i, tool in enumerate(tools):
        tool_node = _make_node(tool["node_type"], tool["display_name"], tool["description"], X_SUBSTART + 400 + i * 180, Y_SUB)
        nodes.append(tool_node)
        connections[tool["display_name"]] = {
            "ai_tool": [[{"node": "AI Agent", "type": "ai_tool", "index": 0}]]
        }

    # 6. Output node — dengan atau tanpa If branch
    if has_branch:
        # Sisipkan If node antara AI Agent dan Output
        if_node = _make_node("n8n-nodes-base.if", "Cek Kondisi", "Percabangan berdasarkan hasil agent", X_OUTPUT - 180, Y_MAIN)
        nodes.append(if_node)
        connections["AI Agent"] = {
            "main": [[{"node": "Cek Kondisi", "type": "main", "index": 0}]]
        }
        # True branch → Output
        out_node = _make_node(output["node_type"], output["display_name"], output["description"], X_OUTPUT + 50, Y_MAIN - 100)
        nodes.append(out_node)
        connections["Cek Kondisi"] = {
            "main": [
                [{"node": output["display_name"], "type": "main", "index": 0}],  # true
                [],  # false — kosong, user isi sendiri
            ]
        }
    else:
        # Langsung AI Agent → Output
        out_node = _make_node(output["node_type"], output["display_name"], output["description"], X_OUTPUT, Y_MAIN)
        nodes.append(out_node)
        connections["AI Agent"] = {
            "main": [[{"node": output["display_name"], "type": "main", "index": 0}]]
        }

    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "staticData": None,
    }


async def build_agent_workflow(
    prompt: str,
    user_id: str | None,
    session_id: str | None,
    db,
) -> BuildWorkflowResponse:
    """
    Bangun AI Agent workflow berdasarkan prompt user.
    Dipanggil dari build_workflow() ketika is_agent_request() = True.
    """
    from app.embedding_search import find_best_trigger, find_best_tools

    catalog = get_catalog()
    known_types = {n["node_type"] for n in catalog}

    # Cari trigger dan tools secara TERPISAH pakai category-aware + bilingual search
    best_triggers_raw = await find_best_trigger(prompt, top_k=6)
    # Deprioritize @n8n/n8n-nodes-langchain triggers (AI framework nodes, not service triggers).
    # Re-sort: n8n-nodes-base triggers first, langchain triggers last.
    best_triggers = sorted(
        best_triggers_raw,
        key=lambda t: (0 if t["node_type"].startswith("n8n-nodes-base.") else 1),
    )[:5]

    # Untuk agent: cari Tool nodes khusus (langchain tool) + output nodes
    agent_tool_prompt = f"{prompt} AI agent tool action capability"
    all_tools = await find_best_tools(agent_tool_prompt, top_k=18)

    # Pisah tool nodes vs output nodes berdasarkan tipe — httpRequest masuk output saja
    # (httpRequest sebagai ai_tool tidak didukung n8n, hanya sebagai action/output node)
    tool_nodes = [n for n in all_tools if n["node_type"].endswith("Tool")]
    output_nodes = [n for n in all_tools
                    if not n["node_type"].endswith("Trigger")
                    and not n["node_type"].endswith("Tool")
                    and "@n8n/n8n-nodes-langchain" not in n["node_type"]]

    # Fallback: pastikan minimal ada tool dan output
    if not tool_nodes:
        tool_nodes = [n for n in catalog if n["node_type"].endswith("Tool")][:6]
    if not output_nodes:
        output_nodes = [n for n in catalog
                        if not n["node_type"].endswith("Trigger")
                        and not n["node_type"].endswith("Tool")
                        and "@n8n/n8n-nodes-langchain" not in n["node_type"]][:6]

    def _fmt_tools(nodes: list[dict], limit: int = 8) -> str:
        return "\n".join(
            f"- {n['node_type']} ({n['display_name']}): {n.get('description', '')[:60]}"
            for n in nodes[:limit]
        )

    # Format trigger: pakai ★★ TRIGGER TERBAIK sama seperti regular workflow
    best_trigger_node = best_triggers[0] if best_triggers else None
    if best_trigger_node:
        trigger_summary_lines = [
            f"★★ TRIGGER TERBAIK (gunakan ini sebagai trigger, copy node_type PERSIS):",
            f"  {best_trigger_node['node_type']} ({best_trigger_node['display_name']}): "
            f"{best_trigger_node.get('description', '')[:80]}",
        ]
        if len(best_triggers) > 1:
            trigger_summary_lines.append("   Alternatif (hanya jika ★★ benar-benar tidak sesuai):")
            for t in best_triggers[1:3]:
                trigger_summary_lines.append(
                    f"  - {t['node_type']} ({t['display_name']}): {t.get('description', '')[:60]}"
                )
        trigger_summary = "\n".join(trigger_summary_lines)
    else:
        trigger_summary = _fmt_tools(best_triggers)

    system_prompt = AGENT_ANALYZER_PROMPT.format(
        trigger_summary=trigger_summary,
        tool_summary=_fmt_tools(tool_nodes),
        output_summary=_fmt_tools(output_nodes),
    )

    if user_id:
        cross_ctx = await get_cross_session_context(user_id, db)
        if cross_ctx:
            system_prompt = cross_ctx + "\n\n" + system_prompt

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]

    raw = await _call_mistika(messages, max_tokens=800)

    try:
        plan = json.loads(extract_json_from_response(raw))
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail=f"LLM returned non-JSON: {raw[:300]}")

    trigger = plan.get("trigger", {})
    tools   = plan.get("tools", [])
    output  = plan.get("output", {})
    has_branch = plan.get("has_branch", False)
    workflow_name = plan.get("summary", prompt)[:60]

    # Koreksi node_type menggunakan suffix_to_type + best_triggers fallback
    suffix_to_type: dict[str, str] = {nt.split(".")[-1].lower(): nt for nt in known_types}
    display_to_type: dict[str, str] = {n["display_name"].lower(): n["node_type"] for n in catalog}

    def _correct_node(component: dict, role: str) -> None:
        nt = component.get("node_type", "")
        if nt in known_types:
            return
        # Coba suffix match
        nt_lower = nt.lower()
        if nt_lower in suffix_to_type:
            component["node_type"] = suffix_to_type[nt_lower]
            return
        # Coba display_name match
        if component.get("display_name", "").lower() in display_to_type:
            component["node_type"] = display_to_type[component["display_name"].lower()]
            return
        # Fallback berdasarkan peran
        if role == "trigger" and best_trigger_node:
            component["node_type"] = best_trigger_node["node_type"]
            component["display_name"] = best_trigger_node["display_name"]
        elif role == "tool":
            component["node_type"] = "n8n-nodes-base.httpRequest"
            component["display_name"] = "HTTP Request"
        else:
            component["node_type"] = "n8n-nodes-base.set"
            component["display_name"] = "Set Output"

    _correct_node(trigger, "trigger")
    for t in tools:
        _correct_node(t, "tool")
    _correct_node(output, "output")

    mistika_credential = await _get_mistika_credential_id()
    workflow_json = _build_agent_workflow_json(
        workflow_name, trigger, tools, output, has_branch, mistika_credential
    )
    created = await _create_workflow_in_n8n(workflow_json)
    workflow_id = str(created.get("id", ""))

    if user_id:
        history_entry = WorkflowHistory(
            user_id=user_id,
            session_id=session_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            workflow_url=f"{settings.n8n_base_url}/workflow/{workflow_id}",
            steps=[trigger] + tools + [output],
            original_prompt=prompt,
        )
        db.add(history_entry)
        await db.commit()
        await _save_turn(user_id, session_id, "user", prompt, db)
        await _save_turn(user_id, session_id, "assistant",
                         f"AI Agent workflow '{workflow_name}' dibuat dengan {len(tools)} tool.", db)

    all_steps = [
        {"step": 1, "node": trigger["display_name"], "description": trigger.get("description", "")},
        {"step": 2, "node": "AI Agent", "description": "AI Agent dengan Mistika Chat Model + Simple Memory"},
        *[{"step": i+3, "node": t["display_name"], "description": t.get("description", "")} for i, t in enumerate(tools)],
        {"step": len(tools)+3, "node": output["display_name"], "description": output.get("description", "")},
    ]

    return BuildWorkflowResponse(
        message=f"AI Agent workflow berhasil dibuat! Trigger: {trigger['display_name']}, Tool: {len(tools)} node.",
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        workflow_url=f"{settings.n8n_base_url}/workflow/{workflow_id}",
        steps=all_steps,
    )
