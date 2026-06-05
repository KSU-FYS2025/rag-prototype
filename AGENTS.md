# AGENTS.md: RAG Prototype Development Guide

## Project Overview
This is a **Retrieval Augmented Generation (RAG) backend** for a 3D AR navigation system connecting Unity to AI-powered location search. It combines local LLMs (Ollama), vector embeddings (Milvus), and multi-agent workflows (Google ADK) to understand user navigation/information queries about building Points of Interest (POIs).

## Architecture: Core Data Flow

**Query Pipeline** (from Unity to response):
```
WebSocket /ws/AI → Triage Agent (classify intent) → Search Agent (vector search on POI DB) 
→ Context Reranking (validate candidates) → RAG Response → Verification Agent (physical distance) 
→ Return {type, response, targets[], actions[]} to Unity
```

**Key Components:**
- `app/AI/full_agent/`: Multi-agent orchestration using Google ADK workflows
  - `root_agent`: Entry point (Gemini 2.5-flash)
  - `triage_agent`: Intent classification (navigation/inquiry/greeting/clarification)
  - `search_agent`: Vector search + distance calculation between POIs
  - `synthesis_agent`: Path planning from search results
- `app/database/db.py`: Milvus vector DB client + embedding function
- `app/websockets/api.py`: WebSocket endpoints for Unity communication
- `app/poi/models.py`: POI schema (aligned with Unity POIData structure)

## Critical Workflow Pattern: 3+1 Stage Processing

**STAGE 1 (Triage):** LLM classifies user query intent and extracts search terms
- Input: User query + conversation history + user context (position/rotation)
- Output: Structured JSON with `targets[]` array (multiple if multi-destination)
  - Each target has: `target_type` (specific/generic), `semantics` (search terms), `filter` (Milvus SQL filter)
- **Key rule:** Specific targets must match EXACTLY (e.g., "Room 2000" != "Room 2010"). Generic targets are flexible.

**STAGE 2 (Search & Reranking):** Vector search → AI validation of candidates
- Calls `search_poi()` which embeds query and finds k-nearest POIs
- **Fallback strategy:** If filter returns 0 results, retry without filter
- STAGE 2.5: AI reranker validates if candidates semantically match semantic target
  - For specific targets: Returns empty [] if exact match not found (critical for navigation!)
  - For generic targets: Returns all matching semantic candidates for distance calculation

**STAGE 3 (Inference):** Generate natural language response using RAG context
- Formats retrieved POI data into knowledge text
- LLM synthesizes response using system prompt + knowledge + conversation history

**STAGE 4 (Verification):** If navigation query, Unity calculates distances → backend selects best POI
- Weights semantic match vs physical distance
- Returns final action: `{"cmd": "navigation", "id": poi_id}`

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

### Response Structure (from /ws/AI or triage_agent)
```python
{
    "type": "navigation|inquiry|greeting|clarification|error",
    "response": "Natural language response",
    "targets": [{                          # Only populated for nav/inquiry
        "target_type": "specific|generic",
        "semantics": "search terms",
        "filter": "Milvus SQL filter",
        "poi_results": [{"id": int, "name": str}]  # Results after Stage 2
    }],
    "actions": [{"cmd": "navigation|inquiry", "id": poi_id}],
    "context_used": [{"id": int, "name": str}]    # For RAG transparency
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

### Debugging Tips
- Check `/ping` endpoint to verify server is running
- WebSocket `/ws/AI` logs all stages: [STAGE 1: TRIAGE], [STAGE 2: SEARCH], [STAGE 3: INFERENCE], [STAGE 4: SERIALIZED_RETURN]
- Print full LLM input/output in logs (already done in triage_agent function)
- Verify POI JSON is loading: Check lifespan logs on startup
- Test vector search: GET `/poi/all` or MCP tool `search_poi(query, top_n=5)`

### Adding New Agents or Routes
1. **New AI route:** Add to `app/AI/api.py`, decorate with `@router.get()`, use `generate_chat_response()` helper
2. **New WebSocket endpoint:** Extend `app/websockets/api.py`, follow `Triage` class pattern (on_connect, on_receive, on_disconnect)
3. **New ADK workflow:** Create agent in `full_agent/<agent_name>/agent.py`, wire into workflow edges
4. **Database queries:** Always use `get_db_gen()` context manager, never globals (thread-safety)

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

- **Entry point:** `app/main.py` (FastAPI lifespan, POI DB initialization)
- **Primary API logic:** `app/AI/api.py` (triage_agent function is 500+ lines but well-structured)
- **Prompts:** `app/AI/prompts.py` (system instructions that guide LLM behavior—edit for tuning)
- **Vector DB client:** `app/database/db.py` (search_poi, embedding_fn, context managers)
- **POI schema:** `app/poi/models.py` (defines all Milvus fields and validation)
- **Configuration:** `pyproject.toml` (dependencies), `Dockerfile` (containerization), `docker-compose.yml` (services)

