import os
import ast
import re
import yaml
import json
import subprocess
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from dotenv import load_dotenv

load_dotenv()
OPEN_AI_API_KEY = os.getenv("OPENAI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")


def get_llm():
    """Initialize an LLM using OpenAI (if valid key is present) or fallback to Ollama."""
    if OPEN_AI_API_KEY and not OPEN_AI_API_KEY.startswith("your_ope"):
        try:
            return ChatOpenAI(model="gpt-4", temperature=0, openai_api_key=OPEN_AI_API_KEY)
        except Exception as e:
            print(f"OpenAI failed: {e}")
    if OLLAMA_BASE_URL:
        try:
            return ChatOllama(model="llama3.2", base_url=OLLAMA_BASE_URL, temperature=0)
        except Exception as e:
            print(f"Ollama failed: {e}")
    return None


llm = get_llm()


def llm_predict(prompt: str) -> dict:
    """Generate a structured LLM response with tokens and model metadata."""
    if llm:
        try:
            print(f"🤖 Prompt: {prompt}")
            result = llm.invoke(prompt)
            return {
                "content": result.content if hasattr(result, "content") else str(result),
                "response_metadata": getattr(result, "response_metadata", {}),
                "usage_metadata": getattr(result, "usage_metadata", {})
            }
        except Exception as e:
            return {
                "content": f"LLM failed: {e}",
                "response_metadata": {},
                "usage_metadata": {}
            }
    return {
        "content": "No LLM available.",
        "response_metadata": {},
        "usage_metadata": {}
    }


@tool
def check_build_status(log: str) -> str:
    """Detect if Jenkins log indicates build failure."""
    keywords = ["BUILD FAILURE", "FAILURE", "Error:", "Exception", "Traceback"]
    return "Build failed." if any(k in log for k in keywords) else "Build passed."


@tool
def extract_error_lines(log: str) -> str:
    """Extract error or exception lines from Jenkins log."""
    lines = log.splitlines()
    return "\n".join([l for l in lines if "error" in l.lower() or "exception" in l.lower()]) or "No errors found."


@tool
def suggest_fixes(errors: str) -> str:
    """Suggest fixes based on extracted Jenkins error lines using LLM."""
    return llm_predict(f"Suggest fixes for the following Jenkins build errors:\n{errors}")


@tool
def explain_yml(content: str) -> str:
    """Explain a Jenkins pipeline YAML configuration using LLM."""
    return llm_predict(f"Explain this Jenkins pipeline YAML file:\n{content}")


@tool
def check_tf_issues(tf_file: str) -> str:
    """Detect common Terraform misconfigurations using LLM."""
    return llm_predict(f"Check for misconfigurations in this Terraform file:\n{tf_file}")


@tool
def generate_pr_text(fix_summary: str) -> str:
    """Generate a GitHub PR title and body based on the provided fix summary."""
    return llm_predict(f"Create a GitHub PR title and body for the following fix:\n{fix_summary}")


@tool
def summarize_log(log: str) -> str:
    """Generate a human-readable summary of the provided Jenkins build log."""
    return llm_predict(f"Summarize this Jenkins log:\n{log}")

@tool
def detect_slow_tests(log: str) -> str:
    """Identify test cases that exceed 5 seconds from Jenkins log output."""
    slow_tests = []
    for line in log.splitlines():
        match = re.search(r"(\d+(\.\d+)?)s\s+->\s+([\w\.]+)", line)
        if match and float(match.group(1)) > 5.0:
            slow_tests.append(f"Slow test: {match.group(3)} took {match.group(1)}s")
    return "\n".join(slow_tests) or "No slow tests found."


@tool
def extract_failed_tests(log: str) -> str:
    """Extract failed test case names from Jenkins logs under 'Failed tests' section."""
    failed_tests = []
    capture = False
    for line in log.splitlines():
        if "Failed tests:" in line:
            capture = True
        elif capture and line.strip() == "":
            break
        elif capture:
            failed_tests.append(line.strip())
    return "\n".join(failed_tests) or "No failed tests found."


@tool
def detect_deprecated_warnings(log: str) -> str:
    """Identify lines in Jenkins logs that contain 'deprecated' warnings."""
    warnings = [line for line in log.splitlines() if "deprecated" in line.lower()]
    return "\n".join(warnings) or "No deprecated warnings found."


@tool
def lint_python_files(root_dir: str) -> str:
    """Recursively lint Python files for syntax errors in a given directory."""
    errors = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith(".py"):
                try:
                    with open(os.path.join(dirpath, fname), encoding="utf-8") as f:
                        ast.parse(f.read())
                except SyntaxError as e:
                    errors.append(f"{fname}: {e}")
    return "\n".join(errors) or "No Python syntax errors found."


