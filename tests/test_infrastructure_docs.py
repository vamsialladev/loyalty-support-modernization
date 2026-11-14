"""The AWS Terraform keeps its safety properties, and the operations documents stay in step with the code (DEL-06,
DEL-08, DEL-09, OPS-06, SEC-22, SEC-23; ADR-0085). `scripts\\terraform_check.ps1` runs fmt and validate."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TF = ROOT / "infrastructure" / "terraform" / "aws"


def _tf() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(TF.glob("*.tf")))


def test_the_database_is_private_encrypted_and_backed_up() -> None:
    rds = (TF / "rds.tf").read_text(encoding="utf-8")
    assert "publicly_accessible    = false" in rds
    assert "storage_encrypted     = true" in rds
    assert re.search(r"backup_retention_period\s+= var.environment == \"production\" \? 14 : 7", rds)
    assert "manage_master_user_password   = true" in rds  # no password in code or state
    assert '"rds.force_ssl"' in rds


def test_only_the_load_balancer_takes_traffic_from_the_internet_and_only_on_443() -> None:
    security = (TF / "security.tf").read_text(encoding="utf-8")
    ingress = re.findall(r'resource "aws_vpc_security_group_ingress_rule" "(\w+)" \{(.*?)\n\}', security, re.S)
    open_to_world = [name for name, body in ingress if "0.0.0.0/0" in body]
    assert open_to_world == ["alb_https"]
    body = dict(ingress)["alb_https"]
    assert "from_port         = 443" in body and "to_port           = 443" in body
    assert "assign_public_ip = false" in (TF / "ecs.tf").read_text(encoding="utf-8")


def test_no_secret_value_and_no_long_lived_key_is_in_the_terraform() -> None:
    text = _tf()
    for pattern in (r"secret_string\s*=", r"password\s*=\s*\"", r"aws_iam_access_key", r"AKIA[0-9A-Z]{16}"):
        assert not re.search(pattern, text), pattern
    assert "readonlyRootFilesystem = true" in text and 'drop = ["ALL"]' in text


def test_providers_are_pinned_and_the_lock_file_is_committed() -> None:
    versions = (TF / "versions.tf").read_text(encoding="utf-8")
    assert re.search(r'version\s*=\s*"\d+\.\d+\.\d+"', versions)
    assert (TF / ".terraform.lock.hcl").is_file()


def test_the_rollback_table_covers_every_migration() -> None:
    revisions = sorted(p.name[:4] for p in (ROOT / "migrations" / "versions").glob("0*.py") if p.name[:4] != "0001")
    rollback = (ROOT / "docs" / "rollback.md").read_text(encoding="utf-8")
    listed = re.findall(r"^\| (\d{4}) ", rollback, re.M)
    assert sorted(listed) == revisions, "add the new migration to docs/rollback.md"


def test_the_slos_are_labelled_proposed_and_claim_nothing_measured_in_production() -> None:
    slos = (ROOT / "docs" / "slos.md").read_text(encoding="utf-8")
    assert "Proposed, not measured" in slos and "a local test proves no production" in slos.replace("\n", " ")
    assert "Not measured (no hosted deployment)" in slos


def test_every_alarm_names_a_runbook_that_exists() -> None:
    for runbook in re.findall(r"Runbook: (docs/[\w/.-]+\.md)", _tf()):
        assert (ROOT / runbook).is_file(), runbook
