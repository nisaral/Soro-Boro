"""Veyra Policy Pack & Plugin Example."""

from veyra import Veyra
from veyra.plugins import default_plugins, veyra_plugin

@veyra_plugin(name="strict_security", version="1.0.0", capabilities=["authorization", "tenant_isolation"])
class StrictSecurityPolicyPack:
    def __init__(self):
        self.name = "strict_security"

def main():
    veyra = Veyra(policy="deterministic")
    print("Installed Veyra plugins:", default_plugins.list_plugins())
    print("Strict security plugin metadata:", default_plugins.inspect("strict_security"))

if __name__ == "__main__":
    main()
