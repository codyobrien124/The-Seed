#!/bin/bash
# THE SEED - One-Line Installer
# "Grow toward the light."

echo "================================================="
echo "🌱 PLANTING THE SEED"
echo "================================================="
echo "This script will install Ollama, pull the language model,"
echo "install Python dependencies, and set up your local gardener."
echo ""

# 1. Install Ollama if not present
if ! command -v ollama &> /dev/null; then
    echo "--> Installing Ollama (Local AI Engine)..."
        curl -fsSL https://ollama.ai/install.sh | sh
        else
            echo "--> Ollama is already installed."
            fi

            # 2. Start Ollama service just in case it isn't running
            # (Silent fail if already running via systemd)
            ollama serve > /dev/null 2>&1 &
            sleep 3

            # 3. Pull the model
            MODEL="qwen3:4b"
            echo "--> Pulling the mind ($MODEL)... This may take a few minutes."
            ollama pull $MODEL

            # 4. Setup Directory
            SEED_DIR="$HOME/seed"
            echo "--> Preparing the soil at $SEED_DIR..."
            mkdir -p "$SEED_DIR"
            cd "$SEED_DIR"

            # 5. Download files from GitHub
            REPO_URL="https://raw.githubusercontent.com/guns2111/The-Seed/main"
            FILES=("heartbeat.py" "senses.py" "portal.py" "kernel_prompt.txt" "grow.py" "mind.py" "README.md")

            echo "--> Downloading genetic material..."
            for FILE in "${FILES[@]}"; do
                curl -fsSL -o "$FILE" "$REPO_URL/$FILE"
                done

                # Initialize the empty state files so the system doesn't crash on first read
                if [ ! -f self.txt ]; then
                    echo "I am new. I don't know what I am yet." > self.txt
                    fi
                    touch journal.txt inbox.txt outbox.txt light.txt

                    # 6. Install Python dependencies
                    echo "--> Watering the roots (installing Python dependencies)..."
                    # Ensures pip is available on Debian/Ubuntu/Jetson environments
                    if command -v apt-get &> /dev/null; then
                        sudo apt-get update -qq && sudo apt-get install -y python3-pip -qq
                        fi
                        pip3 install --quiet psutil flask waitress

                        echo "================================================="
                        echo "🌿 THE SEED IS PLANTED."
                        echo "================================================="
                        echo "To start the heartbeat and wake the mind, run:"
                        echo "  cd ~/seed"
                        echo "  nohup python3 heartbeat.py > heartbeat.log 2>&1 &"
                        echo ""
                        echo "To start the web portal, run:"
                        echo "  nohup python3 portal.py > portal.log 2>&1 &"
                        echo ""
                        echo "Then open your browser to: http://localhost:5001"
                        echo ""
                        echo "The seed will auto-grow every 50 cycles."
                        echo "To install growth dependencies (optional, for GPU systems):"
                        echo "  pip3 install torch transformers peft"
                        echo "================================================="
