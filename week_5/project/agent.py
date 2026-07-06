import os
import sys
import json
import uuid
import asyncio
import argparse
from datetime import datetime, timezone
from openai import OpenAI
from dotenv import load_dotenv

import tools.files as files
import tools.exec as exec_tools
import tools.search as search
import tools.plan as plan
import tools.skills as skills
from tools.mcp_manager import MCPManager, load_mcp_config

load_dotenv()

def get_config() -> dict:
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f).get("agent", {})
    return {}

CONFIG = get_config()
MODEL = CONFIG.get("model", "openrouter/free")
MAX_ITERATIONS = CONFIG.get("max_iterations", 15)
SESSIONS_DIR = ".agent/sessions"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)

def build_system_prompt() -> str:
    prompt = "You are Code Scout, an autonomous, extensible software engineering platform."
    if os.path.exists("AGENTS.md"):
        with open("AGENTS.md", "r", encoding="utf-8") as f:
            prompt += f"\n\n{f.read()}"
    prompt += skills.get_skills_catalog_prompt()
    return prompt

def save_session(session_id: str, messages: list, title: str = "Untitled") -> None:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    data = {"id": session_id, "title": title, "created_at": now, "updated_at": now, "messages": messages}
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_session(session_id: str) -> dict:
    filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

class Agent:
    def __init__(self, session_id: str = None):
        self.session_id = session_id or uuid.uuid4().hex[:8]
        session_data = load_session(self.session_id)
        self.messages = session_data.get("messages", []) if session_data else [{"role": "system", "content": build_system_prompt()}]
        self.mcp = MCPManager()
        self.local_tools = (
            files.FILE_TOOLS + 
            exec_tools.TOOLS + 
            search.TOOLS + 
            plan.TOOLS + 
            skills.TOOLS
        )

    async def initialize(r_self):
        """Connects to all configured MCP servers before starting the loop."""
        await r_self.mcp.connect_all()

    async def chat(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        save_session(self.session_id, self.messages)
        return await self._run_loop()

    async def _run_loop(self) -> str:
        master_tools = self.local_tools + self.mcp.openai_tools
        
        for _ in range(MAX_ITERATIONS):
            response = client.chat.completions.create(
                model=MODEL,
                messages=self.messages,
                tools=master_tools if master_tools else None
            )
            
            assistant_msg = response.choices[0].message
            self.messages.append(assistant_msg.model_dump())
            save_session(self.session_id, self.messages)

            if assistant_msg.tool_calls:
                for tool_call in assistant_msg.tool_calls:
                    tool_output = await self.dispatch(tool_call)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": tool_output
                    })
                save_session(self.session_id, self.messages)
                continue
            
            todos_state = plan.get_todos()
            if isinstance(todos_state, dict) and "todos" in todos_state:
                unfinished = [t for t in todos_state["todos"] if t["status"] in ["pending", "in_progress"]]
                if unfinished:
                    self.messages.append({"role": "user", "content": "SYSTEM: Continue working on remaining todo items until verified."})
                    continue
            return assistant_msg.content or ""
        return "Max execution loop iterations reached."

    async def dispatch(self, tool_call) -> str:
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            return "Error: Malformed JSON arguments in tool call."
        
        if name in self.mcp.tool_to_session:
            return await self.mcp.call_tool(name, args)
        
        try:
            if name == "run_command": res = exec_tools.run_command(**args)
            elif name == "grep": res = search.grep(**args)
            elif name == "list_definitions": res = search.list_definitions(**args)
            elif name == "add_todos": res = plan.add_todos(**args)
            elif name == "get_todos": res = plan.get_todos(**args)
            elif name == "mark_todo": res = plan.mark_todo(**args)
            elif name == "read_file": res = files.read_file(**args)
            elif name == "write_file": res = files.write_file(**args)
            elif name == "edit_file": res = files.edit_file(**args)
            elif name == "list_files": res = files.list_files(**args)
            elif name == "load_skill": res = skills.load_skill(**args)
            else: res = {"error": f"Unknown tool dispatched: {name}"}
        except Exception as e: 
            res = {"error": f"Execution error in {name}: {str(e)}"}
            
        return json.dumps(res) if not isinstance(res, str) else res

    async def cleanup(self):
        await self.mcp.aclose()

class REPLAgent(Agent):
    async def run(self) -> None:
        await self.initialize()
        print(f"\n--- Code Scout Platform Ready (Model: {MODEL}) ---")
        print("Type '/skills list', '/mcp list', or start chatting. Type '/quit' to exit.")
        while True:
            try:
                inp = input("\n> ").strip()
                if inp in ["/quit", "/exit"]: 
                    break
                if not inp: 
                    continue
                
                if inp == "/skills list":
                    catalog = skills.scan_skills()
                    print("\n[Available Skills]")
                    for s in catalog: print(f"  - {s['name']}: {s['description']}")
                    continue
                if inp == "/mcp list":
                    print("\n[Connected MCP Servers]")
                    for s in self.mcp.active_servers: print(f"  - {s} (Online)")
                    continue
                
                print(await self.chat(inp))
            except (KeyboardInterrupt, EOFError):
                break
        await self.cleanup()

async def run_oneshot(agent, prompt: str) -> None:
    await agent.initialize()
    try:
        if prompt == "/skills list":
            catalog = skills.scan_skills()
            print("\n[Available Skills]")
            for s in catalog: print(f"  - {s['name']}: {s['description']}")
            return
        if prompt == "/mcp list":
            print("\n[Connected MCP Servers]")
            for s in agent.mcp.active_servers: print(f"  - {s} (Online)")
            return
            
        response = await agent.chat(prompt)
        print(response)
    finally:
        await agent.cleanup()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="?")
    args = parser.parse_args()
    agent = REPLAgent()
    try:
        if args.prompt:
            asyncio.run(run_oneshot(agent, args.prompt))
        else:
            asyncio.run(agent.run())
    except (RuntimeError, GeneratorExit, KeyboardInterrupt, Exception) as e:
        if "cancel scope" not in str(e) and "asynchronous generator" not in str(e):
            print(f"\n[Notice] Script exited: {e}")
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()