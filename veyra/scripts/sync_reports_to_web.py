"""Script to compile all benchmark report JSON artifacts into web/src/lib/generatedBenchmarkReports.json."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def sync_reports():
    reports_dir = ROOT / "reports"
    web_dest = ROOT / "web" / "src" / "lib" / "generatedBenchmarkReports.json"

    data = {
        "results_m4_real_faults": json.loads((reports_dir / "results_m4_real_faults.json").read_text(encoding="utf-8")),
        "results_m2_m3_conformal_pasc": json.loads((reports_dir / "results_m2_m3_conformal_pasc.json").read_text(encoding="utf-8")),
        "results_conformal_matched_sweep": json.loads((reports_dir / "results_conformal_matched_sweep.json").read_text(encoding="utf-8")),
        "contract_inference_audit_100": json.loads((reports_dir / "contract_inference_audit_100.json").read_text(encoding="utf-8")),
        "claims_ledger": json.loads((reports_dir / "CLAIMS_LEDGER.json").read_text(encoding="utf-8")),
        "vendor_openapi_declared_vs_verified": json.loads((reports_dir / "vendor_openapi_declared_vs_verified.json").read_text(encoding="utf-8")),
    }

    web_dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Successfully compiled generatedBenchmarkReports.json ({web_dest.stat().st_size} bytes)")

if __name__ == "__main__":
    sync_reports()
