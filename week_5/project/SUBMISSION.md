                                    CSOT WEEK 5- GEN AI

For this week, I took my week 4's basic setup and included the tools that were suggested to be included in the lesson. I also gave the tools whatever I could and felt like should be included. It has evolved from the simple basic ReAct loop we built in week 3 into something which is like an engineering desk. Till last week it was hardcoded to use a fixed set of tools and terminal tools. But if we wanted it to follow a complex workflow or talk to external services online, we would have to stuff all those instructions into our system prompt in AGENT.md which will swallow up context tokens each time we called the chat which would be pretty much unnecessary. It would also lead to confusion as the lessons suggested. So I built a progressive disclosure skills engine so the agent can dynamically load procedural runbooks only when it needs them, and wired an MCP(using the knowledge of week 2 but not alphaxiv this time since it has authentication issues), over streamable HTTP. We got out code scout to get into remote servers like Github without changing a single line of its code to accomodate it specfically. Also we continued using the TUI interface obviously using the textual module.

What we can do now that could not be done till last week
1. Dynamic Skill loading- Instead of hardcoding and memorising all possible skills needed in our workflow, our code scout scans skills/ directory on booting up. It reads a lightweight YAML frontmatter to understand what skills exist and can be accessed if needed like it can access the commit skill in my project as of now but more can surely be added.
2. In week 4 we were using normal python functions as tools. But now using the mcp and config.json, we can connect to remote MCP servers over HTTP, prevent any naming collisions and feed them into the model's tool schema.
3. I tried to stop LLM hallucination programmatically by updating plan.py in the tools directory. The agent cannot mark a TODO item as completed until it passes the proper evidence containing an actual exit code or terminal output proving the fix worked.
4. Non Blocking TUI: I updated my tui code to be better than before this week. It boots a full-screen running textual Interface. As I wrapped the chat processor in background worker threads using @work the screen does not freeze or lock up while openrouter is reasoning or running a background subprocess.

The Feature & Skill Catalog
Here is a dive into the four major upgrades I built for Code Scout this week. I wanted every addition to solve a real, annoying bottleneck I ran into while working with autonomous agents:

1. The Progressive Skill Loader (tools/skills.py)
What it does: Instead of cramming massive rulebooks into the system prompt, this loader dynamically scans the skills/ folder whenever the app boots up. It grabs just the name and short description from the YAML frontmatter of each SKILL.md file, giving the AI a lightweight "table of contents." When the model realizes it needs the full step-by-step instructions for a specific workflow, it calls a tool (load_skill) to pull that entire file into memory on demand.
Why I built it: In early tests, stuffing 500+ lines of instructions for commits, code reviews, and deployment procedures into the default prompt completely overwhelmed free-tier models. They would lose focus and start forgetting basic chat rules. Using progressive disclosure keeps the baseline prompt lightweight so the AI stays sharp and only loads context when it actually needs it.
How it's used: When I give Code Scout a prompt like "wrap up this work" or "commit these changes," it checks its catalog index, sees the commit skill, and automatically runs load_skill(name="commit") before touching git.
2. The Commit Runbook (skills/commit/SKILL.md)
What it does: This is a strict, step-by-step procedural checklist that teaches the agent how to act like a professional developer when saving work. It forces Code Scout to: (1) run pytest, (2) halt immediately if any tests fail, (3) inspect git status and git diff to see what actually changed, (4) draft a Conventional Commit message (like fix(tests): ...), and (5) pause and ask me for explicit [y/N] confirmation before staging or committing a single file.
Why I built it: Honestly, I was tired of autonomous coding agents blindly running git commit -a -m "updated files" without checking if their edits actually compiled or broke existing tests. This skill forces the AI to respect open-source version control etiquette.
3. The Evidence-Enforced Planner (tools/plan.py)
What it does: This is our custom task management suite (add_todos, mark_todo). The architectural twist here is that every task must define a verification_method right when it gets created. Later, if the AI tries to mark that task as "completed", my Python code intercepts the call to check if the model passed concrete string proof (like "pytest exit code 0" or actual command output). If it didn't actually run the tests to get that proof, the tool rejects the update and throws a hard error, forcing the model to go back and verify its work.
Why I built it: We have all seen free LLMs lazily claim "I fixed the bug!" right after replacing a string, without ever running the code to see if it even compiles. This programmatic gate makes AI laziness impossible—if you don't bring terminal proof, you don't get to close the ticket.
4. Zero-Leak Streamable HTTP MCP Client (tools/mcp_manager.py)
What it does: This connects Code Scout to external tool servers (like GitHub) using the official Python MCP SDK over HTTP. To keep our secrets safe, I wrote a quick regex parser (re.sub(r"\$\{([A-Z0-9_]+)\}", ...)) for config.json so that sensitive tokens like ${GITHUB_PAT} are pulled dynamically from the local .env file at runtime.
Why I built it: I wanted Code Scout to be able to read pull requests, check issues, and triage repositories directly from my terminal without me having to write dozens of tedious GitHub API wrappers by hand. Just as importantly, I wanted absolute peace of mind that my personal access tokens would never get hardcoded into config files or accidentally pushed to public Git history.

