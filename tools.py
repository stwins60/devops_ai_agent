
from langchain.tools import tool
from langchain.chat_models import ChatOpenAI

llm = ChatOpenAI(model="gpt-4", temperature=0)

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
    return llm.predict(f"Suggest fixes for the following Jenkins build errors:\n{errors}")

@tool
def explain_yml(content: str) -> str:
    """Explains a CI/CD YAML file."""
    return llm.predict(f"Explain this Jenkins pipeline YAML file:\n{content}")

@tool
def check_tf_issues(tf_file: str) -> str:
    """Identifies common issues in Terraform files."""
    return llm.predict(f"Check for misconfigurations in this Terraform file:\n{tf_file}")

@tool
def generate_pr_text(fix_summary: str) -> str:
    """Creates GitHub PR content."""
    return llm.predict(f"Create a GitHub PR title and body for the following fix:\n{fix_summary}")

@tool
def summarize_log(log: str) -> str:
    """Gives a high-level summary of the log file."""
    return llm.predict(f"Summarize this Jenkins log:\n{log}")
