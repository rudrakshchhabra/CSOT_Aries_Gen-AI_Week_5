import os
import re

WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))
SKILLS_DIR = os.path.join(WORKSPACE_ROOT, "skills")

def scan_skills() -> list[dict]:
    """Scans the skills directory and extracts Tier 1 YAML frontmatter metadata."""
    if not os.path.exists(SKILLS_DIR):
        return []
    
    catalog = []
    for entry in os.listdir(SKILLS_DIR):
        skill_path = os.path.join(SKILLS_DIR, entry)
        skill_md = os.path.join(skill_path, "SKILL.md")
        if os.path.isdir(skill_path) and os.path.exists(skill_md):
            try:
                with open(skill_md, "r", encoding="utf-8") as f:
                    content = f.read()
                
                match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
                if match:
                    frontmatter = match.group(1)
                    name_match = re.search(r"name:\s*(.+)", frontmatter)
                    desc_match = re.search(r"description:\s*>?\s*(.+?)(?=\n[a-z]:|\n$|$)", frontmatter, re.DOTALL)
                    
                    name = name_match.group(1).strip() if name_match else entry
                    desc = desc_match.group(1).strip().replace("\n", " ") if desc_match else "No description provided."
                    
                    catalog.append({
                        "name": name,
                        "description": desc,
                        "path": entry
                    })
            except Exception as e:
                print(f"[Warning] Failed to read skill {entry}: {e}")
    return catalog

def get_skills_catalog_prompt() -> str:
    """Returns the formatted skills catalog string for injection into build_system_prompt()."""
    catalog = scan_skills()
    if not catalog:
        return ""
    
    prompt = "\n\n## Available Skills (Progressive Disclosure)\n"
    prompt += "You have access to specialized runbooks. When a user request matches a description below, call `load_skill` with the skill name BEFORE attempting the task:\n"
    for skill in catalog:
        prompt += f"- **{skill['name']}**: {skill['description']}\n"
    return prompt

def load_skill(name: str) -> dict:
    """Tool: Reads the full Tier 2 body of a SKILL.md and lists sibling resources."""
    skill_dir = os.path.join(SKILLS_DIR, name)
    skill_md = os.path.join(skill_dir, "SKILL.md")
    
    if not os.path.exists(skill_md):
        return {"error": f"Skill '{name}' not found. Use `/skills list` to see available skills."}
    
    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Strip frontmatter for cleaner token consumption
        body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL).strip()
        
        # Discover Tier 3 bundled scripts or resources
        resources = []
        for root, _, files in os.walk(skill_dir):
            for file in files:
                if file != "SKILL.md":
                    rel_path = os.path.relpath(os.path.join(root, file), WORKSPACE_ROOT)
                    resources.append(rel_path.replace("\\", "/"))
        
        output = f"# Loaded Skill: {name}\n\n## Instructions\n{body}"
        if resources:
            output += f"\n\n## Bundled Resources (Available via read_file or run_command)\n" + "\n".join(f"- {r}" for r in resources)
            
        return {"content": output}
    except Exception as e:
        return {"error": f"Failed to load skill '{name}': {str(e)}"}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": "Load the full procedural instructions and resource list for a specialized skill. Call this when the user's task matches an available skill description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The exact name of the skill to load (e.g., 'commit')."
                    }
                },
                "required": ["name"]
            }
        }
    }
]