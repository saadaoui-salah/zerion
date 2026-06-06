from __future__ import annotations

import json
import re
from pathlib import Path

from zerion_core.config import settings


def parse_skill_md(path: Path) -> dict[str, str] | None:
    """Parse a skill file (Modelfile-like) and extract instructions."""
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    
    data = {}
    
    # 1. Extract FROM
    from_match = re.search(r'^FROM\s+(\S+)', content, re.MULTILINE)
    if from_match:
        data["model"] = from_match.group(1)
    
    # 2. Extract SYSTEM prompt from triple quotes
    system_match = re.search(r'SYSTEM\s+"""(.*?)"""', content, re.DOTALL)
    if not system_match:
        # Fallback to single line or simple block if no triple quotes
        system_match = re.search(r'SYSTEM\s+(.+)', content)
        
    if system_match:
        data["system_prompt"] = system_match.group(1).strip()
    else:
        # If no SYSTEM block, use everything except instructions as fallback
        clean_content = re.sub(r'^(FROM|PARAMETER|TEMPLATE|ADAPTER)\s+.*$', '', content, flags=re.MULTILINE)
        data["system_prompt"] = clean_content.strip()

    if not data.get("system_prompt"):
        return None

    # Role and name will be provided by CLI usually, but defaults here
    data["role"] = path.stem.lower()
    data["name"] = path.stem.replace("_", "-").title()

    return data


def save_skill(name: str, skill_data: dict[str, str], registered_model: str) -> Path:
    """Save skill data with a specific name and registered model."""
    skill_data["name"] = name.title()
    skill_data["role"] = name.lower().replace("-", "_")
    skill_data["registered_model"] = registered_model
    
    role = skill_data["role"]
    target_path = settings.skills_dir / f"{role}.json"
    
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(skill_data, f, indent=2)
    
    return target_path


def list_custom_skills() -> dict[str, str]:
    """Load all custom skills from the skills directory."""
    skills = {}
    if not settings.skills_dir.exists():
        return skills

    for path in settings.skills_dir.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                role = data.get("role")
                prompt = data.get("system_prompt")
                if role and prompt:
                    skills[role] = prompt
        except Exception:
            continue
    return skills
