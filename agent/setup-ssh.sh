#!/bin/bash
set -e

if [ -f /proc/sys/kernel/core_pattern ]; then
	echo '/tmp/cores/core.%e.%p' >/proc/sys/kernel/core_pattern || true
fi

PUB_KEY_PATH="/master_data/agent_pub_key.txt"

echo "--> [Agent] 等待 Master 公钥..."
while [ ! -f "$PUB_KEY_PATH" ]; do sleep 2; done

# 注入公钥
# mkdir -p /home/jenkins/.ssh
# cat "$PUB_KEY_PATH" > /home/jenkins/.ssh/authorized_keys

# 权限修正
# chown -R jenkins:jenkins /home/jenkins/.ssh
# chmod 700 /home/jenkins/.ssh
# chmod 600 /home/jenkins/.ssh/authorized_keys

# 核心优化：利用官方环境变量，而不是手动写 authorized_keys
# 这样可以交由官方入口脚本处理复杂的 SSHD 配置和权限
export JENKINS_AGENT_SSH_PUBKEY=$(cat "$PUB_KEY_PATH")

echo "--> [Agent] 公钥注入完成，启动 SSHD..."
exec setup-sshd
