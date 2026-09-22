#!/bin/zsh
# Runs anything inside the project venv with the sponsor keys loaded.
#   ./run.sh agent.py "who do I know here?"
#   ./run.sh -m brain.memory ingest
cd "$(dirname "$0")"
set -a
[ -f ~/.claude-secrets ] && . ~/.claude-secrets
[ -f .env ] && . ./.env   # zsh's `.` searches PATH for bare names, hence ./
set +a
export LLM_API_KEY="${LLM_API_KEY:-$OPENAI_API_KEY}"
unset ANTHROPIC_BASE_URL
export PYTHONPATH="$PWD:/Users/williamwang/Documents/personal-crm"
exec .venv/bin/python "$@"
