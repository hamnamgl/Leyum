#!/bin/bash

echo "=============================="
echo "  LEYUM - Setup Starting..."
echo "=============================="

# Step 1 - Install Ollama
echo ""
echo "Step 1: Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh

# Step 2 - Pull Gemma 4 E4B model
echo ""
echo "Step 2: Pulling Gemma 4 E4B model (3.3GB - please wait)..."
ollama pull gemma3:4b

# Step 3 - Install Python dependencies
echo ""
echo "Step 3: Installing Python packages..."
pip install ollama gradio

# Step 4 - Create storage folders
echo ""
echo "Step 4: Creating storage folders..."
mkdir -p storage/sessions
mkdir -p storage/misconceptions
mkdir -p storage/schedules
mkdir -p storage/progress
mkdir -p storage/reports
mkdir -p demo/screenshots
mkdir -p demo/sample_reports

echo ""
echo "=============================="
echo "  LEYUM Setup Complete!"
echo "  Run: python app.py"
echo "  Then open: http://localhost:7860"
echo "=============================="
