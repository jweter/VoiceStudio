"""Pin the Docker workflow contract: image BUILD verification only, and no publishing to anyone else's registry.

History: the workflow used to push to the original author's registries (ghcr.io/debpalash/..., docker.io/palashdeb/...)
and failed on every push with permission_denied. It is now build-only. These tests keep that from regressing, keep the
CUDA and ROCm builds verified, and require publishing to this repository's own registry to be a deliberate, reviewed
change (it must update these tests) rather than something that creeps back in.
"""

import os
import re

import pytest

yaml = pytest.importorskip("yaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "docker.yml")


def _text():
    with open(WORKFLOW, encoding="utf-8") as fh:
        return fh.read()


def _code():
    """The workflow without comment lines: comments may NAME what was removed, configuration may not use it."""
    return "\n".join(line for line in _text().splitlines() if not line.lstrip().startswith("#"))


def _workflow():
    return yaml.safe_load(_text())


def _steps(job):
    return _workflow()["jobs"][job]["steps"]


def _build_step(job):
    return next(s for s in _steps(job) if str(s.get("uses", "")).startswith("docker/build-push-action"))


def test_the_workflow_cannot_publish_anywhere():
    text = _code()
    workflow = _workflow()
    # permissions: read-only token, no package write.
    assert workflow["permissions"] == {"contents": "read"}
    assert "packages: write" not in text
    # No registry login, no secrets, no push.
    assert not any(str(s.get("uses", "")).startswith("docker/login-action") for job in workflow["jobs"].values()
                   for s in job["steps"])
    assert "secrets." not in text.replace("GITHUB_TOKEN", "")
    assert re.search(r"push:\s*true", text) is None
    for job in workflow["jobs"]:
        assert _build_step(job)["with"]["push"] is False


def test_no_upstream_registry_destinations_remain():
    code = _code()
    for forbidden in ("debpalash", "palashdeb", "ghcr.io", "docker.io", "hub.docker.com", "imagetools"):
        assert forbidden not in code, f"docker.yml still references {forbidden}"


def test_cuda_and_rocm_image_builds_are_both_verified():
    workflow = _workflow()
    assert set(workflow["jobs"]) == {"build-cuda", "build-rocm"}
    for job in workflow["jobs"]:
        assert _build_step(job)["with"]["file"] == "deploy/Dockerfile"
    rocm = _build_step("build-rocm")["with"]["build-args"]
    assert "BASE_IMAGE=rocm/pytorch:" in rocm and "GPU_FLAVOR=rocm" in rocm
    assert "build-args" not in _build_step("build-cuda")["with"]


def test_the_two_builds_keep_the_same_disk_reclaim_list():
    def reclaim(job):
        step = next(s for s in _steps(job) if s.get("name") == "Free runner disk space")
        return step["run"]

    assert reclaim("build-cuda") == reclaim("build-rocm")
    assert "docker image prune --all --force" in reclaim("build-cuda")


def test_the_workflow_runs_on_the_files_that_define_the_images():
    on = _workflow()[True] if True in _workflow() else _workflow()["on"]
    assert on["pull_request"]["paths"] == ["deploy/**", ".github/workflows/docker.yml"]
    assert "main" in on["push"]["branches"] and "v*" in on["push"]["tags"]


def test_sha_tags_follow_the_checked_out_source_commit():
    text = _text()
    assert text.count("git rev-parse --short=7 HEAD") == 2
    assert "type=sha" not in text
    assert "GITHUB_SHA::7" not in text


def test_active_templates_still_use_the_documented_public_image_path():
    """Templates and docs consume the upstream project's published images; that is unchanged and not publishing."""
    canonical = "ghcr.io/debpalash/voicestudio"
    for rel in (
        "deploy/docker-compose.yml",
        "docs/integration-directory.md",
        "docs/install/linux.md",
        "electron/src/renderer/src/features/integrations/setup-registry.ts",
    ):
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert canonical in text, f"{rel} does not use the documented GHCR path"
