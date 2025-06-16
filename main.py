
from fastapi import FastAPI, UploadFile
from tools import (
    check_build_status, extract_error_lines,
    suggest_fixes, explain_yml,
    check_tf_issues, generate_pr_text,
    summarize_log
)
from langchain.chat_models import ChatOpenAI
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
    summarize_log
]

if not llm:
    agent = initialize_agent(
        tools=tools,
        llm=ollama,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
    )
else:
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
    )

app = FastAPI()

@app.post("/analyze/")
async def analyze(log: UploadFile):
    log_content = await log.read()
    decoded_log = log_content.decode()
    result = agent.run(f"Analyze this Jenkins build log and suggest a fix:\n{decoded_log}")
    return {"result": result}
