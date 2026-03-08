import json
import os
from typing import Annotated

import ollama
from fastapi import APIRouter, WebSocket
from fastapi.params import Body
from starlette.responses import StreamingResponse, JSONResponse

from app.database.db import search_poi
from app.dependencies import NeedsDb, NeedsOllama
from app.AI.prompts import *


def json_serializable(data):
    """Recursively convert non-serializable objects (like Milvus/gRPC containers) to standard lists/dicts."""
    if isinstance(data, dict):
        return {k: json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [json_serializable(item) for item in data]
    elif hasattr(data, '__class__') and data.__class__.__name__ == 'RepeatedScalarContainer':
        return list(data)
    elif hasattr(data, 'tolist'): # Handle numpy arrays if they appear
        return data.tolist()
    return data

def generate_chat_response(model_name: str, messages: list, format: str = None) -> str:
    if model_name.lower().startswith("gemini"):
        from google import genai
        from google.genai import types
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            print("WARNING: GEMINI_API_KEY environment variable is not set!")
        client = genai.Client(api_key=api_key)
        
        system_instruction = next((msg["content"] for msg in messages if msg["role"] == "system"), None)
        gemini_history = []
        for msg in messages:
            if msg["role"] != "system":
                # Convert 'assistant' -> 'model', leaving 'user' alone
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [{"text": msg["content"]}]})
                
        config_args = {}
        if system_instruction:
            config_args["system_instruction"] = system_instruction
        if format == "json":
            config_args["response_mime_type"] = "application/json"
            
        response = client.models.generate_content(
            model=model_name,
            contents=gemini_history,
            config=types.GenerateContentConfig(**config_args) if config_args else None
        )
        return response.text
    else:
        # Fallback to Ollama
        import ollama
        kwargs = {
            "model": model_name,
            "messages": messages
        }
        if format:
            kwargs["format"] = format
        res = ollama.chat(**kwargs)
        return res["message"]["content"]

router = APIRouter()

@router.get("/ai/search", tags=["poi", "vector search"], dependencies=[NeedsOllama])
async def user_query_step_1(
        poi_query: str
) -> StreamingResponse:
    retrieved_knowledge = search_poi(poi_query, 5, ["label", "tags", "pos", "description"])


    model = os.environ.get("AI_MODEL", "qwen2.5:3b")

    async def response():
        if model.lower().startswith("gemini"):
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
            
            res = client.models.generate_content_stream(
                model=model,
                contents=[{"role": "user", "parts": [{"text": poi_query}]}],
                config=types.GenerateContentConfig(
                    system_instruction=instruction_prompt(retrieved_knowledge)
                )
            )
            for chunk in res:
                yield chunk.text
        else:
            stream = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": instruction_prompt(retrieved_knowledge)},
                    {"role": "user", "content": poi_query}
                ],
                stream=True
            )
            for chunk in stream:
                yield chunk["message"]["content"]

    return StreamingResponse(response())

