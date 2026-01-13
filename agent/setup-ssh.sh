#!/bin/bash
set -e

if [ -f /proc/sys/kernel/core_pattern ]; then
    echo '/tmp/cores/core.%e.%p' > /proc/sys/kernel/core_pattern || true
fi

PUB_KEY_PATH="/master_data/agent_pub_key.txt"

echo "--> [Agent] Waiting for Master public key..."
while [ ! -f "$PUB_KEY_PATH" ]; do sleep 2; done

# Inject public key
# mkdir -p /home/jenkins/.ssh
# cat "$PUB_KEY_PATH" > /home/jenkins/.ssh/authorized_keys

# Fix permissions
# chown -R jenkins:jenkins /home/jenkins/.ssh
# chmod 700 /home/jenkins/.ssh
# chmod 600 /home/jenkins/.ssh/authorized_keys

# Core optimization: leverage official environment variables instead of manually writing authorized_keys
# This allows official entrypoint script to handle complex SSHD configuration and permissions
export JENKINS_AGENT_SSH_PUBKEY=$(cat "$PUB_KEY_PATH")

echo "--> [Agent] Public key injection complete, starting SSHD..."
exec setup-sshd
