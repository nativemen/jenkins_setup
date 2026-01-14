/* groovylint-disable CompileStatic */

String getFileName(String path) {
    return path.split('/').last()
}

void verifyAgent() {
    String nodeName = env.NODE_NAME
    echo "Current Running Node: ${nodeName}"
    if (nodeName == 'master') {
        error('Error: Running on Master! Check Label configuration.')
    }
}

void cleanupOldArtifacts() {
    echo '--- Cleaning up old cores and reports ---'
    sh 'rm -rf /tmp/cores/*'
}

void compileSources() {
    sh '''
        cd /home/jenkins/codes
        for f in *.c; do
            echo "Compiling $f..."
            filename=$(basename "$f" .c)
            gcc -g "$f" -o /tmp/cores/"$filename"
        done
    '''
}

void testExecutable(String exePath) {
    String fileName = getFileName(exePath)
    int exitCode = sh(
        script: "ulimit -c unlimited && './${fileName}'",
        returnStatus: true
    )

    if (exitCode != 0) {
        echo "Crash Detected in ${fileName}! Starting diagnosis..."
        String diagScript = '/home/jenkins/tasks/diagnose-crash.sh'
        sh "bash '${diagScript}' '/tmp/cores/${fileName}'"
    } else {
        echo "Starting: ${fileName}"
    }
}

Map<String, Closure> setupParallelExecutionStages(List<String> executables) {
    Map<String, Closure> branches = [:]
    executables.each { String exePath ->
        String fileName = getFileName(exePath)
        branches[fileName] = {
            stage("Test: ${fileName}") {
                // groovylint-disable-next-line InsecureRandom
                int sleepTime = (Math.random() * 5).toInteger() + 1
                sleep sleepTime
                dir('/tmp/cores') {
                    testExecutable(exePath)
                }
            }
        }
    }
    return branches
}

void archiveReports() {
    echo '--- Copying reports to Workspace for archiving ---'
    sh 'cp /tmp/cores/*.html /tmp/cores/*.txt . 2>/dev/null || true'
    archiveArtifacts(
        artifacts: '*.html, *.txt',
        allowEmptyArchive: true
    )
}

pipeline {
    agent { label 'linux' }

    stages {
        stage('Verify Agent') {
            steps {
                script {
                    verifyAgent()
                }
            }
        }

        stage('Initial Cleanup') {
            steps {
                script {
                    cleanupOldArtifacts()
                }
            }
        }

        stage('Recursive Build') {
            steps {
                script {
                    compileSources()
                }
            }
        }

        stage('Parallel Execution & Analysis') {
            steps {
                script {
                    String findCmd = 'find /tmp/cores -maxdepth 1 -executable -type f'
                    List<String> executables = (
                        sh(
                            script: findCmd,
                            returnStdout: true
                        ).trim().split('\n')
                    ) as List
                    Map<String, Closure> branches = setupParallelExecutionStages(
                        executables
                    )
                    parallel branches
                }
            }
        }
    }

    post {
        always {
            script {
                archiveReports()
            }
        }
    }
}