@router.get("/ai/triage_agent", tags=["poi", "ai", "triage_agent"], dependencies=[NeedsOllama])
def triage_agent(
        user_query: str,
        context: dict = None,
        history: list = None
) -> dict:
    model = os.environ.get("AI_MODEL")

    # Construct a systematic prompt
    full_prompt = ""
    if history:
        full_prompt += "[CONVERSATION HISTORY]\n"
        for turn in history:
            full_prompt += f"User: {turn['user']}\nAI: {turn['ai']}\n"
        full_prompt += "\n"

    if context:
        pos = context.get("position", [0, 0, 0])
        rot = context.get("rotation", [0, 0, 0])
        scene = context.get("scene", "Unknown")
        full_prompt += f"[USER CONTEXT] Position: {pos}, Rotation: {rot}, Scene: {scene}\n"

    full_prompt += f"[USER QUERY] {user_query}"

    # STAGE 1: Triage
    print(f"\n--- [STAGE 1: TRIAGE] ---")
    print(f"Prompt sent to LLM:\n{full_prompt}")

    content = ""
    try:
        content = generate_chat_response(
            model_name=model,
            messages=[
                {"role": "system", "content": triage_agent_prompt()},
                {"role": "user", "content": full_prompt}
            ],
            format="json"
        )
        print(f"LLM Raw Output: {content}")

        # Try to parse the JSON output from the LLM
        # LLM might wrap JSON in backticks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)

        # Identify mixed intents from the actions array
        intents = set()
        for action in data.get("actions", []):
            if isinstance(action, dict) and "cmd" in action:
                intents.add(action["cmd"])
        if not intents and data.get("type"):
            intents.add(data.get("type"))

        print(f"Parsed Intents: {intents}")

        all_candidates_for_rag = []

        # 1. Handle Navigation: Already searching, but let's ensure it's robust
        # Expected 'targets' structure from LLM for navigation or inquiry types:
        # - targets: An array of objects to search for (for navigation or inquiry types). Each target must have:
        #   - target_type: "specific" (e.g. Room 1110, The Lab) or "generic" (e.g. restroom, exit, coffee).
        #   - semantics: A comma-separated list of synonyms and related terms to expand the search. Put the specific predicted name here.
        #   - filter: A Milvus-style SQL filter if applicable. Valid fields: name, poiName, parentName, type.
        #       - For specific names or room numbers, use LIKE with '%' wildcards (e.g. name LIKE 'Room 1110%' or poiName LIKE '%Reception%').
        #       - For broad categories, use == (e.g. type == 'Toilet' or type == 'Restroom').
        if "navigation" in intents and "targets" in data:
            for target in data["targets"]:
                semantics = target.get("semantics", "")
                if semantics:
                    # STAGE 2: Search (Navigation)
                    print(f"\n--- [STAGE 2: SEARCH (NAV)] ---")
                    search_filter = target.get("filter", "")
                    target_type = target.get("target_type", "generic")

                    fetch_count = 5 # Fetch enough candidates for the AI to pick from

                    print(f"Searching for semantics: {semantics}. Type: {target_type}. Filter: {search_filter}")
                    try:
                        raw_results = search_poi(
                            semantics,
                            fetch_count,
                            ["id", "name", "poiName", "description", "type", "position"],
                            filter_expression=search_filter
                        )
                        if not raw_results and search_filter:
                            print("Filter returned 0 results, retrying without filter.")
                            raw_results = search_poi(
                                semantics,
                                fetch_count,
                                ["id", "name", "poiName", "description", "type", "position"]
                            )
                    except Exception as filter_err:
                        print(f"Filter failed, retrying without filter: {filter_err}")
                        raw_results = search_poi(
                            semantics,
                            fetch_count,
                            ["id", "name", "poiName", "description", "type", "position"]
                        )

                    # --- AI Reranking / Validation ---
                    if raw_results:
                        print("\n--- [STAGE 2.5: AI SELECTION] ---")
                        candidate_strings = []
                        for res in raw_results:
                            item = res[0]
                            candidate_strings.append(f"ID: {item.get('id')} | Name: {item.get('name')} | Local Name: {item.get('poiName')} | Type: {item.get('type')}")
                        candidate_text = "\n".join(candidate_strings)

                        sys_prompt = f"""You are a STRICT JSON spatial filter API. The user requested to navigate: "{user_query}"
The target location they are looking for is: "{semantics}"
Target Type: {target_type.upper()}

Here are the top candidates retrieved from the building database:
{candidate_text}

TASK:"""
                        if target_type == "specific":
                            sys_prompt += """
This is a SPECIFIC target request. You must find the exact or logically equivalent match for the queried location from the candidates.
Evaluate fuzzy names (e.g., 'Reception' matches 'Room 3138/Reception').
CRITICAL INSTRUCTION: If none of the candidates are an exact logical match (e.g. if they asked for 'Room 2000' and the candidates are 'Room 3210' or 'Room 2010' - those are DIFFERENT rooms!), you MUST return an EMPTY array [].
Do NOT return a "close enough" room number or a physically nearby location. You must strictly return [] if the exact specific place requested is missing!
DO NOT ATTEMPT TO GUESS OR APPROXIMATE. If the EXACT room number or specific name is not explicitly in the candidate list, you MUST strictly return [] !"""
                        else:
                            sys_prompt += """
This is a GENERIC target request (e.g., they asked for 'nearest restroom', 'coffee', etc.).
Return ALL relevant IDs from the candidates that semantically match this category so the engine can calculate the physically closest one in the next step."""

                        sys_prompt += """
OUTPUT FORMAT:
You MUST reply ONLY with a minified JSON object containing strictly the key "selected_ids". Do NOT add any other keys!
Example 1: { "selected_ids": [53] }
Example 2: { "selected_ids": [12, 14, 15] }
Example 3: { "selected_ids": [] }"""

                        try:
                            val_content = generate_chat_response(
                                model_name=model,
                                messages=[
                                    {"role": "system", "content": sys_prompt},
                                    {"role": "user", "content": "Analyze the candidates and return the selected_ids JSON."}
                                ],
                                format="json"
                            )
                            # Fallback if backticks apply
                            if "```json" in val_content:
                                val_content = val_content.split("```json")[1].split("```")[0].strip()
                            elif "```" in val_content:
                                val_content = val_content.split("```")[1].split("```")[0].strip()

                            val_data = json.loads(val_content)
                            print(f"AI Selected IDs: {val_data}")

                            # Robustly extract selected_ids, protecting against hallucinations
                            if isinstance(val_data, dict) and "selected_ids" in val_data:
                                valid_ids = val_data["selected_ids"]
                            elif isinstance(val_data, list):
                                valid_ids = val_data
                            else:
                                if target.get("target_type") == "specific":
                                    valid_ids = []
                                    print(f"Warning: STAGE 2.5 AI Hallucinated response or failed to emit 'selected_ids'. Assuming empty match for specific target.")
                                else:
                                    valid_ids = None
                                    print(f"Warning: STAGE 2.5 AI Hallucinated response or failed to emit 'selected_ids'. Bypassing filter.")

                            if valid_ids is not None and len(valid_ids) == 0:
                                if target.get("target_type") == "specific":
                                    # Explicitly empty list for a specific target means "Target Doesn't Exist"
                                    raw_results = []
                                else:
                                    # Explicitly empty list for a generic target means no valid candidates were found by the AI
                                    raw_results = []
                            elif valid_ids:
                                try:
                                    valid_ids = [int(v) for v in valid_ids]
                                    raw_results = [r for r in raw_results if r[0].get("id") in valid_ids]
                                except Exception:
                                    pass # Ignore conversion error; filter fails
                        except Exception as e:
                            print(f"AI selection failed, returning empty. Error: {e}")
                            raw_results = []

                    # If this target is completely missing, and it's either specific OR there are absolutely no other valid targets remaining, we should tell the user!
                    if not raw_results:
                        print(f"Aborting query: Target '{semantics}' could not be found.")

                        # Only abort immediately if this is specific OR if this was the only target we had.
                        # (If they asked for 'Room 1' and 'food', and 'food' is missing, we still want to route them to Room 1.
                        # But if 'food' was the ONLY target and it's missing, we must apologize and abort).
                        if target.get("target_type") == "specific" or len(data["targets"]) == 1:
                            try:
                                msg_prompt = f"The user asked using this query: '{user_query}'. However, the location '{semantics}' does not exist or couldn't be found in our building database. Write a short, natural, and helpful response politely informing them of this, and ask if they want to double-check or navigate somewhere else instead. Consider the conversation history if any to make the response sound natural in context. Do not use quotes around your response."
                                error_msg = generate_chat_response(
                                    model_name=model,
                                    messages=[
                                        {"role": "system", "content": f"You are a helpful building navigation assistant. Use the conversation history below for context if needed.\n\n{full_prompt}"},
                                        {"role": "user", "content": msg_prompt}
                                    ]
                                ).strip('\"')
                            except Exception:
                                error_msg = f"I couldn't find '{semantics}' in the building. Could you please double-check or clarify?"

                            return {
                                "type": data.get("type", "navigation"),
                                "response": error_msg,
                                "targets": [],
                                "actions": []
                            }

                    # Return only 'id' and 'name' to Unity as requested, securely
                    target["poi_results"] = [{"id": res[0].get("id", 0), "name": res[0].get("name", "Unknown")} for res in raw_results]
                    print(f"Found {len(target['poi_results'])} POI results for this target.")
                    all_candidates_for_rag.extend(raw_results)

        # 2. Handle Inquiry: Use RAG to provide a grounded response
        if "inquiry" in intents:
            # STAGE 2: Search (Inquiry)
            print(f"\n--- [STAGE 2: SEARCH (INQ)] ---")

            # Use expanded semantics from targets if available, otherwise fallback to query
            search_term = user_query
            search_filter = data.get("filter", "")

            if "targets" in data and len(data["targets"]) > 0:
                search_term = data["targets"][0].get("semantics", user_query)
                search_filter = data["targets"][0].get("filter", search_filter)

            if all_candidates_for_rag:
                print("Reusing candidates from Navigation block for RAG Context.")
                retrieved_knowledge = all_candidates_for_rag
            else:
                print(f"Searching database for grounding context. Search Term: {search_term}. Filter: {search_filter}")
                try:
                    retrieved_knowledge = search_poi(
                        search_term,
                        10,  # Raise top_n for inquiry to capture more candidates
                        ["id", "name", "poiName", "description", "type", "position", "parentName"],
                        filter_expression=search_filter
                    )
                    if not retrieved_knowledge and search_filter:
                        print("Filter returned 0 results, retrying without filter.")
                        retrieved_knowledge = search_poi(
                            search_term,
                            10,
                            ["id", "name", "poiName", "description", "type", "position", "parentName"]
                        )
                except Exception as filter_err:
                    print(f"Filter failed, retrying without filter: {filter_err}")
                    retrieved_knowledge = search_poi(
                        search_term,
                        10,
                        ["id", "name", "poiName", "description", "type", "position", "parentName"]
                    )
                print(f"Retrieved {len(retrieved_knowledge)} context items.")

            # Formulate a context-aware response using the second prompt style
            if retrieved_knowledge:
                # STAGE 3: Inference (RAG)
                print(f"\n--- [STAGE 3: INFERENCE (RAG)] ---")
                knowledge_strings = []
                for entity, dist in retrieved_knowledge:
                    knowledge_strings.append(
                        f"Name: {entity.get('name')} | "
                        f"Type: {entity.get('type')} | "
                        f"Local Name: {entity.get('poiName')} | "
                        f"Location (X,Y,Z): {entity.get('position')} | "
                        f"Parent Area: {entity.get('parentName')} | "
                        f"Description: {entity.get('description')}"
                    )

                knowledge_text = "\n".join(knowledge_strings)

                system_prompt_content = f"""
You are a helpful building assistant. Using ONLY the information provided below, describe the requested location(s) or answer the question.
You may reference the Location (X,Y,Z) to describe where something is in the building (e.g. 'on the east wing').  
Simply describe all matched locations accurately. Use the conversation history provided to understand the context of the user's question, if applicable.

[BUILDING DATA]
{knowledge_text}
"""
                data["response"] = generate_chat_response(
                    model_name=model,
                    messages=[
                        {"role": "system", "content": f"{system_prompt_content}\n\n{full_prompt}"},
                        {"role": "user", "content": user_query}
                    ]
                )

                # If this is purely an inquiry, we do not want Unity to construct NavMesh routes.
                # We clear the targets so it skips STAGE 5 entirely and immediately displays this RAG response.
                if "targets" in data and "navigation" not in intents:
                    data["targets"] = []

                # Return only 'id' and 'name' for the context used
                data["context_used"] = [{"id": res[0]["id"], "name": res[0]["name"]} for res in retrieved_knowledge]
                print(f"Generated RAG Response: {data['response']}")
            else:
                data["response"] = "I'm sorry, I couldn't find any information about that in our database."

        # 3. Handle Greeting / Others: Generate a direct conversational response
        if ("greeting" in intents or "others" in intents) and not data.get("response"):
            print(f"\n--- [STAGE 2: CONVERSATION ({data.get('type').upper()})] ---")
            system_prompt_content = "You are a friendly, helpful building assistant in a 3D environment. Respond naturally and concisely to the user's greeting or casual conversation."
            data["response"] = generate_chat_response(
                model_name=model,
                messages=[
                    {"role": "system", "content": system_prompt_content},
                    {"role": "user", "content": user_query}
                ]
            )
            print(f"Generated Chat Response: {data['response']}")

        # STAGE 4: Return
        final_data = json_serializable(data)
        print(f"\n--- [STAGE 4: SERIALIZED RETURN] ---")

        # Pretty-print the response to the python terminal for debugging
        json_output = json.dumps(final_data, indent=2)
        print(f"Payload ready for Unity ({len(json_output)} chars):\n{json_output}")

        return final_data
    except Exception as e:
        import logging
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"Failed to parse or process triage_agent response:\n{error_details}\nContent: {content}")
        # Print directly to stdout so it shows up in dev servers
        print(f"FATAL TRIAGE ERROR:\n{error_details}")
        return {"type": "error", "message": "Failed to process query", "raw_content": content, "traceback": error_details}


