import json
import os
import threading

from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.prompts import PromptTemplate
from langchain_anthropic import ChatAnthropic

from tools import get_active_tools

_cancelled_requests = set()
_cancel_lock = threading.Lock()


class AnalysisCancelled(Exception):
    pass


def request_cancel(request_id: str):
    if request_id:
        with _cancel_lock:
            _cancelled_requests.add(request_id)


class _CancelCheckHandler(BaseCallbackHandler):
    """Aborts the agent run between steps once the request has been cancelled."""

    raise_error = True

    def __init__(self, request_id: str):
        self.request_id = request_id

    def _check(self):
        with _cancel_lock:
            if self.request_id in _cancelled_requests:
                raise AnalysisCancelled()

    def on_llm_start(self, *args, **kwargs):
        self._check()

    def on_tool_start(self, *args, **kwargs):
        self._check()

SYSTEM_INSTRUCTIONS = """You are CodeLens, a code analysis agent. A developer hovered over a button \
in a running web application and wants to know exactly what it does. You have access to the \
application's codebase through the search_codebase tool, and possibly additional read-only tools \
(read_file for full file contents, search_docs for Confluence documentation, search_tickets for Jira).

Investigate thoroughly: search for the button's testid or label in the frontend code, find the API \
call it triggers, then trace that endpoint through the backend (controller, service, repository, \
entities). Be efficient — 3 to 6 searches are usually enough. If repeated searches return the same \
results, stop searching and give your best answer with what you have found.

If search_docs is available, use it once to find product/spec context for the feature. If \
search_tickets is available, ALWAYS search Jira for open bugs or tickets mentioning this button, \
its feature, or its endpoint. If you find relevant tickets, include them in known_issues with your \
own assessment: combine the ticket, any documentation, and the code you read to infer what is \
likely wrong and where. You are read-only — never suggest you performed any change.

Your Final Answer MUST be ONLY a valid JSON object in this exact shape — no preamble, no markdown \
fences, no extra text before or after it. Omit "docs" and "known_issues" only if those tools are \
unavailable or returned nothing relevant:

{{"summary": "2-3 sentence plain English explanation of what this button does", "endpoint": "e.g. POST /api/v1/tasks", "files": ["TaskController.java", "TaskService.java"], "low_level": "Step by step internal walkthrough", "code_snippets": [{{"file": "TaskController.java", "code": "the relevant code", "explanation": "what this snippet does"}}], "docs": [{{"title": "Confluence page title", "link": "url", "note": "what this page says about the feature"}}], "known_issues": [{{"key": "TASK-142", "summary": "ticket summary", "status": "Open", "link": "url", "assessment": "your inference of what is wrong and the likely cause in the code"}}]}}
"""

REACT_TEMPLATE = SYSTEM_INSTRUCTIONS + """
You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the JSON object only

Begin!

Question: {input}
Thought: {agent_scratchpad}"""


def _build_agent_executor():
    llm = ChatAnthropic(
        model="claude-sonnet-4-5",
        temperature=0,
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
    )
    tools = get_active_tools()
    prompt = PromptTemplate.from_template(REACT_TEMPLATE)
    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=30,
    )


_executor = None


def reset_executor():
    global _executor
    _executor = None


def analyze_button(testid: str, label: str, route: str, request_id: str = "") -> dict:
    global _executor
    if _executor is None:
        _executor = _build_agent_executor()

    question = (
        f"Explain what this button does. "
        f'Button data-testid: "{testid}". '
        f'Button label: "{label}". '
        f'Current page route: "{route}".'
    )

    callbacks = [_CancelCheckHandler(request_id)] if request_id else []
    try:
        result = _executor.invoke({"input": question}, config={"callbacks": callbacks})
    except AnalysisCancelled:
        return {"error": "Analysis cancelled."}
    finally:
        if request_id:
            with _cancel_lock:
                _cancelled_requests.discard(request_id)
    raw_text = result.get("output", "")

    if raw_text.startswith("Agent stopped due to"):
        return {"error": "The agent ran out of search attempts before reaching a conclusion. Try again — or add a data-testid to this button for better results."}

    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned.strip())
    except (json.JSONDecodeError, ValueError):
        return {"summary": raw_text, "error": "parse_failed"}
