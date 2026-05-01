#!/bin/bash
set -e

DATASET_NAME="${1:-prometheus-agent/tblite-eval}"
OUTPUT_DIR="${2:-./outputs/tblite}"
CONFIG_NAME="${3:-default}"

mkdir -p "$OUTPUT_DIR"
mkdir -p logs

echo "=== TBLite Evaluation ==="
echo "Dataset: $DATASET_NAME"
echo "Output: $OUTPUT_DIR"
echo "Config: $CONFIG_NAME"

python -m atroposlib.run \
    --env_cls environments.benchmarks.tblite:TBLiteEnv \
    --config_name "$CONFIG_NAME" \
    --num_episodes 10 \
    --save_dir "$OUTPUT_DIR" \
    --log_dir logs/tblite \
    2>&1 | tee "$OUTPUT_DIR/eval.log"

echo "=== Evaluation complete ==="
echo "Results saved to $OUTPUT_DIR/eval.log"
