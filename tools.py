
import os
import ast
import re
import yaml
import json
from langchain.tools import tool
from langchain_community.chat_models import ChatOpenAI
from langchain_ollama import ChatOllama
import dotenv

dotenv.load_dotenv()

OPEN_AI_API_KEY = os.getenv("OPENAI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")

llm = ChatOpenAI(model="gpt-4", temperature=0, openai_api_key=OPEN_AI_API_KEY) if OPEN_AI_API_KEY else None
ollama = ChatOllama(model="llama3.2", base_url=OLLAMA_BASE_URL, temperature=0) if OLLAMA_BASE_URL else None

def llm_predict(prompt: str) -> str:
    """Try OpenAI LLM, fallback to Ollama if OpenAI fails."""
    if llm:
        try:
            return llm.invoke(prompt)
        except Exception as e:
            # Try Ollama if OpenAI fails for any reason
            if ollama:
                try:
                    return ollama.invoke(prompt)
                except Exception as e2:
                    return f"Both OpenAI and Ollama failed: {e2}"
            return f"OpenAI failed: {e} and no Ollama available."
    elif ollama:
        try:
            return ollama.invoke(prompt)
        except Exception as e2:
            return f"Ollama failed: {e2}"
    return "No LLM available."

@tool
def check_build_status(log: str) -> str:
    """Checks if the Jenkins build failed."""
    keywords = ["BUILD FAILURE", "FAILURE", "Error:", "Exception", "Traceback"]
    if any(k in log for k in keywords):
        return "Build failed."
    return "Build passed."

@tool
def extract_error_lines(log: str) -> str:
    """Returns error-related lines from a Jenkins log."""
    lines = log.splitlines()
    errors = [line for line in lines if "error" in line.lower() or "exception" in line.lower()]
    return "\n".join(errors) if errors else "No errors found."

@tool
def suggest_fixes(errors: str) -> str:
    """Suggests fixes for the extracted errors using an LLM."""
    return llm_predict(f"Suggest fixes for the following Jenkins build errors:\n{errors}")

@tool
def explain_yml(content: str) -> str:
    """Explains a CI/CD YAML file."""
    return llm_predict(f"Explain this Jenkins pipeline YAML file:\n{content}")

@tool
def check_tf_issues(tf_file: str) -> str:
    """Identifies common issues in Terraform files."""
    return llm_predict(f"Check for misconfigurations in this Terraform file:\n{tf_file}")

@tool
def generate_pr_text(fix_summary: str) -> str:
    """Creates GitHub PR content."""
    return llm_predict(f"Create a GitHub PR title and body for the following fix:\n{fix_summary}")

@tool
def summarize_log(log: str) -> str:
    """Gives a high-level summary of the log file."""
    return llm_predict(f"Summarize this Jenkins log:\n{log}")

# --- New tools below ---

@tool
def lint_python_files(root_dir: str) -> str:
    """Recursively lints Python files in the given directory and subdirectories."""
    errors = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith('.py'):
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        source = f.read()
                    ast.parse(source, filename=fpath)
                except SyntaxError as e:
                    errors.append(f"{fpath}: {e}")
    return "\n".join(errors) if errors else "No Python syntax errors found."

@tool
def check_dockerfile_security(root_dir: str) -> str:
    """Checks Dockerfiles for common security issues."""
    issues = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.lower() == 'dockerfile':
                fpath = os.path.join(dirpath, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                if 'latest' in content:
                    issues.append(f"{fpath}: Avoid using 'latest' tag.")
                if 'add ' in content:
                    issues.append(f"{fpath}: Use COPY instead of ADD if possible.")
                if 'apt-get install' in content and '--no-install-recommends' not in content:
                    issues.append(f"{fpath}: Use '--no-install-recommends' with apt-get install.")
    return "\n".join(issues) if issues else "No obvious Dockerfile security issues found."

@tool
def scan_for_secrets(root_dir: str) -> str:
    """Scans files for hardcoded secrets or credentials."""
    secret_patterns = [
        r'AKIA[0-9A-Z]{16}',  # AWS Access Key ID
        r'(?i)secret[_-]?key\s*=\s*[\'"][^\'"]+[\'"]',
        r'(?i)password\s*=\s*[\'"][^\'"]+[\'"]',
        r'(?i)api[_-]?key\s*=\s*[\'"][^\'"]+[\'"]',
    ]
    findings = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith(('.py', '.env', '.yml', '.yaml', '.json', '.js')):
                fpath = os.path.join(dirpath, fname)
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                for pattern in secret_patterns:
                    for match in re.findall(pattern, content):
                        findings.append(f"{fpath}: Potential secret found: {match}")
    return "\n".join(findings) if findings else "No secrets found."

@tool
def check_dependency_vulnerabilities(root_dir: str) -> str:
    """Checks requirements.txt or package.json for insecure dependencies (basic check)."""
    findings = []
    # Python
    for dirpath, _, filenames in os.walk(root_dir):
        if 'requirements.txt' in filenames:
            fpath = os.path.join(dirpath, 'requirements.txt')
            with open(fpath, 'r', encoding='utf-8') as f:
                for line in f:
                    if '==' in line:
                        pkg, ver = line.strip().split('==')
                        if ver == '0.0.0':
                            findings.append(f"{fpath}: {pkg} version is 0.0.0 (placeholder or insecure).")
    # Node.js
    for dirpath, _, filenames in os.walk(root_dir):
        if 'package.json' in filenames:
            fpath = os.path.join(dirpath, 'package.json')
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for dep, ver in data.get('dependencies', {}).items():
                if ver in ['*', 'latest']:
                    findings.append(f"{fpath}: {dep} version is {ver} (not pinned).")
    return "\n".join(findings) if findings else "No obvious dependency vulnerabilities found."

@tool
def check_yaml_json_syntax(root_dir: str) -> str:
    """Checks YAML and JSON files for syntax/structural errors."""
    errors = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            if fname.endswith(('.yml', '.yaml')):
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        yaml.safe_load(f)
                except Exception as e:
                    errors.append(f"{fpath}: YAML error: {e}")
            elif fname.endswith('.json'):
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        json.load(f)
                except Exception as e:
                    errors.append(f"{fpath}: JSON error: {e}")
    return "\n".join(errors) if errors else "No YAML/JSON syntax errors found."
