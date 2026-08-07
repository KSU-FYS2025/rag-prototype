import pathlib
from functools import lru_cache

from google.adk.tools.skill_toolset import SkillToolset
from google.adk.skills import load_skill_from_dir

skill_names = [
    "milvus-boolean-filter",
    "milvus-json-operators",
    "milvus-array-operators",
    "milvus-struct-array-operators",
    "milvus-geometry-operators",
    "milvus-random-sampling",
    "milvus-filter-templating",
    "poi-json-schema",
]

skills_dir = pathlib.Path(__file__).parent


@lru_cache(maxsize=None)
def load(skills: tuple[str, ...] | None = None) -> SkillToolset:
    if not skills:
        loaded_names = skill_names
    else:
        for skill in skills:
            if skill not in skill_names:
                raise Exception(
                    f"skill {skill} is not found in skill_names inside skills/skills.py!"
                )
        loaded_names = skills

    return SkillToolset(
        skills=[load_skill_from_dir(skills_dir / name) for name in loaded_names]
    )
