# AGENTS.md: RAG Prototype Development Guide

## Project Overview
This is a **Retrieval Augmented Generation (RAG) backend** for a 3D AR navigation system connecting Unity to AI-powered location search. It combines local LLMs (Ollama), vector embeddings (Milvus), and multi-agent workflows (Google ADK) to understand user navigation/information queries about building Points of Interest (POIs).

## Architecture: Core Data Flow

**Query Pipeline** (from Unity to response):
```
WebSocket /ws/AI → Root Agent (classify intent) → Triage Agent (extract targets) 
→ Search Workflow (parallel: vector search + distance + path planning) 
→ Response sent to Unity
Optional: POST for distance verification → verify_route_agent (final weighting)
```

**Key Components:**
- `app/AI/full_agent/`: Multi-agent orchestration using Google ADK Workflows
  - `root_agent` (`full_agent/root_agent/agent.py`): Entry point classifier (Gemini 2.5-flash) — determines intent (navigation_guidance/navigation_query/conversational)
  - `triage_agent` (`full_agent/triage_agent/agent.py`): LLM agent extracting `targets[]` with semantics + filters
  - `search_agent` (`full_agent/search_agent/agent.py`): Workflow with parallel target processing:
    - `parallel_router`: Routes each target through parallel search pipelines using JoinNode
    - `search_poi_node`: Vector DB search per target
    - `validate_pois`: Converts results to POI objects
    - `distance_calculator`: Inter-POI distances and semantic rankings
    - `synthesis_agent`: LLM agent for multi-POI path planning
  - `full_workflow`: Linear orchestration (START → root_agent → triage_agent → search_workflow)
- `app/AI/api.py`: Flask-style route `triage_agent()` wrapping the workflow for WebSocket
- `app/database/db.py`: Milvus vector DB client + embedding function
- `app/websockets/api.py`: WebSocket `/ws/AI` (Triage handler) + `/ws/sync` (POI sync) + optional `verify_route_agent` post-verification
- `app/poi/models.py`: POI schema (aligned with Unity POIData structure)

## Critical Workflow Pattern: Multi-Agent ADK Workflow

**Full Workflow (Google ADK Workflow)** with 5 processing stages:

**STAGE 0 (Root Classification):** Root agent classifies user intent
- Input: User query + conversation history
- Output: Intent classification (navigation_guidance/navigation_query/conversational)
- Only continues to triage if intent requires search

**STAGE 1 (Triage):** Triage agent extracts and structures search targets
- Input: User query + optional intent context
- Output: `TriageAgentOutput` with `targets[]` array (multiple targets if multi-destination query)
  - Each target: `order` (position), `intent`, `target_type` (specific/generic), `semantics` (search terms), `filter` (Milvus SQL filter)
- **Key rule:** Specific targets must match EXACTLY (e.g., "Room 2000" != "Room 2010"). Generic targets are flexible.

**STAGE 2 (Parallel Search & Validation):** Search workflow processes targets in parallel via JoinNode
- Each target runs through its own pipeline:
  1. `search_poi_node`: Vector search with filter fallback (retries without filter if 0 results)
  2. `validate_pois`: Converts raw search results to POI objects
  3. Distance calculations between POIs
- Joins all target results using `JoinNode` before moving to synthesis

**STAGE 3 (Synthesis):** synthesis_agent generates multi-POI path plan
- Input: All POI candidates with inter-POI distances
- Output: `SearchOutput` with `validations[]` (one per target) containing selected POI candidates
- **Critical for specific targets:** Returns empty `selected_ids[]` if exact match not found (stops navigation)

**Optional STAGE 4 (Route Verification):** Post-flight distance verification via WebSocket
- Only triggered when Unity sends `{"type": "verification", ...}` payload with calculated distances
- `verify_route_agent()` in `app/AI/api.py` weights semantic match vs physical distances
- Returns final selected POI for navigation action

## Essential Data Structures

