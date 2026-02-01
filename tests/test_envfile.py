from pathlib import Path


def test_docker_compose_uses_env_local():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert ".env.local" in compose
