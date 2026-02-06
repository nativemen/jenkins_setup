#!/bin/bash
set -e

if [ -f /proc/sys/kernel/core_pattern ]; then
    echo '/tmp/cores/core.%e.%p' > /proc/sys/kernel/core_pattern || true
fi

HOST_KEY_FILE="/etc/ssh/ssh_host_ed25519_key.pub"
MASTER_HOST_KEY_PATH="/shared_keys/agent_host_key.txt"

if [ ! -f "$HOST_KEY_FILE" ]; then
    echo "--> [Agent] Generating SSH host key..."
    ssh-keygen -t ed25519 -f /etc/ssh/ssh_host_ed25519_key -N "" -C "jenkins-agent"
fi

if [ -f "$HOST_KEY_FILE" ]; then
    echo "--> [Agent] Sharing host key with master for verification..."
    cat "$HOST_KEY_FILE" > "$MASTER_HOST_KEY_PATH"
    chmod 644 "$MASTER_HOST_KEY_PATH"
    echo "--> [Agent] Host key shared at $MASTER_HOST_KEY_PATH"
fi

PUB_KEY_PATH="/master_data/agent_pub_key.txt"

echo "--> [Agent] Waiting for Master public key..."
while [ ! -f "$PUB_KEY_PATH" ]; do sleep 2; done

export JENKINS_AGENT_SSH_PUBKEY=$(cat "$PUB_KEY_PATH")

echo "--> [Agent] Public key injection complete, starting SSHD..."
exec setup-sshd
