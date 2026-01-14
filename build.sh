#!/bin/bash
set -e

# Step 1: Clean up old data
cleanup_old_data() {
    echo "--> [1/5] Cleaning up old data..."
    docker-compose down -v
    sudo rm -rf ~/jenkins_home
    rm -rf ./cores
    echo "[✓] Old data cleaned"
}

# Step 2: Setup Jenkins security configuration
setup_security_config() {
    echo "--> [2/5] Setting up Jenkins security configuration..."
    local should_setup_env=true

    if [ -f .env ]; then
        echo "⚠️  Found existing .env file"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Keeping existing .env file, skipping..."
            should_setup_env=false
        fi
    else
        echo "[*] Creating new .env file..."
    fi

    if [ "$should_setup_env" = true ]; then
        cp .env.example .env
        echo "[✓] .env file created"
        echo ""
        echo "Please enter your Gemini API key:"
        echo "Get one at: https://makersuite.google.com/app/apikey"
        echo ""
        read -p "Enter GEMINI_API_KEY: " api_key

        if [ -z "$api_key" ]; then
            echo "⚠️  No API key provided, using placeholder"
        else
            # Update .env file
            sed -i.bak "s|XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX|$api_key|g" .env
            rm -f .env.bak
            echo "[✓] API key configured"
        fi
    fi
}

# Step 3: Generate SSL certificate
generate_ssl_certificate() {
    echo "--> [3/5] Generating SSL certificate..."
    mkdir -p ./certs

    # Generate SSL Certificate
    if [ ! -f "./certs/jenkins.key" ]; then
        mkcert -install
        mkcert -cert-file certs/jenkins.crt -key-file certs/jenkins.key localhost 127.0.0.1 jenkins-master
        # openssl ecparam -genkey -name prime256v1 -out ./certs/jenkins.key
        # openssl req -x509 -new -days 3650 -key ./certs/jenkins.key -out ./certs/jenkins.crt -subj "/C=CN/ST=BJ/O=Jenkins-Security/CN=localhost"
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
    # Use --build to ensure any Dockerfile changes take effect
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
setup_security_config
generate_ssl_certificate
verify_directory_permissions
start_cluster
display_completion_message
