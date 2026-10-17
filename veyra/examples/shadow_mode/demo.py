"""Veyra Production Shadow & Fail-Closed Mode Example."""

from veyra import Veyra

def process_payment(amount: float) -> str:
    return f"Processed payment of ${amount}"

def main():
    shadow_veyra = Veyra(mode="shadow")
    @shadow_veyra.wrap
    def shadow_payment(amount: float) -> str:
        return process_payment(amount)

    print("Shadow mode call:", shadow_payment(amount=100.0))

    strict_veyra = Veyra(mode="fail_closed")
    @strict_veyra.wrap
    def strict_payment(amount: float) -> str:
        return process_payment(amount)

    print("Fail-closed mode call:", strict_payment(amount=50.0))

if __name__ == "__main__":
    main()
