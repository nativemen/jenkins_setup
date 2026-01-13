import jenkins.model.*
import hudson.security.*
import hudson.model.*
import hudson.slaves.* // Explicitly import slaves package for RetentionStrategy
import jenkins.security.s2m.AdminWhitelistRule
import jenkins.install.InstallState
import jenkins.model.JenkinsLocationConfiguration // New import: fix URL alert
import java.util.logging.Logger

def logger = Logger.getLogger('init_bundle.groovy')
def j = Jenkins.get()

/**
 * Module One: Core Security & Authentication
 * Executed immediately to lock down the system and create initial admin
 */
def setupCoreSecurity(j, logger) {
    logger.info('--> [Core Security] Initializing hardening and authentication configuration...')

    // 1. Enable CSRF Protection
    if (j.getCrumbIssuer() == null) {
        try {
            def descriptor = hudson.security.csrf.DefaultCrumbIssuer.getDescriptor()
            if (descriptor != null) {
                j.setCrumbIssuer(descriptor.newInstance(null, true))
                logger.info('   [✓] CSRF protection enabled')
            } else {
                logger.info('   [!] CSRF descriptor not yet available at init time, will be handled by plugins')
            }
        } catch (Exception e) {
            logger.info("   [!] Skipping CSRF init (plugins may set it later): ${e.message}")
        }
    } else {
        logger.info('   [✓] CSRF protection already enabled')
    }

    // 2. Block Insecure Protocols (completely disable JNLP 1-4)
    if (!j.getAgentProtocols().isEmpty()) {
        j.getAgentProtocols().clear()
        logger.info('   [✓] Cleared and disabled all unencrypted agent protocols (JNLP)')
    }

    // 3. Close Unnecessary Port 50000 (further reduce attack surface)
    if (j.getSlaveAgentPort() != -1) {
        j.setSlaveAgentPort(-1)
        logger.info('   [✓] Completely closed TCP agent port (50000)')
    }

    // 4. Auto-configure Jenkins URL (fix red alert warnings on dashboard)
    def jlc = JenkinsLocationConfiguration.get()
    if (!jlc.getUrl()) {
        jlc.setUrl('https://localhost/') // Set to HTTPS for your Nginx environment
        jlc.setAdminAddress('admin@localhost')
        logger.info('   [✓] Auto-configured Jenkins URL to eliminate system alerts')
    }

    // 5. Enable Agent-to-Master Security Isolation
    try {
        def adminWhitelist = j.getDescriptorByType(AdminWhitelistRule.class)
        if (adminWhitelist != null) {
            adminWhitelist.setMasterKillSwitch(false)
            logger.info('   [✓] Configured agent access isolation policy')
        } else {
            logger.info('   [-] Current version has AdminWhitelistRule enabled by default or managed by system')
        }
    } catch (Exception e) {
        logger.warning("   [!] Skipped configuring AdminWhitelistRule: ${e.message}")
    }

    // 6. Dynamic Admin Password Generation & Privacy Protection
    if (!(j.getSecurityRealm() instanceof HudsonPrivateSecurityRealm)) {
        def dynamicPass = java.util.UUID.randomUUID().toString().replace('-', '')[0..23]

        def realm = new HudsonPrivateSecurityRealm(false)
        realm.createAccount('admin', dynamicPass)
        j.setSecurityRealm(realm)

        def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
        strategy.setAllowAnonymousRead(false) // Core hardening: strictly prohibit anonymous access
        j.setAuthorizationStrategy(strategy)

        try {
            def secretFile = new File('/run/secrets/tmp/initial_admin_password')
            secretFile.parentFile.mkdirs()
            secretFile.text = dynamicPass
            logger.info('   [✓] Dynamic password securely stored in tmpfs volume')
        } catch (Exception e) {
            logger.severe("   [!] Failed to write to tmpfs volume: ${e.message}. Admin password: ${dynamicPass}")
        }
    }

    // 7. Set Installation Wizard State
    if (j.getInstallState() != InstallState.INITIAL_SETUP_COMPLETED) {
        j.setInstallState(InstallState.INITIAL_SETUP_COMPLETED)
        logger.info('   [✓] Skipped initial setup wizard')
    }

    // 8. Disable Built-in Node Executors
    if (j.getNumExecutors() != 0) {
        j.setNumExecutors(0)
        j.setMode(Node.Mode.EXCLUSIVE)
        logger.info('   [✓] Set Built-in Node executor count to 0')
    }

    j.save()
}

/**
 * Module Two: Plugin Dependency Configuration (SSH/Credentials/Agent)
 * Use async threads to avoid exceptions caused by plugins not fully loaded
 */
