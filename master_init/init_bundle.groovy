import jenkins.model.*
import hudson.security.*
import hudson.model.*
import hudson.slaves.* // 显式导入 slaves 包以获取 RetentionStrategy
import jenkins.security.s2m.AdminWhitelistRule
import jenkins.install.InstallState
import jenkins.model.JenkinsLocationConfiguration // 新增导入：修复 URL 告警
import java.util.logging.Logger

def logger = Logger.getLogger('init_bundle.groovy')
def j = Jenkins.get()

/**
 * 【模块一：核心安全与身份验证】
 * 立即执行，用于锁定系统并创建初始管理员
 */
def setupCoreSecurity(j, logger) {
    logger.info('--> [核心安全] 正在启动基础加固与身份验证配置...')

    // 1. 开启 CSRF 防护
    if (j.getCrumbIssuer() == null) {
        j.setCrumbIssuer(new hudson.security.csrf.DefaultCrumbIssuer(true))
        logger.info('   [✓] 已启用 CSRF 保护')
    }

    // 2. 封杀不安全协议 (新增：彻底禁用 JNLP 1-4 协议)
    if (!j.getAgentProtocols().isEmpty()) {
        j.getAgentProtocols().clear()
        logger.info('   [✓] 已清空并禁用所有非加密 Agent 协议 (JNLP)')
    }

    // 3. 关闭不必要的 50000 端口 (新增：进一步收敛攻击面)
    if (j.getSlaveAgentPort() != -1) {
        j.setSlaveAgentPort(-1)
        logger.info('   [✓] 已彻底关闭 TCP Slave 代理端口 (50000)')
    }

    // 4. 自动配置 Jenkins URL (新增：修复网页红框告警)
    def jlc = JenkinsLocationConfiguration.get()
    if (!jlc.getUrl()) {
        jlc.setUrl('https://localhost/') // 根据您的 Nginx 环境设为 HTTPS
        jlc.setAdminAddress('admin@localhost')
        logger.info('   [✓] 已自动配置 Jenkins URL 消除系统告警')
    }

    // 5. 启用 Agent-to-Master 安全隔离
    try {
        def adminWhitelist = j.getDescriptorByType(AdminWhitelistRule.class)
        if (adminWhitelist != null) {
            adminWhitelist.setMasterKillSwitch(false)
            logger.info('   [✓] 已配置 Agent 访问隔离策略')
        } else {
            logger.info('   [-] 当前版本 AdminWhitelistRule 默认生效或已由系统托管')
        }
    } catch (Exception e) {
        logger.warning("   [!] 配置 AdminWhitelistRule 时跳过: ${e.message}")
    }

    // 6. 动态管理员密码生成与隐私保护
    if (!(j.getSecurityRealm() instanceof HudsonPrivateSecurityRealm)) {
        def dynamicPass = java.util.UUID.randomUUID().toString().replace('-', '')[0..23]

        def realm = new HudsonPrivateSecurityRealm(false)
        realm.createAccount('admin', dynamicPass)
        j.setSecurityRealm(realm)

        def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
        strategy.setAllowAnonymousRead(false) // 核心加固：严禁匿名访问
        j.setAuthorizationStrategy(strategy)

        try {
            def secretFile = new File('/run/secrets/tmp/initial_admin_password')
            secretFile.parentFile.mkdirs()
            secretFile.text = dynamicPass
            logger.info('   [✓] 动态密码已安全存入内存卷')
        } catch (Exception e) {
            logger.severe("   [!] 内存卷写入失败: ${e.message}。管理员密码为: ${dynamicPass}")
        }
    }

    // 7. 设置安装向导状态
    if (j.getInstallState() != InstallState.INITIAL_SETUP_COMPLETED) {
        j.setInstallState(InstallState.INITIAL_SETUP_COMPLETED)
        logger.info('   [✓] 已跳过初始化安装向导')
    }

    // 8. 禁用内置节点执行者
    if (j.getNumExecutors() != 0) {
        j.setNumExecutors(0)
        j.setMode(Node.Mode.EXCLUSIVE)
        logger.info('   [✓] 已将 Built-in Node 执行者数量设为 0')
    }

    j.save()
}

/**
 * 【模块二：插件依赖配置 (SSH/Credentials/Agent)】
 * 使用异步线程，避开插件尚未完全加载导致的异常
 */
def setupPluginDependentConfig() {
    Thread.start {
        def logger = Logger.getLogger('init_bundle_delayed.groovy')
        def j = Jenkins.get()

        // 等待 Jenkins 初始化完成
        while (j.getInitLevel() != hudson.init.InitMilestone.COMPLETED) {
            Thread.sleep(5000)
        }

        // 切换到系统权限执行敏感操作
        def ctx = hudson.security.ACL.as(hudson.security.ACL.SYSTEM)
        try {
            if (j.getPlugin('credentials') == null || j.getPlugin('ssh-slaves') == null) {
                logger.info('--> [延迟初始化信息] 插件未安装(Credentials/SSH Slaves)，跳过 Agent 配置。')
                return
            }

            logger.info('--> [延迟初始化] 插件已加载，开始高级配置...')

            def domainClass = Class.forName('com.cloudbees.plugins.credentials.domains.Domain')
            def sshKeyClass = Class.forName('com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey')
            def directSourceClass = Class.forName("com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey\$DirectEntryPrivateKeySource")
            def scopeClass = Class.forName('com.cloudbees.plugins.credentials.CredentialsScope')

            def credId = 'agent-ssh-key'
            def store = j.getExtensionList('com.cloudbees.plugins.credentials.SystemCredentialsProvider')[0].getStore()

            if (!store.getCredentials(domainClass.global()).find { it.id == credId }) {
                def keyFile = '/dev/shm/id_ed25519'
                ['ssh-keygen', '-t', 'ed25519', '-N', '', '-f', keyFile].execute().waitFor()

                def privKey = new File(keyFile).text
                def source = directSourceClass.getConstructor(String.class).newInstance(privKey)

                def credentials = sshKeyClass.getConstructor(
                    scopeClass, String.class, String.class,
                    Class.forName("com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey\$PrivateKeySource"),
                    String.class, String.class
                ).newInstance(scopeClass.GLOBAL, credId, 'jenkins', source, '', 'Auto-Generated-Ed25519')

                store.addCredentials(domainClass.global(), credentials)

                new File('/var/jenkins_home/agent_pub_key.txt').text = new File("${keyFile}.pub").text

                new File(keyFile).delete()
                new File("${keyFile}.pub").delete()
                logger.info('   [✓] Ed25519 凭据已注册')
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
                logger.info("   [✓] Agent 节点 'docker_agent' 已注册")
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
                    logger.info("   [✓] 已自动创建 Pipeline 任务: ${jobName}")

                    job.scheduleBuild2(2)
                    logger.info("   [✓] 已自动创建并触发 Pipeline 任务: ${jobName}")
                }
            }

            j.save()
            logger.info('--> [延迟初始化] 所有自动化任务执行完毕。')
        } catch (Exception e) {
            logger.severe('--> [延迟初始化失败] 错误详情: ' + e.toString())
        } finally {
            if (ctx != null) ctx.close()
    }
}
}

// --- 启动顺序执行 ---
setupCoreSecurity(j, logger)
setupPluginDependentConfig()
