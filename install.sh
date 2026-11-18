#!/usr/bin/env bash
# Bootstrap the tiny-web-code checkout on Ubuntu/Debian.
set -Eeuo pipefail

usage() {
    printf '%s\n' 'Usage: bash install.sh [--install-only] [--name PROFILE] [--with-web]' \
        'Installs missing dependencies and opens local chat on a terminal.' \
        '--with-web also sets up optional keyless web search (DDGS).'
}
fail() { printf 'Install failed: %s\n' "$*" >&2; exit 1; }
name=tiny-web-code
launch=true
with_web=false
while (( $# )); do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --install-only) launch=false; shift ;;
        --with-web) with_web=true; shift ;;
        --name) [[ $# -ge 2 ]] || fail '--name needs a profile name'; name=$2; shift 2 ;;
        *) usage >&2; fail "Unknown argument: $1" ;;
    esac
done
[[ $name =~ ^[a-z0-9][a-z0-9_-]*$ ]] || fail 'Use a lowercase profile name with letters, numbers, hyphens or underscores.'
[[ $EUID -ne 0 ]] || fail 'Run as your normal user, not with sudo. The installer requests sudo if needed.'
[[ $(uname -s) == Linux && -r /etc/os-release ]] || fail 'This installer supports Ubuntu and Debian only.'
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in ubuntu|debian) ;; *) fail 'This installer supports Ubuntu and Debian only.' ;; esac
case "$(uname -m)" in x86_64|aarch64) ;; *) fail 'An x86-64 or ARM64 machine is required.' ;; esac

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
[[ -f "$root/scripts/setup.py" && -f "$root/distribution.yaml" ]] || fail 'Extract the full tiny-web-code archive or clone the repo, then run its install.sh.'
export PATH="$HOME/.local/bin:$PATH"
packages=()
for package in ca-certificates curl git python3; do
    if ! dpkg -s "$package" 2>/dev/null | command awk '/^Status: install ok installed$/ {found=1} END {exit !found}'; then
        packages+=("$package")
    fi
done
if ! command -v ollama >/dev/null && ! command -v zstd >/dev/null; then
    packages+=(zstd)
fi
if (( ${#packages[@]} )); then
    command -v sudo >/dev/null || fail 'sudo is needed to install missing system packages.'
    printf 'Installing system packages: %s\n' "${packages[*]}"
    sudo apt-get update
    sudo apt-get install -y "${packages[@]}"
fi
# Use the OS interpreter, not a possibly stale Python from an activated venv.
/usr/bin/python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || fail 'This checkout requires system Python 3.10 or newer (e.g. Ubuntu 22.04+ or Debian 12+).'

scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
fetch_installer() {
    curl --disable --proto '=https' --proto-redir '=https' --fail --silent --show-error \
        --location --retry 2 --connect-timeout 15 --max-time 120 --output "$2" "$1"
}
if ! command -v hermes >/dev/null; then
    printf 'Installing Hermes Agent from Nous Research…\n'
    fetch_installer 'https://hermes-agent.nousresearch.com/install.sh' "$scratch/hermes.sh"
    bash "$scratch/hermes.sh" --non-interactive --channel stable --skip-browser --skip-computer-use
fi
hash -r
hermes profile install --help >/dev/null || fail 'The Hermes CLI cannot install profiles. Update Hermes Agent and retry.'

if ! command -v ollama >/dev/null; then
    command -v sudo >/dev/null || fail 'sudo is needed by the official Ollama installer.'
    printf 'Installing Ollama…\n'
    fetch_installer 'https://ollama.com/install.sh' "$scratch/ollama.sh"
    bash "$scratch/ollama.sh"
fi
hash -r
command -v ollama >/dev/null || fail 'The Ollama installer did not put ollama on PATH.'

export OLLAMA_HOST=http://127.0.0.1:11434
export NO_PROXY="${NO_PROXY:+$NO_PROXY,}127.0.0.1,localhost"
export no_proxy="${no_proxy:+$no_proxy,}127.0.0.1,localhost"
ready() { curl --disable --noproxy '*' -fsS --max-time 2 "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; }
if ! ready; then
    state="${XDG_STATE_HOME:-$HOME/.local/state}/tiny-web-code"
    mkdir -p -- "$state"
    printf 'Starting Ollama on localhost…\n'
    (umask 077; nohup ollama serve </dev/null >>"$state/ollama.log" 2>&1 &)
    for (( attempt=0; attempt<45; attempt++ )); do
        ready && break
        sleep 1
    done
    ready || fail "Ollama did not start. See $state/ollama.log."
fi

/usr/bin/python3 "$root/scripts/setup.py" --name "$name"
if $with_web; then
    printf 'Setting up keyless web search (DDGS)…\n'
    if ! { hermes -p "$name" tools post-setup ddgs &&
           hermes -p "$name" config set web.search_backend ddgs; }; then
        printf 'Warning: Web search setup failed. Local chat is still available.\n' >&2
    fi
fi
if $launch && [[ -t 0 && -t 1 ]]; then
    # Do not use exec: the EXIT trap removes the temporary installer files.
    hermes -p "$name" chat --cli
else
    printf 'To chat, run: hermes -p %s chat --cli\n' "$name"
fi
