from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ZERION_", env_file=".env", extra="ignore")

    workspace: Path = Path.cwd()
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    default_model: str = "qwen2.5-coder:14b"
    fast_model: str = "qwen2.5-coder:7b"
    heavy_model: str = "deepseek-coder-v2:16b"
    vision_model: str = "qwen2.5vl:7b"
    chat_model: str = "llama3.1:8b"
    chroma_path: Path = Path(".memory/chroma")
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "zerion"
    use_neo4j: bool = False

    @property
    def memory_root(self) -> Path:
        return self.workspace / ".memory"

    @property
    def stm_dir(self) -> Path:
        return self.memory_root / "stm"

    @property
    def episodic_dir(self) -> Path:
        return self.memory_root / "episodic"

    @property
    def semantic_dir(self) -> Path:
        return self.memory_root / "semantic"

    @property
    def procedural_dir(self) -> Path:
        return self.memory_root / "procedural"

    @property
    def skills_dir(self) -> Path:
        skills = self.procedural_dir / "skills"
        skills.mkdir(parents=True, exist_ok=True)
        return skills

    @property
    def agent_bus_dir(self) -> Path:
        return self.workspace / ".agent_bus"

    @property
    def project_registry_path(self) -> Path:
        return self.memory_root / "project_registry.json"

    @property
    def repo_intel_dir(self) -> Path:
        return self.workspace

    @property
    def sessions_dir(self) -> Path:
        sessions = self.memory_root / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        return sessions


settings = Settings()