def verify_route_agent(
    user_query: str,
    distances_payload: dict,
    context: dict = None,
    history: list = None
) -> dict:
    """Verifies the physical distances against the semantic meaning to pick the best overall POI and generate a realization."""
    model = os.environ.get("AI_MODEL")
    print(f"\n--- [STAGE 5: ROUTE VERIFICATION] ---")
    
    # We expect distances_payload to have 'targets' array with POIs and 'distance'
    original_type = distances_payload.get("original_type", "navigation")
    
    prompt = f"[USER QUERY] {user_query}\n\n[CALCULATED DISTANCES FROM UNITY]\n"
    import json
    prompt += json.dumps(distances_payload.get("targets", []), indent=2)
    
    system_prompt_content = verify_route_agent_prompt(original_type)

    try:
        content = generate_chat_response(
            model_name=model,
            messages=[
                {"role": "system", "content": system_prompt_content},
                {"role": "user", "content": prompt}
            ],
            format="json"
        )
        
        print(f"LLM Verification Raw Output: {content}")
        
        if not content or not content.strip():
            print("Warning: LLM returned an empty string for verification.")
            return {"type": "error", "message": "Backend AI returned empty verification response.", "actions": []}
            
        # LLM might wrap JSON in backticks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        # Fallback to ast literal eval if strict json fails (because LLMs sometimes emit single quotes)
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            import ast
            print("Warning: Strict JSON failed, attempting AST evaluation.")
            data = ast.literal_eval(content)
        
        selected_ids = data.get("selected_ids", [])
        # Provide fallback if AI still returns selected_id
        if "selected_id" in data and not selected_ids:
            selected_ids = [data["selected_id"]]
            
        actions = []
        for pid in selected_ids:
            actions.append({"cmd": original_type, "id": pid})
        
        # Package for unity
        final_data = {
            "type": original_type,
            "response": data.get("response", ""),
            "actions": actions
        }
        
        # Echo print
        json_output = json.dumps(final_data, indent=2)
        print(f"Verified Final Choice ({len(json_output)} chars):\n{json_output}")
        
        return final_data
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"FATAL VERIFICATION ERROR:\n{error_details}")
        return {"type": "error", "message": "Failed to verify route", "raw_content": "", "traceback": error_details}
