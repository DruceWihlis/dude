# Shared platform detection. Sourced by the timer scripts. DUDE_PLATFORM overrides it.

detect_platform() {
  if [[ -n "${DUDE_PLATFORM:-}" ]]; then
    printf '%s\n' "$DUDE_PLATFORM"
  elif [[ "$(uname -s)" == Darwin ]]; then
    printf 'macos\n'
  elif [[ -n "${WSL_DISTRO_NAME:-}" ]] || grep -qi microsoft /proc/version 2>/dev/null; then
    printf 'wsl\n'
  else
    printf 'linux\n'
  fi
}

readonly LAUNCHD_LABEL='dude.scan'
readonly WINDOWS_TASK='dude'
