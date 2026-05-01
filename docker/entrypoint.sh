#!/usr/bin/env bash
set -euo pipefail

PROMETHEUS_HOME="${PTG_HOME:-$HOME/.prometheus}"

if [ ! -f "$PROMETHEUS_HOME/config.yaml" ]; then
    echo "No config found, running ptg setup..."
    ptg setup
fi

exec ptg chat
