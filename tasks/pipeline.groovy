pipeline {
    agent { label 'linux' }

    stages {
        stage('Verify Agent') {
            steps {
                script {
                    def nodeName = env.NODE_NAME
                    echo "Current Running Node: ${nodeName}"
                    if (nodeName == 'master') {
                        error('Error: Running on Master! Check Label configuration.')
                    }
                }
            }
        }

        stage('Initial Cleanup') {
            steps {
                script {
                    echo '--- Cleaning up old cores and reports ---'
                    // 清理旧的二进制、core文件和报告
                    sh 'rm -rf /tmp/cores/*'
                }
            }
        }

        stage('Recursive Build') {
            steps {
                script {
                    sh '''
                    cd /home/jenkins/codes
                    for f in *.c; do
                        echo "Compiling $f..."
                        gcc -g "$f" -o "/tmp/cores/${f%.c}"
                    done
                    '''
                }
            }
        }

        stage('Parallel Execution & Analysis') {
            steps {
                script {
                    def executables = sh(script: 'find /tmp/cores -maxdepth 1 -executable -type f', returnStdout: true).trim().split('\n')
                    def branches = [:]

                    executables.each { exePath ->
                        def fileName = exePath.split('/').last()
                        branches[fileName] = {
                            stage("Test: ${fileName}") {
                                def sleepTime = Math.abs(new Random().nextInt() % 5) + 1
                                sleep sleepTime

                                dir('/tmp/cores') {
                                    try {
                                        echo "Starting: ${fileName}"
                                        sh "ulimit -c unlimited && ./${fileName}"
                                    } catch (Exception e) {
                                        echo "💥 Crash Detected in ${fileName}! Starting diagnosis..."
                                        sh "bash /home/jenkins/tasks/diagnose-crash.sh /tmp/cores/${fileName}"
                                    }
                                }
                            }
                        }
                    }
                    parallel branches
                }
            }
        }
    }

    post {
        always {
            script {
                echo '--- Copying reports to Workspace for archiving ---'
                sh 'cp /tmp/cores/*.html /tmp/cores/*.txt . || echo "No reports found to copy"'
            }
            // 现在可以直接归档工作空间根目录下的文件了
            archiveArtifacts artifacts: '*.html, *.txt', allowEmptyArchive: true
        }
    }
}
