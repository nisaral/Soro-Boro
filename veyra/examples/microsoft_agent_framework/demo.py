"""Microsoft Agent Framework Veyra Integration Example."""

from veyra import Veyra
from veyra.integrations.microsoft_agent_framework import VeyraMicrosoftAgentMiddleware

def update_record(record_id: int, status: str) -> str:
    return f"Record {record_id} updated to {status}"

def main():
    veyra = Veyra()
    middleware = VeyraMicrosoftAgentMiddleware(veyra)

    res = middleware("update_record", {"record_id": 101, "status": "APPROVED"}, update_record)
    print("Microsoft Agent Middleware result:", res)

if __name__ == "__main__":
    main()