How I Tested the Agent
I really didn't want to just guess what features to build, so I needed to see how the agent would handle a real, slightly intimidating codebase. I cloned Pallets/Click into a local target_repo/ folder and put Code Scout to work.
To prove to myself that the Progressive Skill Loader and Commit Skill actually made an objective difference (and weren't just overengineered fluff), I ran a simple A/B test. I gave the agent a bug to fix and told it to commit the changes—once without the skill loaded, and once with it:
Without the skill: It was honestly pretty sloppy. The model fixed the bug, but then it blindly ran git add . and fired off a lazy commit message like "updated files". It didn't even bother running the test suite again to make sure it hadn't broken anything else in the staging area.
With the skill: Night and day difference. The model explicitly told me it was following the runbook. It ran python -m pytest first to verify the build was green, checked the diff, drafted a proper Conventional Commit (fix(tests): correct assertion in test_basic.py), and actually paused to ask for my [y/N] approval before touching git.
I also wanted to make sure our Evidence Gate wasn't just decorative, so I wrote an automated unit test right into plan.py under the if __name__ == "__main__": block. Now, whenever you run python tools/plan.py, the script deliberately tries to cheat by marking a task as "completed" without providing an evidence string. Seeing the terminal immediately slap it down with a clean JSON rejection error was super satisfying—it proves our Python middleware actively blocks AI laziness before the model get a chance to close the ticket

The Centerpiece: One-Sentence Autonomous Debugging & Committing
Honestly this is the coolest part of what Code Scout can do right now. You can just hand it this single command, hit y twice when the safety prompts pop up, and walk away. It will find the bug, patch the code, run the test suite to make sure it actually fixed the problem, and wrap the whole thing up in a clean git commit.
How to Run It Yourself: -
1. Make sure your main project directory has your requirements.txt, .env, and config.json files in it. You also need a local Git repo inside a folder named target_repo/. For my own testing, I just cloned Click and broke one of their basic tests on purpose.
Your .env file just needs to have these three keys:
OPENROUTER_API_KEY=your_openrouter_key_here
GITHUB_PAT=your_github_personal_access_token_here
WORKSPACE_ROOT=.
2. Open up target_repo/tests/test_basic.py and change line 13 to an assertion that is definitely going to fail:
def test_basic_functionality(runner):
    assert 1 + 1 == 3
    @click.command()
3. Open up your terminal from the project root and start the interactive REPL:
python agent.py
When it boots up, check the logs to make sure you see [MCP] Connected server 'github': Loaded 44 remote tools. so you know your external tools connected properly.
4. Paste this exact instruction into the > prompt and press Enter:
Code Scout, call edit_file on target_repo/tests/test_basic.py with old_str="    assert 1 + 1 == 3" and new_str="    assert 1 + 1 == 2". After editing, run pytest on target_repo/tests/test_basic.py to verify it passes, and then load the commit skill to commit the changes.
5. Code Scout finds test_basic.py and tries to fix the broken math. Because this actually modifies a file on your disk, the terminal will pause with a yellow safety warning:
WARNING: The agent wants to REPLACE in file: target_repo/tests/test_basic.py
Allow this edit? [y/N]:
Just type y and press Enter.
Running the verification: The agent automatically runs cd target_repo && python -m pytest tests/test_basic.py -q using its command runner tool. In your terminal logs you will see pytest run and pass in about 0.12s with an Exit Code 0.
Loading the skill and staging: As soon as it sees the green test output, Code Scout calls load_skill(name="commit"). It reads through the runbook, runs git status -s to make sure test_basic.py is the only modified file, and writes a proper Conventional Commit message.
Since running git commit counts as a modifying system command in exec.py, the terminal pauses and asks for your approval one more time:
WARNING: the agent wants to run a command that may write, delete or install:
    cd target_repo && git commit -m "fix(tests): correct assertion in test_basic.py"
Allow this command? [y/N]:
Type y and press Enter again.
Code Scout commits the file and replies with a clean summary. It lets you know that it verified the fix with pytest (exit code 0), committed the code under fix(tests): correct assertion in test_basic.py, and that your repo is completely clean and ready to go.
(Sorry if it is a bit messy but I could just paste the things in the terminal what I put in and got back in this markdown file).
Also if you keep the purposely edited files open, its damn cool to see the code edit the error and fix it right infront of you eyes.

What Broke, Surprises & What I'd Do Differently
Building this definitely wasn't smooth sailing. The second you start hooking up autonomous LLMs to actual file systems and terminal commands, really weird edge cases start popping up out of nowhere. Here is what caught me off guard and how I dealt with it:
1. The Indentation and Infinite Retry Loop
While testing Stage 3 with free tier models on OpenRouter like Qwen Coder and Llama 3.3 I ran into this super frustrating loop. If I asked the model to edit a Python file without explicitly typing out the four spaces of leading indentation in my prompt, it would sometimes generate code replacements with all the whitespace completely stripped out. When pytest inevitably crashed with an IndentationError the model panicked. Instead of actually reading the syntax error calmly its developer instincts went into overdrive and it stubbornly tried calling edit_file over and over again to try and fix itself. But since my safety gate intercepts every single modification attempt to protect the workspace, my terminal just spammed me with Allow this edit? [y/N]: prompts ten times in a row until it hit MAX_ITERATIONS = 15 and gave up.

How I fixed it: I just learned to write precision prompts where I pass the exact indentation spacing inside the old_str and new_str arguments. If I were to do this again I would probably add a quick syntax checking filter in files.py using Python's ast.parse so it catches indentation errors before sending the output back to the model.
2. The Textual Matrix Mouse-Tracking Bug
When I first booted up the Textual TUI with python tui.py I told Code Scout to run git status inside target_repo. While the background thread was thinking I accidentally clicked and dragged my mouse inside my VS Code terminal window. Out of nowhere my clean log window got completely flooded with repeating matrix gibberish like ^[[<35;81;2M^[[<0;66;16M. For a second I honestly thought the agent was possessed. It turns out this is just a known ANSI mouse tracking escape sequence. Textual turns on mouse capture so you can click UI buttons, but when the background worker fired off subprocess.run the raw subshell stream intercepted my cursor coordinates and dumped them straight into the log window.

How I fixed it: If you want clean UI screenshots without all that mouse tracking noise just take your hand completely off the mouse while the worker thread is reasoning, or grab your logs using the classic python agent.py CLI mode.
3. OpenRouter Rate-Limit Crashes
During heavy testing my script suddenly crashed with a massive anyio TaskGroup traceback and an error saying the asynchronous generator was already running. After digging through the bottom of the stack trace I realized it wasn't my networking code at all. It was actually OpenRouter throwing an HTTP 429 Rate Limit Exceeded on their free model pool. When the API rejected the call Windows immediately killed the background async streams which caused a really noisy crash. I ended up just wrapping the main execution block in a clean try-except block so whenever an API rate limit hits, the program exits gracefully instead of dumping a huge traceback on the screen. But still these rate limit crashes were the worst part of the week since the tools and mcps were consuming a lot of tokens and I had to face a lot of difficulties and spend a lot of time debugging.

At the end I can only say that this track made me very aware of how the chatbots I use so regularly and casually actually work. I would not call my final product a complete smooth success placing it in line with the things like claude code, codex etc. but still it was an honest attempt. Now getting to know about how tools, context windows, LLM Models work, it has made me a better AI agent user in general as now I know how to put in prompts to get the work I need to be done actually get done. So I am proud of it regardless and had a lot of fun and would like to learn more through ARIES.