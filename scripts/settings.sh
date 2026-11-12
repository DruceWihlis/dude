# Shared settings reader. Sourced by dude.sh and helper scripts.
#
# Reads only the requested key from .env so secrets such as TG_BOT_TOKEN never reach the
# environment of the scanning agent. Real environment variables take precedence.

setting() {
  local key="$1"
  local default="${2:-}"
  local env_file="${DUDE_ENV_FILE:-$DUDE_DIR/.env}"
  local value=''

  if [[ -n "${!key:-}" ]]; then
    printf '%s\n' "${!key}"
    return 0
  fi
  if [[ -r "$env_file" ]]; then
    value="$(sed -n -E "s/^[[:space:]]*(export[[:space:]]+)?${key}[[:space:]]*=[[:space:]]*//p" \
      "$env_file" | tail -n 1)"
    value="${value%"${value##*[![:space:]]}"}"
    value="${value#\"}"; value="${value%\"}"
    value="${value#\'}"; value="${value%\'}"
  fi
  printf '%s\n' "${value:-$default}"
}
