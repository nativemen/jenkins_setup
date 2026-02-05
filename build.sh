#!/bin/bash
set -e

# Step 1: Clean up old data
cleanup_old_data() {
    echo "--> [1/5] Cleaning up old data..."
    docker-compose down -v
    rm -rf ~/jenkins_home
    rm -rf ./cores
    echo "[✓] Old data cleaned"
}

# Step 2: Setup AI Provider Configuration
setup_ai_provider_config() {
    echo "--> [2/5] Setting up AI provider configuration..."

    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        echo "[*] Creating new .env file..."
        cat > .env << 'EOF'
# AI Provider Configuration (Unified Variables)
# Options: openai, anthropic, deepseek, google, xai, moonshot, alibaba, tencent
AI_PROVIDER=deepseek
AI_MODEL=deepseek-coder
API_KEY=
BASE_URL=
EOF
        echo "[✓] .env file created"
    else
        echo "⚠️  Found existing .env file"
        read -p "Do you want to update AI provider settings? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Keeping existing .env file, skipping AI provider configuration..."
            return
        fi
    fi

    echo ""
    echo "========================================"
    echo "  AI Provider Selection"
    echo "========================================"
    echo ""
    echo "Choose your AI provider for crash analysis:"
    echo ""
    echo "Tier 1 - Best for Programming:"
    echo "  1) OpenAI GPT-4o (Industry standard)"
    echo "  2) Claude (Anthropic - Excellent reasoning)"
    echo "  3) DeepSeek (Open source, popular in China)"
    echo ""
    echo "Tier 2 - Good for Programming:"
    echo "  4) Google Gemini (Large context)"
    echo "  5) xAI Grok (Growing ecosystem)"
    echo ""
    echo "Tier 3 - Chinese Providers:"
    echo "  6) Moonshot Kimi (Long context)"
    echo "  7) Alibaba Qwen (Enterprise support)"
    echo "  8) Tencent Hunyuan/Yuanbao (DeepSeek support)"
    echo ""
    read -p "Enter your choice [1-8]: " choice

    case $choice in
        1)
            echo "You selected: OpenAI GPT-4o"
            sed -i 's|^AI_PROVIDER=.*|AI_PROVIDER=openai|' .env
            sed -i 's|^AI_MODEL=.*|AI_MODEL=gpt-4o|' .env
            PROVIDER="OpenAI GPT-4o"
            echo "Available models: gpt-4o, gpt-4o-mini, gpt-4-turbo"
            ;;
        2)
            echo "You selected: Claude"
            sed -i 's|^AI_PROVIDER=.*|AI_PROVIDER=anthropic|' .env
            sed -i 's|^AI_MODEL=.*|AI_MODEL=claude-sonnet-4-20250514|' .env
            PROVIDER="Anthropic Claude"
            echo "Available models: claude-sonnet-4-20250514, claude-opus-4-20250514, claude-haiku-4-20250514"
            ;;
        3)
            echo "You selected: DeepSeek"
            sed -i 's|^AI_PROVIDER=.*|AI_PROVIDER=deepseek|' .env
            sed -i 's|^AI_MODEL=.*|AI_MODEL=deepseek-coder|' .env
            PROVIDER="DeepSeek"
            echo "Available models: deepseek-coder (推荐-代码分析), deepseek-v4, deepseek-r1-v2, deepseek-chat"
            ;;
        4)
            echo "You selected: Google Gemini"
            sed -i 's|^AI_PROVIDER=.*|AI_PROVIDER=google|' .env
            sed -i 's|^AI_MODEL=.*|AI_MODEL=gemini-2.5-flash-lite|' .env
            PROVIDER="Google Gemini"
            echo "Available models: gemini-2.5-flash-lite, gemini-2.5-flash, gemini-3-flash"
            ;;
        5)
            echo "You selected: xAI Grok"
            sed -i 's|^AI_PROVIDER=.*|AI_PROVIDER=xai|' .env
            sed -i 's|^AI_MODEL=.*|AI_MODEL=grok-2|' .env
            PROVIDER="xAI Grok"
            echo "Available models: grok-2, grok-2-vision"
            ;;
        6)
            echo "You selected: Moonshot Kimi"
            sed -i 's|^AI_PROVIDER=.*|AI_PROVIDER=moonshot|' .env
            sed -i 's|^AI_MODEL=.*|AI_MODEL=kimi-chat|' .env
            PROVIDER="Moonshot Kimi"
            echo "Available models: kimi-chat, moonshot-v1"
            ;;
        7)
            echo "You selected: Alibaba Qwen"
            sed -i 's|^AI_PROVIDER=.*|AI_PROVIDER=alibaba|' .env
            sed -i 's|^AI_MODEL=.*|AI_MODEL=qwen-plus|' .env
            PROVIDER="Alibaba Qwen"
            echo "Available models: qwen-plus, qwen-turbo, qwen-max"
            ;;
        8)
            echo "You selected: Tencent Hunyuan/Yuanbao"
            sed -i 's|^AI_PROVIDER=.*|AI_PROVIDER=tencent|' .env
            sed -i 's|^AI_MODEL=.*|AI_MODEL=hunyuan-pro|' .env
            PROVIDER="Tencent Hunyuan"
            echo "Available models: hunyuan-pro, hunyuan-standard"
            ;;
        *)
            echo "Invalid choice, defaulting to OpenAI GPT-4o"
            sed -i 's|^AI_PROVIDER=.*|AI_PROVIDER=openai|' .env
            sed -i 's|^AI_MODEL=.*|AI_MODEL=gpt-4o|' .env
            PROVIDER="OpenAI GPT-4o"
            ;;
    esac

    echo ""
    echo "========================================"
    echo "  API Key Configuration (Unified)"
    echo "========================================"
    echo ""
    echo "Provider: $PROVIDER"
    echo "API Endpoint: $API_URL"
    echo ""

    case $PROVIDER in
        "OpenAI")
            echo "Get API key at: https://platform.openai.com/api-keys"
            ;;
        "Anthropic Claude")
            echo "Get API key at: https://console.anthropic.com/"
            ;;
        "DeepSeek")
            echo "Get API key at: https://platform.deepseek.com/"
            ;;
        "Google Gemini")
            echo "Get API key at: https://makersuite.google.com/app/apikey"
            ;;
        "xAI Grok")
            echo "Get API key at: https://console.x.ai/"
            ;;
        "Moonshot Kimi")
            echo "Get API key at: https://www.moonshot.cn/"
            ;;
        "Alibaba Qwen")
            echo "Get API key at: https://dashscope.console.aliyun.com/"
            ;;
        "Tencent Hunyuan")
            echo "Get API key at: https://console.cloud.tencent.com/hunyuan"
            ;;
    esac
    echo ""
    read -p "Enter API key: " api_key

    if [ -z "$api_key" ]; then
        echo "⚠️  No API key provided, leaving as empty"
    else
        sed -i "s|^API_KEY=|API_KEY=${api_key}|g" .env
        echo "[✓] API key configured for $PROVIDER"
    fi

    echo ""
    echo "[✓] AI provider configuration completed"
}

