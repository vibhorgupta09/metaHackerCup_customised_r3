# Multi-Agent Meta HackerCup Starter Kit (Fork)

This repo started from the public **Multi-Agent Meta HackerCup Starter Kit**. The upstream project demonstrated a minimal three-agent workflow (Tester → Brute → Optimal) driven entirely by Google Gemini models. This fork keeps the same spirit but expands the architecture significantly to better support noisy competitive-programming statements, richer validation, and manual auditing.

## 1. Original Workflow (Upstream)
- **Single pass pipeline:** TesterAgent generated 3–5 synthetic inputs, BruteAgent wrote a slow-but-correct solution, and OptimalAgent tried up to five efficient attempts. Each optimal attempt was compared directly with the brute output.
- **Google-only models:** All agents called `google:gemini-2.5-flash` (or other Gemini SKUs) via LangChain and relied on a single API key (`GOOGLE_API_KEY`).
- **Minimal bookkeeping:** Only the latest brute + optimal attempts and their outputs were stored under `workspace/`, and `results.json` captured a light summary for the HTML viewer.
- **Docs-first onboarding:** README/QUICKSTART/SETUP_GEMINI laid out install steps, Gemini key setup, and the “standard” usage flow (edit `PROBLEM.txt`, run `python main.py`, open `viewer.html`).

## 2. What Changed in This Fork
### Architecture & Agents
1. **SampleExtractorAgent (`agents/sample_agent.py`)** – Uses an LLM to scrape the official sample input/output directly from the problem statement. The orchestrator now refuses to continue if it can’t extract both blocks.
2. **Iterative brute forcing** – Instead of a single brute attempt, the orchestrator runs up to 12 tries at varying temperatures. Each attempt must pass official samples before the system even generates custom tests.
3. **Normalized tester prompting** – TesterAgent now copies the official sample first, then appends 8–10 extra cases. It enforces strict formatting (no blank lines, accurate `T` prefix) so downstream parsers are less likely to break.
4. **Temperature ladders everywhere** – Brute and optimal agents both receive per-attempt temperatures pulled from `config.yaml`, enabling controlled exploration.
5. **FinalJudgeAgent (`agents/final_judge_agent.py`)** – After all optimal attempts run, a final judging pass can group them, ask an LLM to pick winners, and write comparator bundles for human review.
6. **Model flexibility** – Every agent can target either OpenAI or Google providers by prefixing model names (e.g., `openai:gpt-5.1`). The fork currently defaults to OpenAI for all agents.

### Orchestrator Workflow
1. **Step 1 – Sample extraction**: saves `workspace/sample_input.txt` and `workspace/sample_output.txt`.
2. **Step 2 – Brute attempts**: loops until a brute solution compiles, runs on the official sample, and matches the sample output. Each attempt is logged (`workspace/brute_attempt_{n}.py` and metadata in `results.json`).
3. **Step 3 – Tester inputs**: once a sample-passing brute exists, generates normalized test inputs (`workspace/small_inputs.txt`).
4. **Step 4 – Brute execution**: runs the brute code on generated cases; failures feed detailed feedback back into the next brute attempt.
5. **Step 5 – Optimal attempts**: up to 12 guided retries with per-attempt feedback, heuristic validation that the response “looks like Python,” and individual artifacts (`workspace/optimal_attempt_{n}.py` + outputs). Accepted attempts are copied to `workspace/optimal_success_{k}.py`.
6. **Final judging + reporting**: optional final judge summary, enhanced `results.json` (sample IO, brute attempt log, judge verdicts), plus instructions to open the viewer via `python -m http.server 8000`.

### Tooling & Config
- `config.yaml` now contains both Google and OpenAI keys, per-stage temperature arrays, `max_brute_attempts`, final-judge toggles, and filenames for saved artifacts.
- `requirements.txt` gained `langchain-openai`, since LangChain’s OpenAI wrapper is now used alongside `langchain-google-genai`.
- `main.py` prints new metadata (number of brute attempts used, whether sample validation succeeded).

### Problem Statement
`PROBLEM.txt` now ships with Meta Hacker Cup 2024 Round 2’s **“Captcha Sorting”** bitstring problem instead of the original Kadane example. You can overwrite this file with any other statement as before.

