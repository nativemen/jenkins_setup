FROM jenkins/jenkins:lts-jdk21

USER root

RUN apt-get update && apt-get install -y \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/jenkins_home/init.groovy.d && \
    chown -R jenkins:jenkins /var/jenkins_home/init.groovy.d

USER jenkins

RUN jenkins-plugin-cli --plugins \
    ssh-slaves:latest \
    credentials:latest \
    ssh-credentials:latest \
    matrix-auth:latest \
    workflow-aggregator:latest \
    warnings-ng:latest \
    htmlpublisher:latest \
    ansicolor:latest \
    pipeline-stage-view:latest \
    configuration-as-code:latest
