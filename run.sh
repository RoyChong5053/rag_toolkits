#!/bin/bash
cd "$(dirname "$0")"

source venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null || true

mkdir -p input/raw input/clean input/photo output/rag output/ocr output/archive checkpoints intermediate logs

if [ $# -eq 0 ]; then
    raw_count=$(find input/raw -maxdepth 1 -type f 2>/dev/null | wc -l)
    photo_count=$(find input/photo -maxdepth 1 -type f 2>/dev/null | wc -l)
    echo ""
    echo "============================================================"
    echo "   RAG Toolkits v3.0"
    echo "============================================================"
    echo "   Input:"
    echo "     input/raw/    ($raw_count files) - put source docs here"
    echo "     input/clean/  preprocessed output (emoji-free, split)"
    echo "     input/photo/  ($photo_count files) - put images for OCR"
    echo "   Output:"
    echo "     output/rag/   RAG knowledge extraction results"
    echo "     output/ocr/   OCR text extraction results"
    echo "     output/archive/  auto-archived old task snapshots"
    echo "============================================================"
    echo ""
fi

python main.py "$@"
