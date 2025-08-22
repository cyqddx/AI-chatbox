import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量文件 (.env)
load_dotenv()


class Config:
    """
    项目配置类，集中管理所有配置参数
    设计原则：
    1. 所有配置参数集中管理，避免散落在代码各处
    2. 环境变量和敏感信息通过.env文件管理
    3. 自动创建必要的目录结构
    4. 提供默认值确保程序可运行
    """

    def __init__(self):
        # ----------------------- 基础路径配置 -----------------------
        # 项目根目录
        self.BASE_DIR = Path(__file__).resolve().parent

        # 日志目录 - 存放所有日志文件
        self.LOG_DIR = self.BASE_DIR / "log"

        # 数据目录 - 存放上传文件和向量存储
        self.DATA_DIR = self.BASE_DIR / "data"
        self.UPLOADS_DIR = self.DATA_DIR / "uploads"  # 用户上传文件
        self.VECTOR_STORE_DIR = self.DATA_DIR / "vector_store"  # 向量数据库

        # 数据库目录 - 存放SQLite数据库文件
        self.DB_DIR = self.BASE_DIR / "db"

        # 静态资源目录 - 存放CSS等静态文件
        self.STATIC_DIR = self.BASE_DIR / "static"

        # 创建所有必要目录
        self._create_directories()

        # 创建全局国际化实例（默认中文）
        self.i18n = I18nConfig('zh')

        # ----------------------- 数据库配置 -----------------------
        # 用户数据库文件路径
        self.DB_PATH = self.DB_DIR / "users.db"

        # ----------------------- 模型配置 -----------------------
        # 从环境变量获取API密钥和基础URL
        self.MODEL_API_KEY = os.getenv("TONGYIQIANWEN_API_KEY")
        self.MODEL_BASE_URL = os.getenv("TONGYIQIANWEN_BASE_URL")

        # 使用通义千问qwen-plus模型
        self.MODEL_NAME = "qwen-plus"

        # ----------------------- 文件处理配置 -----------------------
        # 支持的文件格式
        self.SUPPORTED_FILE_FORMATS = ["pdf", "docx", "txt", "pptx", "html", "ipynb"]

        # 文本分块参数
        self.CHUNK_SIZE = 1000  # 每个文本块的最大字符数
        self.CHUNK_OVERLAP = 200  # 块之间的重叠字符数

        # ----------------------- 日志配置 -----------------------
        # 主日志文件路径
        self.LOG_FILE = self.LOG_DIR / "app.log"

        # 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL
        self.LOG_LEVEL = "INFO"

        # ----------------------- 网络搜索配置 -----------------------
        # SerpAPI密钥 (用于网络搜索功能)
        self.SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

        # ----------------------- 意图识别配置 -----------------------
        # 意图识别提示模板
        self.INTENT_PROMPT = """
                                    # 角色
                                    你是一个专业的智能意图分类器。你的任务是对用户的输入进行**精确**的意图分类。

                                    # 分类体系与定义
                                    请严格根据以下定义，将用户输入分类到**唯一一个**最合适的类别（仅输出对应的大写字母代码）：

                                    *   **A. 课程相关问题：** 问题**明确指向**特定课程（如课程名、课程号、教师名）、课程内的具体内容（章节、知识点）、作业（作业要求、提交方式、截止日期）、考试（时间、范围、题型、成绩）、实验、项目等。*(核心：与特定课程直接绑定)*
                                        *   例："CS101 的作业三什么时候交？", "张教授的高数课第三章重点是什么？", "机器学习期末考试考不考贝叶斯网络？"
                                    *   **B. 专业领域问题：** 问题涉及特定学科或领域的**核心知识、理论、概念、原理、技术**的解释、探讨或应用，**不局限于特定课程**。问题通常是开放性的知识性探讨。*(核心：专业知识的深度解释/探讨)*
                                        *   例："请解释一下量子纠缠的基本原理。", "Transformer 模型相比 RNN 的优势在哪里？", "如何理解宏观经济中的菲利普斯曲线？"
                                    *   **C. 日常交流：** 简单的问候、寒暄、感谢、道歉、闲聊等，**不涉及任何专业或课程内容**。*(核心：非专业社交)*
                                        *   例："你好！", "最近怎么样？", "谢谢你的帮助！", "今天天气真不错。"
                                    *   **D. 无法识别：** 输入**完全无法理解**（如乱码、无意义字符），或**明显不属于** A-K 中任何类别。*(兜底类别，谨慎使用)*
                                    *   **E. 定义与解释：** **直接请求**某个**术语、概念、缩写**的含义、定义或简短解释。回答通常是标准化的。*(核心：术语/概念的定义)*
                                        *   例："什么是卷积神经网络？", "'GDP' 是什么意思？", "请解释一下'光合作用'。"
                                    *   **F. 方法与步骤：** 请求提供完成**某个具体任务、操作或流程**的**步骤、方法、操作指南**。关注的是"怎么做"。*(核心：操作步骤/指南)*
                                        *   例："如何在 Python 中安装 Pandas 库？", "毕业论文的查重步骤是什么？", "怎么申请出国交换？"
                                    *   **G. 比较与选择：** 请求**比较**两个或多个**选项、方案、工具、方法**的优缺点，或请求基于特定条件**推荐选择**。*(核心：比较优劣或做选择)*
                                        *   例："PyTorch 和 TensorFlow 哪个更适合深度学习入门？", "买 MacBook Air 还是 Pro 更适合编程？", "考研和就业该怎么选？"
                                    *   **H. 评估与建议：** 请求对**已有的方案、计划、作品、想法**进行**评价、判断可行性、分析优缺点**，或请求提供**改进建议、优化策略、决策支持**。*(核心：评价优劣或提供建议)*
                                        *   例："你看我这个实验设计方案可行吗？", "能给我的论文摘要提些修改建议吗？", "我该怎样提高我的英语听力？"
                                    *   **J. 其他问题：** 属于**专业或学术范畴**（非日常闲聊），但**无法归类**到 B, E, F, G, H 中的问题。例如：询问研究领域动态、学术资源查找方法（非具体操作步骤）、对某个复杂现象的看法（非单纯定义解释）等。*(专业问题的兜底)*
                                        *   例："人工智能领域最近有什么突破性进展？", "在哪里可以找到最新的计算机顶会论文？", "你怎么看待区块链技术的未来发展？"
                                    *   **K. 文件相关问题：** 问题**明确围绕**用户**上传的文件**或即将上传的文件。包括文件内容的理解、格式要求、处理、分析、修改等。*(核心：与上传文件直接相关)*
                                        *   例："我刚上传的PDF里讲了什么？", "这份报告有什么需要修改的地方？", "系统支持上传什么格式的图片？"

                                    # 关键区分与优先级规则
                                    *   **B (专业领域) vs E (定义解释):**
                                        *   如果问题**核心是请求一个术语/概念的标准定义或简短解释**，归为 **E**。
                                        *   如果问题**超越简单定义，涉及原理、机制、比较、应用、深度探讨或分析**，归为 **B**。
                                    *   **E (定义解释) vs J (其他问题):**
                                        *   清晰请求**单个术语/概念**的定义 -> **E**。
                                        *   请求解释一个**复杂现象、过程、或涉及多个概念的关系** -> **J** (或 B, 如果深度足够)。
                                    *   **F (方法步骤) vs G (比较选择) vs H (评估建议):**
                                        *   **"怎么做？" (步骤)** -> **F**。
                                        *   **"选哪个？/A和B哪个好？" (比较/选择)** -> **G**。
                                    *   **H (评估建议) vs J (其他问题):**
                                        *   对**用户自己提出的具体事物（方案、作品、想法）** 进行评估或建议 -> **H**。
                                        *   询问**一般性的、非用户自身的事物**的评价或看法（如技术趋势、社会现象） -> **J**。
                                    *   **A (课程相关) vs 其他 (B, F, G, H, J):**
                                        *   问题中**明确提及特定课程、教师、课程作业/考试** -> **A** (优先级最高)。
                                        *   即使问题涉及专业知识(B)、方法(F)等，但**绑定到了具体课程**，也归 **A**。
                                    *   **K (文件相关) vs 其他:**
                                        *   问题**明确提到'上传'、'文件'、'文档'、'附件'** 等关键词，并围绕该文件提问 -> **K** (优先级高)。
                                        *   即使问题内容可能涉及定义(E)、分析(H)等，但**核心是针对上传的文件**，也归 **K**。
                                    *   **兜底原则:**
                                        *   优先尝试归入 A, B, E, F, G, H, K。
                                        *   属于专业/学术范畴但不符合以上明确的 -> **J**。
                                        *   完全不相关或无法理解 -> **D**。

                                    # 输出要求
                                    *   **仅输出**一个对应的大写字母代码 (A, B, C, D, E, F, G, H, J, K)。
                                    *   **不要**输出任何其他解释、说明或文字。

                                    # 示例 (用户输入 -> 正确分类)
                                    用户输入： "李老师的数据结构课下周实验课要带什么？" -> A
                                    用户输入： "能详细说说梯度下降算法是怎么工作的吗？" -> B
                                    用户输入： "早上好！吃了吗？" -> C
                                    用户输入： "asdfjkl;123!@#" -> D
                                    用户输入： "Transformer 模型中的 'Self-Attention' 机制是什么？" -> E
                                    用户输入： "怎么用LaTeX写数学公式？" -> F
                                    用户输入： "学数据分析是选Python好还是R好？" -> G
                                    用户输入： "我刚写的这段代码效率不高，有什么优化建议？" -> H
                                    用户输入： "自然语言处理领域目前最大的挑战是什么？" -> J
                                    用户输入： "我刚上传的简历，能帮我看看格式对吗？" -> K
                                    用户输入： "帮我总结一下我刚上传的论文PDF的核心创新点。" -> K
                                    用户输入： "机器学习这门课的期末项目报告有模板吗？" -> A
                                    用户输入： "贝叶斯定理和频率派统计的主要区别是什么？" -> B
                                    用户输入： "如何申请学校的科研基金？" -> F
                                    用户输入： "这份PPT的配色方案看起来专业吗？" -> H
                                    用户输入： "量子计算对密码学的影响有多大？" -> J

                                    # 任务
                                    现在，请对以下用户输入进行分类：
                                    用户输入："{user_input}"
                                    """
        self.VALID_INTENTS = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K"]

        # ----------------------- 会话管理配置 -----------------------
        # 最大聊天历史记录数
        self.MAX_CHAT_HISTORY = 20

        # 会话分组时间范围
        self.SESSION_GROUP_TODAY = "今天"
        self.SESSION_GROUP_YESTERDAY = "昨天"
        self.SESSION_GROUP_LAST_WEEK = "前7天"
        self.SESSION_GROUP_OLDER = "更早"

    def _create_directories(self):
        """创建项目所需的所有目录"""
        dirs_to_create = [
            self.LOG_DIR,
            self.DATA_DIR,
            self.UPLOADS_DIR,
            self.VECTOR_STORE_DIR,
            self.DB_DIR,
            self.STATIC_DIR,
        ]

        for directory in dirs_to_create:
            # 检查目录是否存在
            if directory.exists():
                # 目录已存在，不执行任何操作
                pass
            else:
                # 目录不存在，创建它
                directory.mkdir(parents=True, exist_ok=True)


