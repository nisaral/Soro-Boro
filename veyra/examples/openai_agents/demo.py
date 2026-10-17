"""OpenAI Agents SDK Veyra Integration Example."""

from veyra import Veyra
from veyra.integrations.openai_agents import VeyraOpenAIAgentsAdapter

def search_database(query: str) -> str:
    return f"Results for: {query}"

def main():
    veyra = Veyra()
    adapter = VeyraOpenAIAgentsAdapter(veyra)
    wrapped_tool = adapter.wrap_tool(search_database)

    result = wrapped_tool(query="active users")
    print("Execution Result:", result)

if __name__ == "__main__":
    main()