### Documentation Status
The original README/QUICKSTART/SETUP_GEMINI/etc. were deleted in this fork. This document replaces them and explains both the upstream baseline and the new behavior. If you rely on Gemini-only instructions, reference the upstream repo or re-create similar docs tailored to your preferred provider.

## 3. Getting Started (Current Fork)
### Prerequisites
- Python 3.10+ recommended
- `pip install -r requirements.txt`
- API keys for any models you plan to call (`config.yaml` currently contains placeholder *real-looking* keys – **replace them with your own or load them from environment variables before publishing this repo**).

### Manage Secrets via `.env`
1. Copy the example file and fill in your keys:
   ```bash
   cp .env.example .env
   # edit .env to add GOOGLE_API_KEY / OPENAI_API_KEY
   ```
2. Values in `.env` are loaded automatically when `orchestrator.py` imports, so you usually don’t need to hardcode anything in `config.yaml`.
3. If an environment variable is missing, the orchestrator falls back to whatever is written inside `config.yaml`.

### Configure Models & Secrets
Edit `config.yaml` (leave API key fields blank unless you deliberately want file-based fallbacks):
```yaml
api_keys:
  google: ""  # defaults to GOOGLE_API_KEY from environment/.env
  openai: ""  # defaults to OPENAI_API_KEY from environment/.env

models:
  sample_agent: "openai:gpt-5.1"
  tester_agent: "openai:gpt-5.1"
  brute_agent: "openai:gpt-5.1"
  optimal_agent: "openai:gpt-5.1"
  final_judge_agent: "openai:gpt-5.1"

execution:
  max_brute_attempts: 12
  max_optimal_attempts: 12
  brute_temperatures: [...]
  optimal_temperatures: [...]
```
Any entry can be switched to `google:gemini-2.5-flash` or another supported ID if you prefer Gemini.

### Run the Solver
1. Fill `PROBLEM.txt` with the problem statement you want solved (current default is Captcha Sorting).
2. Execute:
   ```bash
   python main.py
   ```
3. Watch the CLI output. It now shows step-by-step progress plus per-attempt metadata.
4. To inspect the HTML report:
   ```bash
   python -m http.server 8000
   # open http://localhost:8000/viewer.html
   ```

## 4. Outputs & Artifacts
```
workspace/
├── sample_input.txt / sample_output.txt   # Extracted official samples
├── brute_attempt_{n}.py                   # Every brute attempt
├── brute.py / small_outputs.txt           # Latest validated brute code + outputs
├── small_inputs.txt                       # Normalized tester inputs
├── optimal_attempt_{n}.py / *_output.txt  # Optimal attempts + outputs
├── optimal_success_{k}.py                 # Any attempt that matched brute outputs
├── final_comparator.txt                   # Grouped winners for manual review (if judge enabled)
└── results.json                           # Rich metadata for viewer + auditing
```
The repo currently tracks many of these files; consider adding `workspace/` to `.gitignore` if you don’t want generated artifacts under version control.

## 5. Key Differences at a Glance
| Area | Upstream | This Fork |
| --- | --- | --- |
| Agents | Tester, Brute, Optimal | Adds SampleExtractor & FinalJudge; all agents configurable per provider |
| Model Provider | Google Gemini only | OpenAI or Google per agent |
| Brute Strategy | Single attempt | Up to 12 attempts with sample gating + feedback |
| Inputs | Generated tests only | Official sample extraction + normalized custom tests |
| Optimal Loop | Up to 5 attempts, immediate exit on success | Up to 12 attempts, saves every success, optional final judge |
| Metadata | Minimal | Detailed attempt logs, sample validation status, judge summaries |
| Docs | README + quickstart suite | Consolidated into this README |

## 6. Caveats
- **Secrets:** Never commit live API keys; the ones currently in `config.yaml` must be rotated or moved to environment variables before you publish this fork.
- **Workspace noise:** Generated files can be large. Clean or ignore them before committing.
- **LLM Cost/Quota:** Increasing brute/optimal attempts to 12x each dramatically increases API usage. Adjust `max_*_attempts` and temperature ladders to fit your quota.

## 7. License
This repo remains under the MIT License with the original copyright notice (`LICENSE`). You may add an additional notice documenting your modifications if desired.

---
Questions or ideas? Open an issue or continue extending the multi-agent pipeline to suit your Hacker Cup runs!
