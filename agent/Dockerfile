FROM jenkins/ssh-agent:latest-jdk21

USER root

RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    gdb \
    python3 \
    python3-pip \
    python3-requests \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /tmp/cores && chmod 1777 /tmp/cores
RUN touch /etc/environment && chmod 666 /etc/environment
RUN mkdir -p /var/run/sshd

COPY setup-ssh.sh /usr/local/bin/setup-ssh.sh
RUN chmod +x /usr/local/bin/setup-ssh.sh
RUN /usr/bin/ssh-keygen -A

ENTRYPOINT ["/usr/local/bin/setup-ssh.sh"]
