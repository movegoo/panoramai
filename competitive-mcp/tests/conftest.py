"""Configuration pytest — set env vars before imports."""
import os

# Set backend dir so competitive_mcp.db can find the models
os.environ["COMPETITIVE_BACKEND_DIR"] = os.path.join(
    os.path.dirname(__file__), "..", "..", "backend"
)
os.environ["DATABASE_URL"] = "sqlite:///./test_competitive.db"
