import asyncio
import time
import os
import logging
from functools import lru_cache

from fastapi import FastAPI, UploadFile
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from tools import (
    check_build_status, extract_error_lines, suggest_fixes, explain_yml,
    check_tf_issues, generate_pr_text, summarize_log, lint_python_files,
    check_dockerfile_security, scan_for_secrets, check_dependency_vulnerabilities,
    check_yaml_json_syntax, detect_slow_tests, extract_failed_tests,
    detect_deprecated_warnings
)

# Load .env variables
load_dotenv()
OPEN_AI_API_KEY = os.getenv("OPENAI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = "."
EXCLUDED_DIRS = {'.git', 'venv', '__pycache__', 'node_modules'}

# All tools
tools = [
    check_build_status, extract_error_lines, suggest_fixes, explain_yml,
    check_tf_issues, generate_pr_text, summarize_log, lint_python_files,
    check_dockerfile_security, scan_for_secrets, check_dependency_vulnerabilities,
    check_yaml_json_syntax, detect_slow_tests, extract_failed_tests,
    detect_deprecated_warnings
]

# Validate OpenAI key
def is_valid_openai_key(key: str) -> bool:
    return key and not key.startswith("your_ope")

# Cached agent
@lru_cache()
def get_agent():
    """Initialize and cache the LangChain agent with error handling for tool parsing."""
    if is_valid_openai_key(OPEN_AI_API_KEY):
        try:
            llm = ChatOpenAI(model="gpt-4", temperature=0, openai_api_key=OPEN_AI_API_KEY)
            return initialize_agent(
                tools=tools,
                llm=llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True  # <-- important
            )
        except Exception as e:
            logger.warning(f"⚠️ OpenAI failed: {e}")
    if OLLAMA_BASE_URL:
        try:
            llm = ChatOllama(model="llama3.2", base_url=OLLAMA_BASE_URL, temperature=0)
            return initialize_agent(
                tools=tools,
                llm=llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True  # <-- important
            )
        except Exception as e:
            logger.error(f"⚠️ Ollama failed: {e}")
    raise RuntimeError("❌ No valid LLM available")

# FastAPI app
app = FastAPI(
    title="Jenkins AI Analyzer",
    description="Analyze logs and config files using LLM-powered DevOps tools.",
    version="1.0.0"
)

# HTML Formatter
def format_html_report(tool_results, summary):
    def format_llm_output(result):
        if isinstance(result, dict) and "content" in result:
            content = result.get("content", "").strip()
            model = result.get("response_metadata", {}).get("model_name", "Unknown")
            input_tokens = result.get("usage_metadata", {}).get("input_tokens", 0)
            output_tokens = result.get("usage_metadata", {}).get("output_tokens", 0)
            total_tokens = result.get("usage_metadata", {}).get("total_tokens", 0)
            return f"""
                <div>
                    <p><strong>Model:</strong> {model}</p>
                    <p><strong>Tokens Used:</strong> input={input_tokens}, output={output_tokens}, total={total_tokens}</p>
                    <pre>{content}</pre>
                </div>
            """
        elif isinstance(result, str):
            return f"<pre>{result.strip()}</pre>"
        else:
            return f"<pre>{str(result).strip()}</pre>"

    html = [
        '<html><head><style>',
        'body { font-family: Arial, sans-serif; }',
        'h2, h3 { color: #333; }',
        'table { border-collapse: collapse; width: 100%; }',
        'th, td { border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }',
        'th { background-color: #f2f2f2; }',
        'pre { white-space: pre-wrap; word-break: break-word; font-size: 14px; }',
        '</style></head><body>'
    ]

    html.append('<h2>🤖 AI Agent Analysis</h2>')
    html.append('<h3>Summary</h3>')
    html.append(format_llm_output(summary))

    html.append('<h3>Tool Results</h3>')
    html.append('<table><tr><th>Tool</th><th>Result</th></tr>')
    for tool, result in tool_results.items():
        html.append(f'<tr><td><b>{tool}</b></td><td>{format_llm_output(result)}</td></tr>')
    html.append('</table></body></html>')

    return '\n'.join(html)

# Test endpoint
@app.get("/test")
def test_agent():
    try:
        agent = get_agent()
        result = agent.run("What is 2 + 2?")
        return {"response": result}
    except Exception as e:
        logger.exception("Agent test failed")
        return {"error": str(e)}

# Log analysis endpoint
@app.post("/analyze/", response_class=HTMLResponse)
async def analyze(log: UploadFile):
    start = time.time()
    log_content = await log.read()
    decoded_log = log_content.decode(errors="ignore")
    agent = get_agent()
    tool_results = {}

    async def run_tool(tool, args):
        try:
            return await asyncio.to_thread(tool.invoke, args)
        except Exception as e:
            return f"Error: {e}"

    # Run log-based tools
    log_tasks = {
        "check_build_status": run_tool(check_build_status, {"log": decoded_log}),
        "extract_error_lines": run_tool(extract_error_lines, {"log": decoded_log}),
        "summarize_log": run_tool(summarize_log, {"log": decoded_log}),
        "explain_yml": run_tool(explain_yml, {"content": decoded_log}),
        "check_tf_issues": run_tool(check_tf_issues, {"tf_file": decoded_log}),
        "detect_slow_tests": run_tool(detect_slow_tests, {"log": decoded_log}),
        "extract_failed_tests": run_tool(extract_failed_tests, {"log": decoded_log}),
        "detect_deprecated_warnings": run_tool(detect_deprecated_warnings, {"log": decoded_log}),
    }
    log_results = await asyncio.gather(*log_tasks.values())
    tool_results.update(dict(zip(log_tasks.keys(), log_results)))

    # LLM-based follow-ups
    errors = tool_results.get("extract_error_lines", "")
    fix_summary = await run_tool(suggest_fixes, {"errors": errors})
    tool_results["suggest_fixes"] = fix_summary

    pr_text = await run_tool(generate_pr_text, {"fix_summary": fix_summary if isinstance(fix_summary, str) else ""})
    tool_results["generate_pr_text"] = pr_text

    # Directory-based tools
    dir_tasks = {
        "lint_python_files": run_tool(lint_python_files, {"root_dir": PROJECT_ROOT}),
        "check_dockerfile_security": run_tool(check_dockerfile_security, {"root_dir": PROJECT_ROOT}),
        "scan_for_secrets": run_tool(scan_for_secrets, {"root_dir": PROJECT_ROOT}),
        "check_dependency_vulnerabilities": run_tool(check_dependency_vulnerabilities, {"root_dir": PROJECT_ROOT}),
        "check_yaml_json_syntax": run_tool(check_yaml_json_syntax, {"root_dir": PROJECT_ROOT}),
    }
    dir_results = await asyncio.gather(*dir_tasks.values())
    tool_results.update(dict(zip(dir_tasks.keys(), dir_results)))

    try:
        summary_result = await asyncio.to_thread(agent.run, f"Given the following tool results, provide a detailed analysis and suggest a fix:\n{tool_results}")
        summary = {
            "content": str(summary_result),
            "response_metadata": getattr(summary_result, "response_metadata", {}),
            "usage_metadata": getattr(summary_result, "usage_metadata", {})
        }
    except Exception as e:
        summary = {"content": f"LLM summarization failed: {e}"}

    tool_results["analysis_time"] = f"{time.time() - start:.2f} seconds"
    return format_html_report(tool_results, summary)
