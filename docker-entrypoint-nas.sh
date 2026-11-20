#!/bin/sh
set -eu

CONFIG_DIR="${HOMEPAGE_CONFIG_DIR:-/app/config}"
DEFAULT_CONFIG_DIR="${HOMEPAGE_DEFAULT_CONFIG_DIR:-/opt/homepage-defaults/config}"
SYNC_DIR="${HOMEPAGE_SYNC_DIR:-/opt/repo-sync}"
UPSTREAM_ENTRYPOINT="${HOMEPAGE_UPSTREAM_ENTRYPOINT:-/usr/local/bin/docker-entrypoint.sh}"
SKIP_UPSTREAM_ENTRYPOINT="${SKIP_UPSTREAM_ENTRYPOINT:-false}"

AUTO_SYNC_GITHUB="${AUTO_SYNC_GITHUB:-false}"
GITHUB_REPO="${GITHUB_REPO:-https://github.com/Johntsai0320/homepage.git}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"

log_info() {
    printf '[nas-homepage] %s\n' "$*"
}

log_warn() {
    printf '[nas-homepage] WARN: %s\n' "$*" >&2
}

is_true() {
    case "${1:-}" in
        1|true|TRUE|True|yes|YES|Yes|on|ON|On) return 0 ;;
        *) return 1 ;;
    esac
}

validate_git_source() {
    repo_val="$1"
    branch_val="$2"

    [ -n "${repo_val}" ] && [ -n "${branch_val}" ] || return 1

    nl="$(printf '\n_')"
    nl="${nl%_}"
    cr="$(printf '\r')"
    tab="$(printf '\t')"

    case "${repo_val}" in
        -*|*ext::*|*\;*|*\|*|*\`*|*\$*|*" "*|*"${tab}"*|*"${nl}"*|*"${cr}"*)
            return 1
            ;;
    esac
    case "${repo_val}" in
        https://*|http://*|/*)
            ;;
        *)
            return 1
            ;;
    esac

    case "${branch_val}" in
        -*|.*|*..*|*/*/*|*\;*|*\|*|*\`*|*\$*|*" "*|*"${tab}"*|*"${nl}"*|*"${cr}"*)
            return 1
            ;;
    esac
    return 0
}

apply_file_ownership() {
    target_path="$1"
    puid="${PUID:-0}"
    pgid="${PGID:-0}"
    if [ "${puid}" != "0" ] && [ "$(id -u)" = "0" ]; then
        chown "${puid}:${pgid}" "${target_path}" 2>/dev/null || true
    fi
}

sync_github_configs() {
    if ! is_true "${AUTO_SYNC_GITHUB}"; then
        return 0
    fi
    if ! command -v git >/dev/null 2>&1; then
        log_warn "AUTO_SYNC_GITHUB=true but git is not installed; skipping sync."
        return 0
    fi
    if ! validate_git_source "${GITHUB_REPO}" "${GITHUB_BRANCH}"; then
        log_warn "Invalid GITHUB_REPO or GITHUB_BRANCH; skipping sync."
        return 0
    fi

    log_info "Syncing config templates from ${GITHUB_REPO} (${GITHUB_BRANCH})..."
    if [ -d "${SYNC_DIR}/.git" ]; then
        if ! (
            cd "${SYNC_DIR}" && \
            git -c core.hooksPath=/dev/null remote set-url origin -- "${GITHUB_REPO}" && \
            git -c core.hooksPath=/dev/null fetch --depth 1 origin -- "${GITHUB_BRANCH}" && \
            git -c core.hooksPath=/dev/null reset --hard FETCH_HEAD
        ); then
            log_warn "Git sync fetch failed; continuing with existing configuration."
            return 0
        fi
    else
        rm -rf "${SYNC_DIR}"
        if ! git -c core.hooksPath=/dev/null clone --depth 1 --branch "${GITHUB_BRANCH}" -- "${GITHUB_REPO}" "${SYNC_DIR}"; then
            log_warn "Git clone failed; continuing with existing configuration."
            return 0
        fi
    fi

    if [ -d "${SYNC_DIR}/config" ]; then
        mkdir -p "${CONFIG_DIR}"
        for src in "${SYNC_DIR}/config"/*.yaml; do
            [ -e "${src}" ] || continue
            dest="${CONFIG_DIR}/$(basename "${src}")"
            cp "${src}" "${dest}"
            apply_file_ownership "${dest}"
        done
        log_info "Synced YAML configs from GitHub repository."
    fi
}

seed_default_configs() {
    mkdir -p "${CONFIG_DIR}"
    if [ ! -d "${DEFAULT_CONFIG_DIR}" ]; then
        return 0
    fi

    for src in "${DEFAULT_CONFIG_DIR}"/*.yaml; do
        [ -e "${src}" ] || continue
        name="$(basename "${src}")"
        dest="${CONFIG_DIR}/${name}"
        if [ ! -e "${dest}" ]; then
            cp "${src}" "${dest}"
            apply_file_ownership "${dest}"
            log_info "Seeded default config: ${name}"
        fi
    done
}

sync_github_configs
seed_default_configs

if is_true "${SKIP_UPSTREAM_ENTRYPOINT}"; then
    exit 0
fi

exec "${UPSTREAM_ENTRYPOINT}" "$@"
