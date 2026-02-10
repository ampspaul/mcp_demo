# mcp_demo
# Initial update


# Install dependency 
uv sync

# activate virtual env

source .venv/bin/activate 

# Run  Mock Workday API
uv run uvicorn mock_workday_api.app:app --host 127.0.0.1 --port 9001

# Run : MCP Server (SSE)
uv run python -m mcp_server.server_sse

# Run : Agent
uv run python -m agent_app.agent

# RUN: UI APP

uv run streamlit run ui_app.py 

