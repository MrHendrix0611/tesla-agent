from pathlib import Path


class SkillManager:

    def __init__(self, skills_path="skills"):
        self.skills_path = Path(skills_path)

    def list_skills(self):
        if not self.skills_path.exists():
            return []

        return sorted([
            folder.name
            for folder in self.skills_path.iterdir()
            if folder.is_dir()
        ])

    def skill_exists(self, skill_name):
        return skill_name in self.list_skills()

    def load_skill(self, skill_name):
        skill_path = self.skills_path / skill_name

        if not skill_path.exists():
            raise ValueError(
                f"Skill não encontrada: {skill_name}"
            )

        instructions_path = skill_path / "instructions.md"

        if not instructions_path.exists():
            raise ValueError(
                f"instructions.md não encontrada para a Skill: {skill_name}"
            )

        return instructions_path.read_text(
            encoding="utf-8"
        )