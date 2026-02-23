# Walkthrough - rag-prototype (FastAPI Branch)

I have explored the `app/` directory of the `rag-prototype` project. Below is a detailed breakdown of the application structure and its core functionality.

## Application Overview
The project is a FastAPI-based server designed to assist with indoor navigation using RAG (Retrieval-Augmented Generation) and vector-based search.

## Directory Structure

### `app/poi/` - Point of Interest Management
- **[api.py](file:///Users/yzhao20/Documents/GitHub/rag-prototype/app/poi/api.py)**: Provides CRUD endpoints for managing POIs in the Milvus vector database.
- **[models.py](file:///Users/yzhao20/Documents/GitHub/rag-prototype/app/poi/models.py)**: Defines the `POI` data model, including spatial coordinates (`pos`), metadata (`name`, `description`, `type`), and the vector embedding.

### `app/AI/` - RAG & Logic
- **[api.py](file:///Users/yzhao20/Documents/GitHub/rag-prototype/app/AI/api.py)**: Contains the core RAG logic.
    - `/ai/search`: Performs a vector search for POIs and uses Ollama to generate a helpful response for the user.
    - `/ai/triage_agent`: Analyzes user queries to determine if they are related to navigation, inquiries, or greetings.
- **[extras.py](file:///Users/yzhao20/Documents/GitHub/rag-prototype/app/AI/extras.py)**: Defines the system prompts and personas for the assistant and triage agent.

### `app/database/` - Vector Search
- **[db.py](file:///Users/yzhao20/Documents/GitHub/rag-prototype/app/database/db.py)**: Utilities for connecting to Milvus, creating collections, and performing vector searches using the `DefaultEmbeddingFunction`.

### `app/websockets/` - Real-time Features
- **[api.py](file:///Users/yzhao20/Documents/GitHub/rag-prototype/app/websockets/api.py)**:
    - `/ws/AI`: A WebSocket endpoint for real-time triage interaction.
    - `/ws/sync`: A batch upload utility that accepts POI data over a persistent connection and syncs it to the database upon completion.

## Key Functionality
1. **Vector-Based Navigation**: The system uses Milvus to store and search for POIs based on their semantic descriptions.
2. **Modular RAG Chain**: It integrates `ollama` for LLM generation, guided by strict system prompts to prevent hallucinations about the building's layout.
3. **Unity Integration**: The `POI` model and data structure are explicitly designed to align with the data from the Unity project we've been working on.

## Environment Requirements
The application expects several environment variables:
- `DB_URL` & `DB_TOKEN`: For Milvus connection.
- `AI_MODEL`: To specify the Ollama model to use (e.g., `llama3`).