### POI Model (app/poi/models.py)
```python
# Aligned strictly with Unity's POIData from POIExtractor.cs
id: int                    # Unique identifier (primary key in Milvus)
name: str                  # Full name
poiName: str              # Short name (often same as title)
title: str                # Brief description
description: str         # Longer description
type: str                 # Category: "Room", "Restroom", etc.
parentName: str          # Hierarchical location (e.g., "Floor 3")
position: [float, float, float]        # World coordinates [x, y, z]
localPosition: [float, float, float]  # Local object coordinates
rotation, localRotation: [float, float, float]  # Euler angles [x, y, z]
vector: list[float]      # 768-dim embedding
```

### Vector Embedding Strategy
- Text constructed from: `f"The {type} named '{poiName}' ... titled '{title}'. ... {description} within {parentName}"`
- Uses pymilvus `DefaultEmbeddingFunction` (768-dim model)
- Generated at: (1) JSON import in FastAPI lifespan, (2) WebSocket sync endpoint

### Response Structure (from /ws/AI endpoint or triage_agent function)
```python
{
    "type": "navigation_guidance|navigation_query|conversational|error",  # From root_agent classification
    "response": "Natural language response",                             # From synthesis_agent or LLM
    "targets": [{                                                        # Only populated for nav intents
        "order": int,                                                    # Position in multi-target queries
        "target_type": "specific|generic",
        "semantics": "search terms",
        "filter": "Milvus SQL filter",
        "poi_results": [{"id": int, "name": str, "distance": float}]   # After Stage 2 search
    }],
    "actions": [{"cmd": "navigation", "id": poi_id}],                   # When specific match found
    "context_used": [{"id": int, "name": str}]                          # For RAG transparency
}
```

## Project-Specific Conventions

### Environment Configuration (.env required)
```
AI_MODEL=deepseek-r1:8b          # Or gemini-* for Google models
POI_JSON_PATH=<scene_name>.json  # Exported from Unity POITools
DB_URL=database.db               # Milvus database path
GEMINI_API_KEY=<key>            # Only if using Gemini models
```

### LLM Response Parsing
- LLMs sometimes wrap JSON in backticks: `json ... ``` → strip before `json.loads()`
- Fallback to `ast.literal_eval()` if JSON parsing fails (LLMs emit single quotes sometimes)
- **Always wrap format="json" requests in try/except** with sensible defaults

