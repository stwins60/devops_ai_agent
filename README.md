# DevOps AI Agent

This project provides an AI-powered API for analyzing Jenkins build logs and suggesting fixes using FastAPI and LangChain. The agent runs all available tools on the log, then summarizes the results using an LLM (OpenAI or Ollama). The API returns a JSON response and a ready-to-use HTML report for Jenkins.

![alt text](images/image.png)


## Features
- Analyze Jenkins build logs and suggest fixes
- Extract error lines and summarize logs
- Explain CI/CD YAML files
- Identify Terraform issues
- Generate GitHub PR text
- Lint Python files and check Dockerfile security
- Scan for secrets and dependency vulnerabilities
- Check YAML/JSON syntax
- Support for OpenAI GPT-4 and Ollama models
- Easy-to-use REST API
- Returns a formatted HTML report for Jenkins
- Containerized with Docker for easy deployment


## Requirements

- Docker & Docker Compose (recommended)
- Or: Python 3.11+
- A `.env` file with the following variables:
  - `OPENAI_API_KEY` (for OpenAI GPT-4, optional if only using Ollama)
  - `OLLAMA_BASE_URL` (for Ollama, optional if only using OpenAI)


**Note:**
- The agent will automatically use OpenAI if available and valid, and will fall back to Ollama if OpenAI is unavailable or fails (including invalid API key).
- All tools are run directly on the log and project directory, and their results are summarized by the LLM.
- The API response includes a `html_report` field containing a ready-to-publish HTML report for Jenkins.

Example `.env`:
```env
OPENAI_API_KEY=your-openai-key
OLLAMA_BASE_URL=https://ollama.cloudaideveloper.com
```

## Quick Start (Docker Compose)


1. **Create a `.env` file** in the project directory (see above).
2. **Build and run the service:**
   ```bash
   docker-compose up --build
   ```
3. The API will be available at: [http://localhost:8000/analyze/](http://localhost:8000/analyze/)


## API Usage

- **POST** `/analyze/`
  - Upload a Jenkins build log file as form-data with the key `log`.
  - Returns a JSON response with:
    - `tool_results`: Output from all tools (per tool)
    - `summary`: LLM-generated summary and suggestions
    - `html_report`: Formatted HTML report for Jenkins

Example using `curl`:
```bash
curl -X POST "http://localhost:8000/analyze/" -F "log=@/path/to/jenkins.log"
```

### Jenkins Integration

In your Jenkins pipeline, after calling the API, extract the `html_report` from the JSON and write it to `ai-report.html`:

```sh
python3 -c "import sys, json; print(json.load(open('ai-output.json'))['html_report'])" > ai-report.html
```

Then publish `ai-report.html` using the Jenkins HTML Publisher plugin.

## Development (without Docker)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   uvicorn main:app --reload
   ```


## File Structure
- `main.py` - FastAPI app and agent logic
- `tools.py` - Custom LangChain tools for log and code analysis
- `requirements.txt` - Python dependencies
- `Dockerfile` & `docker-compose.yml` - Containerization setup
- `Jenkinsfile` - Example Jenkins pipeline integration

## License
MIT
