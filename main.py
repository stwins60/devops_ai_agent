
from fastapi import FastAPI, UploadFile
from tools import (
    check_build_status, extract_error_lines,
    suggest_fixes, explain_yml,
    check_tf_issues, generate_pr_text,
    summarize_log,
    lint_python_files, check_dockerfile_security,
    scan_for_secrets, check_dependency_vulnerabilities,
    check_yaml_json_syntax
)
# from langchain.chat_models import ChatOpenAI
from langchain_community.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain_ollama import ChatOllama
import os
from dotenv import load_dotenv

load_dotenv()

OPEN_AI_API_KEY = os.getenv("OPENAI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")

llm = ChatOpenAI(model="gpt-4", temperature=0, openai_api_key=OPEN_AI_API_KEY) if OPEN_AI_API_KEY else None
ollama = ChatOllama(model="llama3.2", base_url=OLLAMA_BASE_URL, temperature=0) if OLLAMA_BASE_URL else None


tools = [
    check_build_status,
    extract_error_lines,
    suggest_fixes,
    explain_yml,
    check_tf_issues,
    generate_pr_text,
    summarize_log,
    lint_python_files,
    check_dockerfile_security,
    scan_for_secrets,
    check_dependency_vulnerabilities,
    check_yaml_json_syntax
]


# Always try OpenAI first, fallback to Ollama if OpenAI fails
def get_agent():
    if llm:
        try:
            # Test OpenAI LLM
            # _ = llm.predict("Hello")
            return initialize_agent(
                tools=tools,
                llm=llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True
            )
        except Exception:
            pass
    if ollama:
        return initialize_agent(
            tools=tools,
            llm=ollama,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )
    raise RuntimeError("No LLM available.")

app = FastAPI()

@app.post("/analyze/")
async def analyze(log: UploadFile):
    log_content = await log.read()
    decoded_log = log_content.decode()
    # Always get a fresh agent, so fallback works per request
    try:
        agent = get_agent()
        result = agent.run(f"Analyze this Jenkins build log and suggest a fix:\n{decoded_log}")
    except Exception as e:
        # Try Ollama directly if OpenAI agent fails
        if ollama:
            try:
                agent = initialize_agent(
                    tools=tools,
                    llm=ollama,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    verbose=True
                )
                result = agent.run(f"Analyze this Jenkins build log and suggest a fix:\n{decoded_log}")
            except Exception as e2:
                return {"result": f"Both OpenAI and Ollama failed: {e2}"}
        else:
            return {"result": f"No LLM available: {e}"}
    return {"result": result}