### Milvus Search Filtering
- Filter expressions use SQL-like syntax (see: https://milvus.io/docs/boolean.md)
- Valid fields: name, poiName, type, parentName (all VARCHAR)
- Examples: `name LIKE 'Room 1110%'`, `type == 'Restroom'`
- If filter fails or returns 0 results: **Always retry without filter** (graceful degradation)

### Error Handling Patterns
1. **Search returns 0 results**: Generate natural language error explaining location not found
2. **Specific target missing from candidates**: Return `selected_ids: []` (reject)
3. **Generic target missing**: Still return other valid targets (service partial requests)
4. **LLM hallucination risk**: Validate LLM output against constraints (selected_ids must be integers in candidate list)

## Development Workflows

### Running Locally
```bash
# Setup dependencies with UV
uv sync

# Start in terminal 1: Ollama (for local LLMs)
ollama serve  # Models must already be pulled: ollama pull deepseek-r1:8b

# Terminal 2: FastAPI server
uv run fastapi run  # Auto-reloads on code changes

# Terminal 3 (optional): Test WebSocket
# Use WebSocket client to ws://localhost:8000/ws/AI with JSON: {"query": "..."}
```

### Running with Docker
```bash
docker compose up  # Starts FastAPI on 8000 with Ollama at host.docker.internal:11434
```

### Testing
```bash
pytest  # Uses TestClient + async fixtures
# Key tests: test_fastapi_server, test_ollama, test_milvus (vector search)
```

### Google ADK Workflow Execution
- Workflows are defined using `google.adk` and use Agents (LLM-backed) and Nodes (computation/I/O)
- Each Agent specifies `output_schema` (Pydantic model) for structured outputs
- Workflow edges defined as: `("START", agent1, agent2, ..., agent_n)` or `(node1, node2)` for workflows
- JoinNode used in `search_agent` to parallelize per-target search pipelines
- Context passed through Events between nodes/agents: `Event(output=...)`
- **Important:** Agents use Gemini 2.5-flash by default; local Ollama models require custom adapter (not implemented)

### Debugging Tips
- Check `/ping` endpoint to verify server is running
- WebSocket `/ws/AI` receives queries and calls `triage_agent()` function which orchestrates the full workflow
  - Logs include agent outputs at each stage (check console for Agent execution details)
  - Connection stores conversation history (last 5 turns)
- Optional distance verification: POST to same `/ws/AI` endpoint with `{"type": "verification", "targets": [...], ...}` to trigger `verify_route_agent()`
- Print full LLM input/output in logs (LLMs: Ollama for local models, Gemini API for cloud)
- Verify POI JSON is loading: Check startup logs for embedding function initialization
- Test vector search directly: Call `search_poi()` from MCP tools or access `/poi/all` endpoint
- Parallel search processing: Check that all targets are being routed through the JoinNode correctly by inspecting WorkflowContext logs

### Adding New Agents or Routes
1. **New AI HTTP route:** Add function to `app/AI/api.py`, decorate with `@router.get()`, use `generate_chat_response()` helper
2. **New WebSocket endpoint:** Extend `app/websockets/api.py`, subclass `WebSocketEndpoint` following `Triage` class pattern (on_connect, on_receive, on_disconnect)
3. **New ADK agent:** 
   - Create `full_agent/<new_agent_name>/agent.py` with `Agent()` from `google.adk.agents.llm_agent`
   - Define corresponding schema in `full_agent/<new_agent_name>/schema.py`
   - Wire into `full_workflow.edges` in `full_agent/agent.py` or create sub-workflow
4. **New workflow nodes:** Use `@node` decorator from `google.adk.workflow` with `async def`, return `Event(output=...)` 
5. **Database queries:** Always use `get_db_gen()` context manager, never globals (thread-safety)

## Common Pitfalls & Solutions

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| "Ollama is not running" 500 error | Ollama server down or wrong port | `requests.get("http://localhost:11434")` should return "Ollama is running" |
| Model not found error | Model not installed in Ollama | `ollama list` to see installed; `ollama pull <model>` to install |
| 0 results in vector search | Filter too restrictive or POI doesn't exist | Retry without filter; check POI JSON is loaded in Milvus |
| "AttributeError: RepeatedScalarContainer" when serializing | Milvus returns gRPC container objects | Use `json_serializable()` helper in api.py before returning |
| WebSocket connection drops | Connection timeout or large response | Keep responses under typical WebSocket frame size; implement heartbeat if needed |
| Same POI returned for different queries | Embedding model not discriminative enough | Verify descriptive text construction; consider reembedding with better model |

## Key Files to Know

- **Workflow orchestration:** 
  - `app/AI/full_agent/agent.py` (full_workflow definition with root → triage → search edges)
  - `app/AI/full_agent/root_agent/agent.py` (entry classifier Agent)
  - `app/AI/full_agent/triage_agent/agent.py` (target extraction Agent)
  - `app/AI/full_agent/search_agent/agent.py` (parallel search Workflow + synthesis Agent)
- **WebSocket entry point:** `app/websockets/api.py` (Triage handler routes to `triage_agent()`)
- **HTTP wrapper:** `app/AI/api.py` (triage_agent function + verify_route_agent, wraps workflows)
- **Prompts & LLM behavior:** `app/AI/prompts.py` (system instructions—edit to tune agent behavior)
- **FastAPI setup:** `app/main.py` (lifespan hooks for POI DB initialization)
- **Vector DB client:** `app/database/db.py` (search_poi, EmbeddingFn, context managers)
- **POI data model:** `app/poi/models.py` (Milvus schema + Unity alignment)
- **Configuration:** `pyproject.toml` (dependencies), `Dockerfile`, `docker-compose.yml`
