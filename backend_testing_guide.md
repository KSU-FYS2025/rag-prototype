# Backend Testing Guide - rag-prototype

Since you are on macOS, the setup is much simpler than the WSL instructions in the README. Follow these steps to get your backend ready for the POI synchronization test.

## 1. Install `uv`
`uv` is the recommended tool for managing dependencies in this project.
Open your terminal and run:
```bash
brew install uv
```

## 2. Install Dependencies
Navigate to the `rag-prototype` directory and install all required packages:
```bash
cd ./GitHub/rag-prototype
uv sync
```

## 3. Set Up Environment Variables
The application requires specific configuration. Create a `.env` file in the root of the `rag-prototype` folder.

### Option A: Using Milvus Lite (Local File)
If you don't want to run a full Milvus server, you can use a local file.
1. Update your `.env`:
   ```env
   DB_URL=vectorDB.db
   DB_TOKEN=
   AI_MODEL=llama3
   ```
2. **Note**: You may need to update `app/database/db.py` to allow empty tokens if the code currently enforces them.

### Option C: Using Milvus Cloud (Zilliz)
This is the recommended method for your serverless AWS instance.
1. Update your `.env`:
   ```env
   DB_URL=YOUR_ZILLIZ_PUBLIC_ENDPOINT
   DB_TOKEN=YOUR_ZILLIZ_API_TOKEN
   AI_MODEL=llama3
   ```
2. **Replace** `YOUR_ZILLIZ_API_TOKEN` with the token generated in your Zilliz Cloud console.

> [!IMPORTANT]
> For Zilliz Cloud, you **must** use an API Token. Use the "Project" -> "API Keys" section in the Zilliz console to create one.

### 3.1: Configurable Search Backend (Optional)
The backend can operate in 3 modes by setting `SEARCH_MODE` in `.env`:
* **`milvus`** (Default): Connects to the configured `DB_URL` Zilliz database.
* **`in_memory`**: Completely bypasses Milvus and reads a raw JSON file. It embeds and compares locally, which is incredibly fast for pure prototypes (<1,000 items).
* **`gemini_context`**: Abandons semantic search and instead pipes the *entire JSON file contents* into the Gemini prompt window so the LLM has global awareness of all rooms simultaneously.

**To use `in_memory` or `gemini_context` mode, add this to your `.env`:**
```env
SEARCH_MODE=in_memory
# Provide an absolute path to your Unity POIs JSON
POI_JSON_PATH=../Assets/NavigationFireDynamicMesh_POIs.json
```

## 4. Prepare the AI Engine

The backend supports both local execution via **Ollama** and cloud execution via **Gemini**.

### Option A: Local Ollama Model
If you are running the LLM locally on your Mac:
The AI features require **Ollama** to be running on your Mac.
1. Download and install Ollama from [ollama.com](https://ollama.com).
2. Pull the required model:
   ```bash
   ollama pull llama3
   ```

### Option B: Cloud Gemini API
If you prefer a faster or smarter cloud model, you can stream queries directly to Google's Gemini endpoint.
1. Sign up and grab an API key from Google AI Studio. 
2. Add your key and choose a Gemini model in your `.env`:
   ```env
   GEMINI_API_KEY=YOUR_API_KEY_HERE
   AI_MODEL=gemini-2.5-flash
   ```

## 5. Run the Server
Start the FastAPI server with the following command:
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
You should see output indicating the server is running at `http://0.0.0.0:8000`.

## 6. Verify Connectivity
Open your browser and go to:
- [http://localhost:8000/ping](http://localhost:8000/ping) - Should return `{"message": "pong!"}`.
- [http://localhost:8000/docs](http://localhost:8000/docs) - Interactive API documentation.

Once the server is running, you can use the **POI Sync Tool** in Unity to start the test!
