#!/bin/bash
set -e

echo "--> [1/4] 删除旧的数据.."
# rm ./certs/jenkins.key ./certs/jenkins.crt
docker-compose down -v
sudo rm -rfv ~/jenkins_home/*
rm -rfv ./cores/*

echo "--> [2/4] 正在生成 ECDSA SSL 证书..."
mkdir -p ./certs

# 生成 SSL 证书
if [ ! -f "./certs/jenkins.key" ]; then
    # mkcert -install
    # mkcert -cert-file certs/jenkins.crt -key-file certs/jenkins.key localhost 127.0.0.1 jenkins-master
    # openssl ecparam -genkey -name prime256v1 -out ./certs/jenkins.key
    #openssl req -x509 -new -days 3650 -key ./certs/jenkins.key -out ./certs/jenkins.crt -subj "/C=CN/ST=BJ/O=Jenkins-Security/CN=localhost"
    chmod 600 ./certs/jenkins.key
    echo "    [✓] ECDSA 证书已生成"
fi

echo "--> [3/4] 检查目录权限..."
# 确保 Jenkins 有权读取挂载的初始化脚本
chmod 755 ./master

echo "--> [4/4] 启动全自动化集群..."
# 使用 --build 确保 Dockerfile 的任何修改生效
docker-compose up -d --build

echo "===================================================="
echo "  部署完成！"
echo "  1. 稍等 30 秒待 Jenkins 初始化"
echo "  2. 执行此命令获取动态密码："
echo "     docker exec jenkins-master cat /run/secrets/tmp/initial_admin_password"
echo "  3. 访问 https://localhost (使用 ECDSA 加密)"
echo "===================================================="
