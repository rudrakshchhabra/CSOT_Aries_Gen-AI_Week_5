import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual import work
import agent

class TUIAgent(agent.Agent):
    def __init__(self, session_id: str = None):
        super().__init__(session_id)
        self.app = ResearchApp(self)

    def run(self) -> None:
        self.app.run()

class ResearchApp(App):
    TITLE = "Code Scout — Extensible Engineering Desk"
    CSS = """
    Screen { layout: vertical; }
    RichLog { height: 1fr; border: solid $primary; padding: 0 1; }
    Input { dock: bottom; height: 3; }
    """

    def __init__(self, agent_instance):
        super().__init__()
        self.agent = agent_instance

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log", wrap=True, markup=True)
        yield Input(id="chat_input", placeholder="Ask Code Scout to debug, review PRs, or run skills...")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write(f"[bold green]Session Initialized:[/bold green] {self.agent.session_id}\n")
        self.query_one(Input).focus()
        self.run_worker(self._init_mcp_async())

    async def _init_mcp_async(self):
        log = self.query_one("#log", RichLog)
        log.write("[dim]Connecting to external MCP servers from config.json...[/dim]")
        await self.agent.initialize()
        for server in self.agent.mcp.active_servers:
            log.write(f"[bold cyan]Connected MCP Server:[/bold cyan] {server}")
        log.write("[bold green]Platform Ready.[/bold green]\n")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text: 
            return
        
        inp = self.query_one(Input)
        inp.clear()
        inp.disabled = True 

        log = self.query_one('#log', RichLog)
        log.write(f"\n[bold cyan][You][/bold cyan] {user_text}")
        
        if user_text == "/skills list":
            catalog = agent.skills.scan_skills()
            log.write("[bold yellow]Available Skills:[/bold yellow]")
            for s in catalog: log.write(f"  - [bold]{s['name']}[/bold]: {s['description']}")
            inp.disabled = False; inp.focus()
            return
        if user_text == "/mcp list":
            log.write("[bold yellow]Active MCP Servers:[/bold yellow]")
            for s in self.agent.mcp.active_servers: log.write(f"  - [bold]{s}[/bold] (Online)")
            inp.disabled = False; inp.focus()
            return

        log.write("[dim]Agent is reasoning and executing tools...[/dim]")
        self.process_chat(user_text)

    @work(thread=True)
    def process_chat(self, user_text: str) -> None:
        try:
            # Run the async chat loop safely from the background thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(self.agent.chat(user_text))
            loop.close()
            self.call_from_thread(self.display_response, response)
        except Exception as e:
            self.call_from_thread(self.display_response, f"[red]Execution Error: {str(e)}[/red]")

    def display_response(self, response_text: str) -> None:
        log = self.query_one("#log", RichLog)
        log.write(f"[bold green][Agent][/bold green]\n{response_text}\n")
        inp = self.query_one(Input)
        inp.disabled = False 
        inp.focus()

if __name__ == "__main__":
    TUIAgent().run()