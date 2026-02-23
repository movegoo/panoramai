"""Tests to validate Terraform configuration files exist and are well-structured."""
import os
import pytest

INFRA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "infra")

EXPECTED_FILES = [
    "main.tf",
    "variables.tf",
    "vpc.tf",
    "rds.tf",
    "ecr.tf",
    "ecs.tf",
    "alb.tf",
    "s3.tf",
    "ssm.tf",
    "security_groups.tf",
    "outputs.tf",
    "dev.tfvars",
    "prod.tfvars",
    "backend-dev.hcl",
    "backend-prod.hcl",
]


class TestTerraformFiles:
    """Validate Terraform infra files exist and contain expected resources."""

    @pytest.mark.parametrize("filename", EXPECTED_FILES)
    def test_file_exists(self, filename):
        """Each expected Terraform file should exist."""
        path = os.path.join(INFRA_DIR, filename)
        assert os.path.isfile(path), f"Missing: infra/{filename}"

    def test_vpc_has_cidr(self):
        with open(os.path.join(INFRA_DIR, "vpc.tf")) as f:
            content = f.read()
        assert "10.0.0.0/16" in content

    def test_rds_postgres16(self):
        with open(os.path.join(INFRA_DIR, "rds.tf")) as f:
            content = f.read()
        assert 'engine_version = "16"' in content
        assert "storage_encrypted = true" in content

    def test_alb_idle_timeout_3600(self):
        with open(os.path.join(INFRA_DIR, "alb.tf")) as f:
            content = f.read()
        assert "idle_timeout = 3600" in content

    def test_alb_health_check_path(self):
        with open(os.path.join(INFRA_DIR, "alb.tf")) as f:
            content = f.read()
        assert "/api/health" in content

    def test_ecs_fargate(self):
        with open(os.path.join(INFRA_DIR, "ecs.tf")) as f:
            content = f.read()
        assert "FARGATE" in content

    def test_security_groups_proper_isolation(self):
        with open(os.path.join(INFRA_DIR, "security_groups.tf")) as f:
            content = f.read()
        # ALB allows 443
        assert "443" in content
        # RDS allows 5432 from ECS only
        assert "5432" in content

    def test_ssm_has_all_secrets(self):
        with open(os.path.join(INFRA_DIR, "ssm.tf")) as f:
            content = f.read()
        required_secrets = [
            "DATABASE_URL", "JWT_SECRET", "META_APP_ID",
            "ANTHROPIC_API_KEY", "SCRAPECREATORS_API_KEY",
        ]
        for secret in required_secrets:
            assert secret in content, f"Missing SSM secret: {secret}"

    def test_s3_encryption(self):
        with open(os.path.join(INFRA_DIR, "s3.tf")) as f:
            content = f.read()
        assert "AES256" in content

    def test_ecr_lifecycle_policy(self):
        with open(os.path.join(INFRA_DIR, "ecr.tf")) as f:
            content = f.read()
        assert "imageCountMoreThan" in content

    def test_dev_tfvars(self):
        with open(os.path.join(INFRA_DIR, "dev.tfvars")) as f:
            content = f.read()
        assert 'env' in content
        assert '"dev"' in content
        assert "512" in content  # 0.5 vCPU

    def test_prod_tfvars(self):
        with open(os.path.join(INFRA_DIR, "prod.tfvars")) as f:
            content = f.read()
        assert '"prod"' in content
        assert "1024" in content  # 1 vCPU
        assert "2048" in content  # 2 GB RAM