def setupPluginDependentConfig() {
    Thread.start {
        def logger = Logger.getLogger('init_bundle_delayed.groovy')
        def j = Jenkins.get()

        // Wait for Jenkins initialization to complete
        while (j.getInitLevel() != hudson.init.InitMilestone.COMPLETED) {
            Thread.sleep(5000)
        }

        // Switch to system permissions for sensitive operations
        def ctx = hudson.security.ACL.as(hudson.security.ACL.SYSTEM)
        try {
            if (j.getPlugin('credentials') == null || j.getPlugin('ssh-slaves') == null) {
                logger.info('--> [Delayed Initialization Info] Required plugins not installed (Credentials/SSH Slaves), skipping agent configuration.')
                return
            }

            logger.info('--> [Delayed Initialization] Plugins loaded, starting advanced configuration...')

            def domainClass = Class.forName('com.cloudbees.plugins.credentials.domains.Domain')
            def sshKeyClass = Class.forName('com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey')
            def directSourceClass = Class.forName("com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey\$DirectEntryPrivateKeySource")
            def scopeClass = Class.forName('com.cloudbees.plugins.credentials.CredentialsScope')

            def credId = 'agent-ssh-key'
            def store = j.getExtensionList('com.cloudbees.plugins.credentials.SystemCredentialsProvider')[0].getStore()

            if (!store.getCredentials(domainClass.global()).find { it.id == credId }) {
                def keyFile = '/run/secrets/ssh_key'
                def keyExists = new File(keyFile).exists()

                if (!keyExists) {
                    logger.warning('   [!] SSH private key file not found at /run/secrets/ssh_key, generating temporary key')
                    def tempKeyFile = '/tmp/id_ed25519'
                    ['ssh-keygen', '-t', 'ed25519', '-N', '', '-f', tempKeyFile].execute().waitFor()
                    keyFile = tempKeyFile
                }

                def privKey = new File(keyFile).text.trim()
                def source = directSourceClass.getConstructor(String.class).newInstance(privKey)

                def credentials = sshKeyClass.getConstructor(
                    scopeClass, String.class, String.class,
                    Class.forName("com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey\$PrivateKeySource"),
                    String.class, String.class
                ).newInstance(scopeClass.GLOBAL, credId, 'jenkins', source, '', 'Auto-Generated-Ed25519')

                store.addCredentials(domainClass.global(), credentials)

                // Safely extract public key: extract from private key if it exists, otherwise from temp key file
                def pubKeyFile = keyExists ? '/run/secrets/ssh_key.pub' : '/tmp/id_ed25519.pub'
                if (new File(pubKeyFile).exists()) {
                    new File('/var/jenkins_home/agent_pub_key.txt').text = new File(pubKeyFile).text.trim()
                    new File(pubKeyFile).delete()
                }

                // Only delete temporarily generated keys; keys in /run/secrets are managed by Docker
                if (!keyExists) {
                    new File('/tmp/id_ed25519').delete()
                }
                logger.info('   [✓] Ed25519 credential registered')
        }

            if (j.getNode('docker_agent') == null) {
                def launcher = Class.forName('hudson.plugins.sshslaves.SSHLauncher')
                                    .getConstructor(String.class, int.class, String.class)
                                    .newInstance('jenkins-agent', 22, credId)

                launcher.setSshHostKeyVerificationStrategy(
                    Class.forName('hudson.plugins.sshslaves.verifiers.NonVerifyingKeyVerificationStrategy').newInstance()
                )

                def node = new hudson.slaves.DumbSlave(
                    'docker_agent', 'Docker Agent', '/home/jenkins', '2',
                    hudson.model.Node.Mode.EXCLUSIVE, 'linux', launcher,
                    hudson.slaves.RetentionStrategy.INSTANCE, []
                )
                j.addNode(node)
                logger.info("   [✓] Agent node 'docker_agent' registered")
            }

            def jobName = 'Coredump-Auto-Diagnostic'
            if (j.getItem(jobName) == null && j.getPlugin('workflow-job')) {
                def scriptFile = new File('/var/jenkins_home/tasks/pipeline.groovy')
                if (scriptFile.exists()) {
                    def job = j.createProject(Class.forName('org.jenkinsci.plugins.workflow.job.WorkflowJob'), jobName)
                    def flowDef = Class.forName('org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition')
                                       .getConstructor(String.class, boolean.class)
                                       .newInstance(scriptFile.text, true)
                    job.setDefinition(flowDef)
                    logger.info("   [✓] Auto-created Pipeline job: ${jobName}")

                    job.scheduleBuild2(2)
                    logger.info("   [✓] Auto-created and triggered Pipeline job: ${jobName}")
                }
            }

            j.save()
            logger.info('--> [Delayed Initialization] All automation tasks completed.')
        } catch (Exception e) {
            logger.severe('--> [Delayed Initialization Failed] Error details: ' + e.toString())
        } finally {
            if (ctx != null) ctx.close()
    }
}
}

// --- Execution order startup ---
setupCoreSecurity(j, logger)
setupPluginDependentConfig()