# Step 3: Generate SSL certificate
generate_ssl_certificate() {
    echo "--> [3/5] Generating SSL certificate..."
    mkdir -p ./certs

    # Generate SSL Certificate
    if [ ! -f "./certs/jenkins.key" ]; then
        mkcert -install
        mkcert -cert-file certs/jenkins.crt -key-file certs/jenkins.key localhost 127.0.0.1 jenkins-master
        chmod 600 ./certs/jenkins.key
        echo "[✓] Certificate generated"
    fi
}

# Step 4: Verify directory permissions
verify_directory_permissions() {
    echo "--> [4/5] Verifying directory permissions..."
    mkdir -p ~/jenkins_home ./cores
    chmod 755 ./master
    echo "[✓] directory permissions verified"
}

# Step 5: Start automated cluster
start_cluster() {
    echo "--> [5/5] Starting automated cluster..."
    docker-compose up -d --build
    echo "[✓] Automated cluster started"
}

# Display deployment completion message
display_completion_message() {
    echo "===================================================="
    echo "  Deployment completed!"
    echo "  1. Wait ~30 seconds for Jenkins to initialize"
    echo "  2. Run this command to get the admin password:"
    echo "     docker exec jenkins-master cat /run/secrets/tmp/initial_admin_password"
    echo "  3. Visit https://localhost (ECDSA encrypted)"
    echo "===================================================="
}

# Main execution
cleanup_old_data
setup_ai_provider_config
generate_ssl_certificate
verify_directory_permissions
start_cluster
display_completion_message
