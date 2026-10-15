#!/usr/bin/env bash
set -euo pipefail

echo "==> Validando integridad de especificaciones SDD..."

for spec_dir in .specify/specs/*/; do
    if [ -d "$spec_dir" ]; then
        echo "Revisando: $spec_dir"
        [ -f "${spec_dir}spec.md" ] || { echo "Falta spec.md en $spec_dir"; exit 1; }
        [ -f "${spec_dir}plan.md" ] || { echo "Falta plan.md en $spec_dir"; exit 1; }
        [ -f "${spec_dir}tasks.md" ] || { echo "Falta tasks.md en $spec_dir"; exit 1; }
    fi
done

echo "==> Todas las especificaciones cumplen la estructura requerida (spec.md, plan.md, tasks.md)."