@tool
def check_dockerfile_security(root_dir: str) -> str:
    """Check Dockerfiles for insecure patterns like 'latest' tags or unsafe commands."""
    issues = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.lower() == "dockerfile":
                with open(os.path.join(dirpath, fname), encoding="utf-8") as f:
                    content = f.read().lower()
                if "latest" in content:
                    issues.append(f"{fname}: Avoid using 'latest' tag.")
                if "add " in content:
                    issues.append(f"{fname}: Use COPY instead of ADD.")
                if "apt-get install" in content and "--no-install-recommends" not in content:
                    issues.append(f"{fname}: Use '--no-install-recommends'.")
    return "\n".join(issues) or "No Dockerfile issues found."


@tool
def scan_for_secrets(root_dir: str) -> str:
    """Scan for hardcoded secrets or API keys in common code and config files, skipping virtual environments."""
    patterns = [
        r'AKIA[0-9A-Z]{16}',
        r'(?i)secret[_-]?key\s*=\s*["\'][^"\']+["\']',
        r'(?i)password\s*=\s*["\'][^"\']+["\']',
        r'(?i)api[_-]?key\s*=\s*["\'][^"\']+["\']'
    ]
    EXCLUDED_DIRS = {'.git', '__pycache__', 'venv', '.venv', 'node_modules'}
    findings = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fname in filenames:
            if fname.endswith(('.py', '.env', '.yml', '.yaml', '.json', '.js')):
                path = os.path.join(dirpath, fname)
                try:
                    with open(path, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        for pattern in patterns:
                            for match in re.findall(pattern, content):
                                findings.append(f"{path}: {match}")
                except Exception as e:
                    findings.append(f"{path}: Error reading file - {e}")
    return "\n".join(findings) or "No secrets found."


@tool
def check_dependency_vulnerabilities(root_dir: str) -> str:
    """Check requirements.txt or package.json for unpinned or insecure versions."""
    findings = []
    for dirpath, _, filenames in os.walk(root_dir):
        if "requirements.txt" in filenames:
            with open(os.path.join(dirpath, "requirements.txt")) as f:
                for line in f:
                    if "==" in line and "0.0.0" in line:
                        findings.append(f"{line.strip()} looks insecure")
        if "package.json" in filenames:
            with open(os.path.join(dirpath, "package.json")) as f:
                data = json.load(f)
                for k, v in data.get("dependencies", {}).items():
                    if v in ["*", "latest"]:
                        findings.append(f"{k} version is not pinned: {v}")
    return "\n".join(findings) or "No obvious dependency issues."


@tool
def check_yaml_json_syntax(root_dir: str) -> str:
    """Validate syntax for all YAML and JSON files in the specified directory."""
    errors = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            path = os.path.join(dirpath, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    if fname.endswith((".yml", ".yaml")):
                        yaml.safe_load(f)
                    elif fname.endswith(".json"):
                        json.load(f)
            except Exception as e:
                errors.append(f"{path}: {e}")
    return "\n".join(errors) or "No YAML/JSON syntax errors."


@tool
def run_static_analysis(root_dir: str) -> str:
    """Run static analysis for multiple languages (Python, JavaScript, Go, Java, PHP, C/C++)."""
    EXCLUDED_DIRS = {'.git', '__pycache__', 'venv', '.venv', 'node_modules'}
    reports = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fname in filenames:
            path = os.path.join(dirpath, fname)

            try:
                if fname.endswith(".py"):
                    result = subprocess.run(["pylint", path], capture_output=True, text=True)
                    reports.append(f"{path} (Python):\n{result.stdout}")
                elif fname.endswith(".js"):
                    result = subprocess.run(["eslint", path], capture_output=True, text=True)
                    reports.append(f"{path} (JavaScript):\n{result.stdout}")
                elif fname.endswith(".go"):
                    result = subprocess.run(["golint", path], capture_output=True, text=True)
                    reports.append(f"{path} (Go):\n{result.stdout}")
                elif fname.endswith(".java"):
                    result = subprocess.run(["checkstyle", "-c", "/google_checks.xml", path], capture_output=True, text=True)
                    reports.append(f"{path} (Java):\n{result.stdout}")
                elif fname.endswith(".php"):
                    result = subprocess.run(["php", "-l", path], capture_output=True, text=True)
                    reports.append(f"{path} (PHP):\n{result.stdout}")
                elif fname.endswith(('.c', '.cpp')):
                    result = subprocess.run(["clang-tidy", path], capture_output=True, text=True)
                    reports.append(f"{path} (C/C++):\n{result.stdout}")
            except FileNotFoundError:
                reports.append(f"{path}: Required linter tool not found for extension {fname}")
            except Exception as e:
                reports.append(f"{path}: Error running analysis - {e}")

    return "\n\n".join(reports) or "No static analysis issues found."
