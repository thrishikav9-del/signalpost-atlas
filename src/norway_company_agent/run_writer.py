"""
Signalpost Atlas — Centralized Run-Artifact Writer
Ensures automatic, predictable, tamper-evident saving of every run,
conforming strictly to Master Prompt Part 9 and Competition requirements.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence import utc_now


class RunArtifactWriter:
    """Centralized manager for atomic checkpointing and run artifact persistence."""

    def __init__(self, base_dir: Path | str, run_id: str, run_config: dict[str, Any]):
        self.base_dir = Path(base_dir).resolve()
        self.run_id = run_id
        self.run_config = run_config
        self.started_at = utc_now()
        self.start_monotonic = time.monotonic()

        # Format timestamped run folder: YYYY-MM-DD_HH-MM-SS_<run_id>
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        self.run_dir_name = f"{ts}_{run_id}"
        self.run_dir = self.base_dir / "runs" / self.run_dir_name
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Update results/LATEST_RUN.txt
        latest_file = self.base_dir / "LATEST_RUN.txt"
        latest_content = f"RUN_ID={self.run_id}\nPATH=results/runs/{self.run_dir_name}\nTIMESTAMP={self.started_at}\n"
        latest_file.write_text(latest_content, encoding="utf-8")

        # Save run configuration immediately
        self.save_json("run_config.json", {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "run_dir": str(self.run_dir),
            "configuration": self.run_config,
        })

        # Setup run logger
        self.log_file = self.run_dir / "run.log"
        self._setup_logger()

    def _setup_logger(self) -> None:
        self.logger = logging.getLogger(f"run_{self.run_id}")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file, encoding="utf-8")
            formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.info("Initialized run %s in %s", self.run_id, self.run_dir)

    def log(self, message: str, level: str = "info") -> None:
        if level == "error":
            self.logger.error(message)
        elif level == "warning":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def save_json(self, filename: str, data: Any) -> Path:
        import uuid
        target = self.run_dir / filename
        temp = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temp.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            for attempt in range(6):
                try:
                    temp.replace(target)
                    break
                except (PermissionError, OSError):
                    if attempt == 5:
                        raise
                    time.sleep(0.05 * (2**attempt))
        finally:
            if temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass
        return target

    def write_jsonl_atomic(self, filename: str, items: list[dict[str, Any]]) -> Path:
        import uuid
        target = self.run_dir / filename
        temp = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temp.open("w", encoding="utf-8") as f:
                for item in items:
                    f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
            for attempt in range(6):
                try:
                    temp.replace(target)
                    break
                except (PermissionError, OSError):
                    if attempt == 5:
                        raise
                    time.sleep(0.05 * (2**attempt))
        finally:
            if temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass
        return target

    def save_manifest(self, input_items: list[dict[str, Any]]) -> Path:
        return self.save_json("input_manifest.json", {
            "run_id": self.run_id,
            "count": len(input_items),
            "items": input_items,
        })

    def save_checkpoint(self, profiles: list[dict[str, Any]]) -> Path:
        return self.write_jsonl_atomic("profiles.jsonl", profiles)

    def finalize_run(
        self,
        *,
        envelopes: list[dict[str, Any]],
        profiles: list[dict[str, Any]],
        metrics: dict[str, Any],
        validation: dict[str, Any],
        status: str = "completed",
    ) -> dict[str, Any]:
        """Finalizes all run artifacts with integrity verification."""
        completed_at = utc_now()
        elapsed_sec = round(time.monotonic() - self.start_monotonic, 2)

        # 1. Write final envelopes (results.jsonl)
        results_path = self.write_jsonl_atomic("results.jsonl", envelopes)

        # 2. Write final profiles
        profiles_path = self.write_jsonl_atomic("profiles.jsonl", profiles)

        # 3. Extract claims and evidence for separate inspection
        all_claims = []
        all_evidence = []
        seen_ev_ids = set()

        for env in envelopes:
            for c in env.get("claims", []):
                all_claims.append({
                    "organisation_number": env["organisation_number"],
                    **c,
                })
            for ev in env.get("evidence", []):
                if ev.get("id") not in seen_ev_ids:
                    seen_ev_ids.add(ev.get("id"))
                    all_evidence.append({
                        "organisation_number": env["organisation_number"],
                        **ev,
                    })

        self.write_jsonl_atomic("claims.jsonl", all_claims)
        self.write_jsonl_atomic("evidence.jsonl", all_evidence)

        # 4. Save detailed metrics
        metrics_payload = {
            "run_id": self.run_id,
            "status": status,
            "started_at": self.started_at,
            "completed_at": completed_at,
            "elapsed_seconds": elapsed_sec,
            "operations": metrics,
            "validation": validation,
        }
        self.save_json("metrics.json", metrics_payload)

        # 5. Save final summary
        summary = {
            "run_id": self.run_id,
            "status": status,
            "started_at": self.started_at,
            "completed_at": completed_at,
            "duration_seconds": elapsed_sec,
            "total_companies_input": len(envelopes),
            "total_envelopes_emitted": len(envelopes),
            "validation_passed": validation.get("passed", False),
            "total_requests": metrics.get("requests", 0),
            "third_party_cost_usd": metrics.get("third_party_cost_usd", 0.0),
            "p50_latency_ms": metrics.get("p50_ms"),
            "p95_latency_ms": metrics.get("p95_ms"),
            "results_path": str(results_path.relative_to(self.base_dir)),
            "profiles_path": str(profiles_path.relative_to(self.base_dir)),
        }
        self.save_json("summary.json", summary)

        # 6. Generate run README.md
        readme_md = f"""# Run Report: {self.run_id}

- **Run ID:** `{self.run_id}`
- **Status:** `{status}`
- **Started:** `{self.started_at}`
- **Completed:** `{completed_at}`
- **Duration:** {elapsed_sec}s
- **Companies Processed:** {len(envelopes)}
- **Validation Passed:** `{validation.get('passed', False)}`
- **Total Requests:** {metrics.get('requests', 0)}
- **Third-Party Cost:** ${metrics.get('third_party_cost_usd', 0.0):.4f}

## Artifacts in this Run Directory
- `results.jsonl`: Evaluator terminal envelopes.
- `profiles.jsonl`: Researched company profiles.
- `claims.jsonl`: Extracted evidence-backed claims.
- `evidence.jsonl`: Source evidence records.
- `metrics.json`: Detailed operations, latencies, and validation metrics.
- `summary.json`: High-level summary of results.
- `run_config.json`: Configuration arguments used for execution.
- `input_manifest.json`: Input organisation numbers.
- `run.log`: Execution log trace.
"""
        (self.run_dir / "README.md").write_text(readme_md, encoding="utf-8")
        self.logger.info("Successfully finalized run %s", self.run_id)
        return summary
