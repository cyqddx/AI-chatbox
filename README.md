<!-- ====================== 项目标题 ====================== -->
# 🎓 智能课程助手 (AI Engineer Mentor)

<!-- ====================== 项目简介 ====================== -->
> 基于 **RAG + LLM** 的智能课程助手，提供：
> - 📚 课程知识问答（RAG 检索）
> - 📁 多格式文件解析（PDF/DOCX/PPTX/TXT/HTML/IPYNB）
> - 🔍 实时网络搜索（SerpAPI）
> - 💬 日常对话交流
> - 📊 专业领域问答（比较选择/评估建议）
> - 👥 用户管理与聊天记录持久化
> - 🛠️ 系统维护（健康监控/版本管理/备份恢复）
> - 📖 知识库维护（内容更新/质量审查/权限管理）


<!-- ====================== 技术栈 ====================== -->
🚀 技术栈
| 层级        | 技术                                     | 说明         |
| --------- | --------------------------------------    | ---------- |
| **前端**    | Gradio                                   | 快速构建交互式界面  |
| **LLM**   | 通义千问 (qwen-plus)                       | 大语言模型      |
| **向量数据库** | ChromaDB                               | 语义检索       |
| **数据库**   | SQLite                                  | 用户/会话/消息存储 |
| **文件解析**  | LangChain + PyPDFLoader/Docx2txtLoader | 多格式文件解析    |
| **系统监控**  | psutil                                 | 系统资源监控     |

<!-- ====================== 安装步骤 ====================== -->
📦 安装步骤

### 1. 进入项目文件夹
cd AI_Engineer_Mentor

### 2. 创建虚拟环境
conda create --name aigc python=3.10

### 3. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

<!-- ======================📁 项目结构 ====================== -->
AI_Engineer_Mentor/
├── 📁 backups/                         # 系统备份目录
├── 📁 data/                            # 数据存储目录
│   ├── 📁 uploads/                     # 用户上传文件
│   └── 📁 vector_store/                # 向量数据库存储
├── 📁 db/                              # 数据库文件目录
│   └── users.db                        # SQLite数据库文件
├── 📁 log/                             # 日志文件目录
│   ├── app.log                         # 主日志文件
│   └── 📁 system_status/               # 系统状态日志
├── 📁 static/                          # 静态资源目录
│   └── styles.css                      # CSS样式文件
├── 📁 utils/                           # 工具类模块
│   ├── logger.py                       # 日志记录器
│   ├── database.py                     # 数据库管理
│   ├── llm_utils.py                    # 大语言模型工具
│   └── (其他工具类)
├── 📁 modules/                         # 功能模块
│   ├── knowledge_base.py               # 知识库管理
│   ├── knowledge_base_maintenance.py   # 知识库维护
│   ├── web_search.py                   # 网络搜索
│   ├── professional_qa.py              # 专业问答
│   ├── daily_chat.py                   # 日常交流
│   ├── intent_recognition.py           # 意图识别
│   ├── intent_router.py                # 意图路由
│   ├── next_questions.py               # 后续问题预测
│   ├── chat_management.py              # 聊天管理
│   ├── file_processing.py              # 文件处理
│   ├── rag.py                          # RAG检索增强生成
│   ├── system_maintenance.py           # 系统维护
│   ├── user_management.py              # 用户管理
│   ├── admin_management.py             # 管理员管理
│   └── ui_handlers.py                  # UI处理
├── main.py                             # 应用主入口
├── config.py                           # 全局配置文件
├── .env                                # 环境变量文件
└── requirements.txt                    # 依赖包列表

<!-- ====================== 使用指南 ====================== -->
🎯 使用指南
1. 启动服务
    python main.py
    自动打开浏览器访问 http://localhost:7890 (聊天界面)
    手动打开浏览器访问 http://localhost:7891 (管理员界面)

2. 用户注册/登录
    默认管理员账户为admin+123456
    首次使用需注册账号（手机号+密码）
    支持多用户隔离，每人独立聊天记录

3. 核心功能演示
    📚 课程问答示例
        用户：什么是梯度下降算法？
        系统：[通过RAG检索课程知识库，返回精准定义+示例]

    📁 文件解析示例
    点击"上传"按钮，选择 PDF/DOCX 等文件
    系统自动解析并建立向量索引
    输入问题："这份文档的核心观点是什么？"
    系统基于上传文件内容回答

<!-- ====================== 开发指南 ====================== -->
👨‍💻 开发指南
添加新意图类型
    修改 config.py 中的 INTENT_PROMPT 增加新分类
    在 intent_router.py 中 _handle_xxx 新增处理方法
    在 config.py 的 VALID_INTENTS 中增加新类型
添加新文件格式支持
    修改 config.py 的 SUPPORTED_FILE_FORMATS
    在 file_processing.py 的 _get_loader() 中增加新格式处理器
自定义样式
    编辑 static/styles.css，支持深色模式、移动端适配等
