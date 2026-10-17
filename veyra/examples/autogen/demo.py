"""AutoGen Veyra Integration Example."""

from veyra import Veyra
from veyra.integrations.autogen import VeyraAutoGenAdapter

def send_email(recipient: str, body: str) -> str:
    return f"Sent email to {recipient}"

def main():
    veyra = Veyra()
    adapter = VeyraAutoGenAdapter(veyra)

    tool = adapter.register_function(send_email)
    res = tool(recipient="user@example.com", body="Hello")
    print("AutoGen execution result:", res)

if __name__ == "__main__":
    main()