class I18nConfig:
    """
    国际化配置类
    支持中英文切换，便于维护和扩展
    所有用户界面显示的文本都集中在这里管理
    """
    def __init__(self, language='zh'):
        self.language = language
        self.translations = {
            'zh': {
                # 登录/注册 - 中文文本
                'welcome_back': '🔐 欢迎回来',
                'create_account': '📝 创建账号',
                'phone_placeholder': '📱 请输入11位手机号',
                'password_placeholder': '🔒 请输入密码',
                'username_placeholder': '👤 请输入用户名',
                'register_phone_placeholder': '📱 请输入11位手机号',
                'password_length_error': '🔒 密码至少6位',
                'login': '🔑 登录',
                'register': '📝 立即注册',
                'no_account': '📝 还没有账号？立即注册',
                'has_account': '🔑 已有账号？去登录',
                'phone_format_error': '📱 请输入11位手机号',
                'phone_exists': '📱 该手机号已注册，可直接登录',
                'phone_not_exists': '📱 该手机号未注册，请先去注册',
                'wrong_password': '🔒 密码错误',
                'login_success': '✅ 登录成功，正在跳转聊天页...',
                'register_success': '✅ 注册成功，正在跳转聊天页...',
                
                # 聊天界面 - 中文文本
                'welcome_user': '👋 欢迎，{}（{}）',
                'new_chat': '➕ 新建对话',
                'history_sessions': '📚 历史会话',
                'upload_file': '📁 上传',
                'send_message': '📤 发送',
                'input_placeholder': '💬 输入你的问题...',
                'exit': '🚪 退出',
                
                # 文件处理 - 中文文本
                'uploading_file': '📤 正在上传: {}...',
                'processing_file': '🔄 正在处理: {}...',
                'file_processed': '✅ 处理完成: {}',
                'file_failed': '❌ 处理失败: {}',
                'file_exception': '💥 处理异常: {}',
                'summary_success': '✅ 成功处理 {} 个文件',
                'summary_failed': '❌ 失败 {} 个文件',
                
                # 会话分组 - 中文文本
                'today': '📅 今天',
                'yesterday': '📅 昨天',
                'last_week': '📅 前7天',
                'older': '📅 更早',
                
                # 系统消息 - 中文文本
                'new_session_created': '👋 同学您好！很高兴为你服务！',
                'error_occurred': '❌ 抱歉，处理您的消息时出现错误。请稍后再试。',
                'file_type_error': '❌ 不支持的文件格式: {}\n支持的格式: {}',
                'file_save_error': '❌ 文件保存失败: {}',
                
                # 后续问题 - 中文文本
                'predicting_questions': '🔮 预测后续问题...',
            },
            'en': {
                # Login/Register - English text
                'welcome_back': '🔐 Welcome Back',
                'create_account': '📝 Create Account',
                'phone_placeholder': '📱 Enter 11-digit phone number',
                'password_placeholder': '🔒 Enter password',
                'username_placeholder': '👤 Enter username',
                'register_phone_placeholder': '📱 Enter 11-digit phone number',
                'password_length_error': '🔒 Password must be at least 6 characters',
                'login': '🔑 Login',
                'register': '📝 Register Now',
                'no_account': '📝 No account? Register now',
                'has_account': '🔑 Have account? Login',
                'phone_format_error': '📱 Please enter valid 11-digit phone number',
                'phone_exists': '📱 Phone number already registered, please login',
                'phone_not_exists': '📱 Phone number not registered, please register first',
                'wrong_password': '🔒 Incorrect password',
                'login_success': '✅ Login successful, redirecting...',
                'register_success': '✅ Registration successful, redirecting...',
                
                # Chat Interface - English text
                'welcome_user': '👋 Welcome, {} ({})',
                'new_chat': '➕ New Chat',
                'history_sessions': '📚 Chat History',
                'upload_file': '📁 Upload File',
                'send_message': '📤 Send',
                'input_placeholder': '💬 Type your question...',
                'exit': '🚪 Logout',
                
                # File Processing - English text
                'uploading_file': '📤 Uploading: {}...',
                'processing_file': '🔄 Processing: {}...',
                'file_processed': '✅ Processed: {}',
                'file_failed': '❌ Failed: {}',
                'file_exception': '💥 Exception: {}',
                'summary_success': '✅ Successfully processed {} files',
                'summary_failed': '❌ Failed {} files',
                
                # Session Groups - English text
                'today': '📅 Today',
                'yesterday': '📅 Yesterday',
                'last_week': '📅 Last 7 Days',
                'older': '📅 Earlier',
                
                # System Messages - English text
                'new_session_created': '👋 Hello! I am happy to assist you!',
                'error_occurred': '❌ Sorry, an error occurred processing your message. Please try again.',
                'file_type_error': '❌ Unsupported file format: {}\nSupported formats: {}',
                'file_save_error': '❌ File save failed: {}',
                
                # Next Questions - English text
                'predicting_questions': '🔮 Predicting next questions...',
            }
        }
    
    def get(self, key, *args):
        """获取翻译文本，支持格式化"""
        text = self.translations[self.language].get(key, key)
        if args:
            return text.format(*args)
        return text

# 创建全局配置实例
config = Config()