"""LangGraph Veyra Integration Example."""

from veyra import Veyra
from veyra.integrations.langgraph import VeyraLangGraphNode

def execute_sql(query: str) -> str:
    return f"Executed: {query}"

def main():
    veyra = Veyra()
    lg_node = VeyraLangGraphNode(veyra, [execute_sql])

    graph_state = {"proposed_action": {"tool": "execute_sql", "arguments": {"query": "SELECT * FROM users"}}}
    output_state = lg_node(graph_state)
    print("LangGraph node state output:", output_state)

if __name__ == "__main__":
    main()
