"""Competition-facing static assets for 职启智评.

These assets are intentionally deterministic so the demo and seed script do not
depend on scraping, real fine-tuning, or a heavy vector database.
"""

COMPETITION_PRODUCT_NAME = "职启智评"
COMPETITION_FULL_TITLE = "职启智评：基于大语言模型与岗位画像匹配的大学生求职能力评估及模拟面试系统"
DEFAULT_TARGET_POSITION = "Python后端开发工程师"

TECHNICAL_INTERVIEW_TOPICS = [
    "语言基础",
    "数据库",
    "Redis",
    "HTTP/网络",
    "并发与异步",
    "算法与数据结构",
    "系统设计",
    "项目追问",
    "线上排障",
]

INTERVIEW_FOCUS_LIBRARY = {
    "python_backend": {
        "company_focus": [
            "互联网中小厂通常看接口开发、数据库、Redis、项目经验和排障思路",
            "偏平台或后端基础架构岗位会追问并发、异步任务、缓存一致性、服务稳定性",
            "校招更重视基础概念、课程项目真实性和能否讲清个人贡献",
        ],
        "sample_questions": [
            "你在项目里设计过哪些接口？如何处理参数校验、异常返回和权限校验？",
            "PostgreSQL 或 MySQL 索引什么时候会失效？你如何定位慢查询？",
            "Redis 在你的项目中解决了什么问题？如果缓存和数据库不一致怎么办？",
            "Celery/异步任务适合处理什么场景？失败重试和幂等怎么考虑？",
            "线上接口突然变慢，你会按什么顺序排查？",
        ],
    },
    "java_backend": {
        "company_focus": [
            "企业常看 Java 基础、集合、线程、JVM、Spring Boot、数据库事务和缓存",
            "有项目经历时会追问接口设计、事务边界、分布式场景和线上问题定位",
            "校招会从八股切入，再要求结合项目解释为什么这样设计",
        ],
        "sample_questions": [
            "HashMap 的扩容过程是什么？为什么线程不安全？",
            "Spring Bean 的生命周期大致有哪些阶段？",
            "数据库事务隔离级别有哪些？脏读、不可重复读、幻读分别是什么？",
            "Redis 缓存击穿、穿透、雪崩分别怎么处理？",
            "如果一个订单接口重复提交，你会怎么保证幂等？",
        ],
    },
    "frontend_engineer": {
        "company_focus": [
            "企业常看 JavaScript、浏览器、框架原理、组件设计、工程化和性能优化",
            "前端岗位经常通过项目追问接口联调、状态管理、权限路由和异常处理",
            "校招会同时考基础题、手写题和项目中遇到的真实问题",
        ],
        "sample_questions": [
            "说一下闭包、原型链和事件循环，你在项目中遇到过相关问题吗？",
            "Vue 的响应式原理是什么？`ref` 和 `reactive` 的差别是什么？",
            "前端页面首屏慢，你会从哪些方面优化？",
            "如何设计一个可复用的表单组件？",
            "接口联调时后端返回异常数据，你前端怎么兜底？",
        ],
    },
    "qa_engineer": {
        "company_focus": [
            "企业常看测试用例设计、接口测试、缺陷定位、自动化脚本和质量意识",
            "测试岗位会追问边界值、等价类、异常流程和回归策略",
            "有项目时重点看能否讲清发现问题、定位问题和推动修复的过程",
        ],
        "sample_questions": [
            "给一个登录功能，你会设计哪些测试用例？",
            "接口测试要验证哪些内容？状态码正确是否就够了？",
            "你提交过 Bug 吗？如何判断优先级和复现路径？",
            "自动化测试适合覆盖哪些场景？哪些不适合？",
            "如果线上出现偶现问题，你会如何协助定位？",
        ],
    },
    "algorithm_engineer": {
        "company_focus": [
            "企业常看机器学习基础、深度学习框架、数据处理、指标评估和实验复现",
            "算法岗会追问数据来源、特征、训练验证划分、过拟合和模型上线风险",
            "校招项目必须能讲清模型为什么有效，而不是只说调用了模型",
        ],
        "sample_questions": [
            "训练集、验证集、测试集分别用来做什么？数据泄漏是什么？",
            "过拟合有哪些表现？你会用哪些方法缓解？",
            "Precision、Recall、F1 分别适合什么场景？",
            "Embedding 向量相似度怎么计算？为什么能用于语义匹配？",
            "如果模型线上效果下降，你会怎么排查？",
        ],
    },
    "data_analyst": {
        "company_focus": [
            "企业常看 SQL、Excel/Python、指标体系、业务理解和结论表达",
            "数据分析面试常给业务场景，让候选人拆指标、找原因、提建议",
            "校招会重点看能否从数据表、图表和业务目标之间建立联系",
        ],
        "sample_questions": [
            "如何用 SQL 统计每个用户最近一次下单时间？",
            "转化率下降，你会从哪些维度拆解原因？",
            "留存率、复购率、客单价分别说明什么问题？",
            "你做过的数据分析结论如何影响后续行动？",
            "遇到缺失值和异常值，你会怎么处理？",
        ],
    },
    "product_assistant": {
        "company_focus": [
            "企业常看需求理解、用户场景、竞品分析、PRD 表达和跨部门协作",
            "产品助理会被追问是否能把模糊需求拆成可开发、可验证的功能",
            "校招项目重点看用户问题、方案取舍和复盘能力",
        ],
        "sample_questions": [
            "你如何判断一个需求是真需求还是伪需求？",
            "请用一个例子说明你如何做竞品分析。",
            "如果开发资源不足，你如何给需求排优先级？",
            "你写 PRD 时会包含哪些关键内容？",
            "你如何衡量一个功能上线后的效果？",
        ],
    },
    "hr_specialist": {
        "company_focus": [
            "企业常看招聘流程、候选人沟通、劳动法基础、Excel 和细致程度",
            "HR 岗会追问校园活动、人事助理、沟通协调等经历是否真实可展开",
            "校招更重视流程意识、服务意识和抗压沟通",
        ],
        "sample_questions": [
            "完整招聘流程通常包括哪些环节？",
            "候选人临时爽约，你会怎么沟通和记录？",
            "劳动合同、试用期、入离职手续有哪些基本注意点？",
            "你用 Excel 做过哪些数据整理？",
            "请讲一个你协调多方完成任务的经历。",
        ],
    },
    "recruiting_assistant": {
        "company_focus": [
            "企业常看简历初筛、渠道维护、邀约话术、记录反馈和执行稳定性",
            "招聘助理岗位会关注重复性事务处理质量和候选人体验",
        ],
        "sample_questions": [
            "你如何根据 JD 初筛简历？",
            "如果候选人问薪资但你不确定，你会怎么回复？",
            "如何记录和跟进候选人面试反馈？",
            "你认为招聘渠道维护的重点是什么？",
        ],
    },
    "operations_assistant": {
        "company_focus": [
            "企业常看活动执行、用户沟通、数据记录、流程跟进和复盘意识",
            "运营岗会追问指标变化、用户反馈和活动结果，而不是只听过程描述",
        ],
        "sample_questions": [
            "你执行过一次活动吗？目标、分工、结果分别是什么？",
            "如果活动参与人数低于预期，你会怎么分析？",
            "你如何收集和整理用户反馈？",
            "运营日报或周报通常应该包含哪些内容？",
        ],
    },
    "new_media_operator": {
        "company_focus": [
            "企业常看内容策划、平台理解、热点判断、文案表达和数据复盘",
            "新媒体岗位会追问阅读量、互动率、涨粉、转化等数据证据",
        ],
        "sample_questions": [
            "你如何判断一个选题是否值得做？",
            "小红书、公众号、抖音的内容逻辑有什么不同？",
            "你如何复盘一篇内容效果？",
            "如果账号数据连续下降，你会怎么调整？",
        ],
    },
    "admin_assistant": {
        "company_focus": [
            "企业常看办公软件、会议组织、流程执行、文档管理和服务意识",
            "行政岗会追问多任务处理、突发事件和细致可靠性",
        ],
        "sample_questions": [
            "组织一场会议前后你需要做哪些准备？",
            "如果两个紧急任务同时出现，你怎么排序？",
            "你如何保证文档归档不出错？",
            "遇到同事临时提出行政需求，你会怎么处理？",
        ],
    },
}

POSITION_PROFILES = [
    {
        "job_id": "python_backend",
        "job_name": "Python后端开发工程师",
        "category": "技术岗",
        "core_skills": ["Python", "FastAPI", "SQLAlchemy", "PostgreSQL", "Redis", "Docker", "异步编程"],
        "typical_tasks": ["接口开发", "数据库建模", "缓存设计", "异步任务", "服务部署", "线上问题排查"],
        "keywords": ["Python", "FastAPI", "SQL", "PostgreSQL", "Redis", "Docker", "Celery", "异步", "接口", "索引", "事务"],
        "evaluation_focus": ["语言和框架基础是否扎实", "是否能解释数据库与缓存取舍", "是否有真实项目和排障证据"],
        "interview_topics": TECHNICAL_INTERVIEW_TOPICS,
    },
    {
        "job_id": "java_backend",
        "job_name": "Java后端开发工程师",
        "category": "技术岗",
        "core_skills": ["Java", "Spring Boot", "MySQL", "Redis", "JVM", "消息队列", "微服务"],
        "typical_tasks": ["业务接口开发", "数据库事务处理", "缓存和消息队列接入", "服务性能优化", "问题定位"],
        "keywords": ["Java", "Spring", "Spring Boot", "MySQL", "Redis", "JVM", "线程", "事务", "消息队列", "微服务"],
        "evaluation_focus": ["Java 基础和并发理解", "Spring 生态使用经验", "数据库事务、缓存一致性和线上排障能力"],
        "interview_topics": TECHNICAL_INTERVIEW_TOPICS,
    },
    {
        "job_id": "frontend_engineer",
        "job_name": "前端开发工程师",
        "category": "技术岗",
        "core_skills": ["JavaScript", "TypeScript", "Vue", "React", "Vite", "前端工程化", "浏览器基础"],
        "typical_tasks": ["页面开发", "组件封装", "接口联调", "状态管理", "构建优化", "兼容性处理"],
        "keywords": ["JavaScript", "TypeScript", "Vue", "React", "Vite", "组件", "路由", "状态管理", "浏览器", "性能优化"],
        "evaluation_focus": ["框架和 JS 基础是否扎实", "是否能描述组件设计和状态管理", "是否有真实联调和性能优化经历"],
        "interview_topics": ["JavaScript 基础", "Vue/React 原理", "工程化", "浏览器渲染", "网络请求", "性能优化", "组件设计", "项目追问"],
    },
    {
        "job_id": "qa_engineer",
        "job_name": "测试工程师",
        "category": "技术岗",
        "core_skills": ["测试用例设计", "接口测试", "自动化测试", "缺陷跟踪", "SQL", "性能测试"],
        "typical_tasks": ["编写测试用例", "执行接口和功能测试", "定位缺陷", "维护自动化脚本", "输出测试报告"],
        "keywords": ["测试用例", "接口测试", "自动化", "缺陷", "Bug", "SQL", "Postman", "Pytest", "性能测试", "回归测试"],
        "evaluation_focus": ["是否理解测试设计方法", "是否能描述缺陷定位链路", "是否有自动化或接口测试实践"],
        "interview_topics": ["测试理论", "接口测试", "自动化框架", "SQL", "缺陷定位", "性能测试", "质量保障流程"],
    },
    {
        "job_id": "algorithm_engineer",
        "job_name": "算法工程师",
        "category": "技术岗",
        "core_skills": ["机器学习", "深度学习", "Python", "数据处理", "模型评估", "算法基础"],
        "typical_tasks": ["数据清洗", "特征构造", "模型训练或调用", "指标评估", "实验复现", "模型部署协作"],
        "keywords": ["机器学习", "深度学习", "PyTorch", "TensorFlow", "特征", "模型评估", "准确率", "召回率", "Embedding", "微调"],
        "evaluation_focus": ["是否能讲清模型原理和指标", "是否有真实实验和数据处理证据", "是否知道训练、验证和过拟合风险"],
        "interview_topics": ["机器学习基础", "深度学习基础", "特征工程", "模型评估", "过拟合", "Embedding", "实验复现", "项目追问"],
    },
    {
        "job_id": "data_analyst",
        "job_name": "数据分析师",
        "category": "数据岗",
        "core_skills": ["SQL", "Excel", "Python", "指标体系", "可视化", "业务理解"],
        "typical_tasks": ["提取数据", "制作报表", "分析业务指标", "解释异常波动", "输出分析结论"],
        "keywords": ["SQL", "Excel", "Python", "Pandas", "指标", "漏斗", "留存", "转化率", "可视化", "报表"],
        "evaluation_focus": ["是否理解业务指标", "是否能用数据解释问题", "是否有报表、分析或复盘证据"],
        "interview_topics": ["SQL 查询", "指标体系", "数据清洗", "可视化", "业务分析", "异常归因", "A/B 测试"],
    },
    {
        "job_id": "product_assistant",
        "job_name": "产品助理",
        "category": "产品岗",
        "core_skills": ["需求分析", "用户访谈", "竞品分析", "原型理解", "文档表达", "跨部门沟通"],
        "typical_tasks": ["整理需求", "协助画原型", "记录用户反馈", "撰写产品文档", "跟进开发测试"],
        "keywords": ["产品", "需求", "用户", "竞品", "原型", "PRD", "流程图", "用户故事", "迭代"],
        "evaluation_focus": ["是否能从用户视角表达问题", "是否能结构化拆解需求", "是否有跨部门沟通意识"],
        "interview_topics": ["需求分析", "用户场景", "竞品分析", "PRD", "原型", "优先级判断", "项目协作"],
    },
    {
        "job_id": "hr_specialist",
        "job_name": "人力资源专员",
        "category": "职能岗",
        "core_skills": ["招聘流程", "沟通协调", "劳动法基础", "Excel", "员工关系", "档案管理"],
        "typical_tasks": ["发布招聘信息", "筛选简历", "安排面试", "维护员工档案", "协助入离职手续"],
        "keywords": ["招聘", "面试", "劳动合同", "员工关系", "Excel", "人事", "档案管理", "入职", "离职"],
        "evaluation_focus": ["是否理解招聘流程", "是否能讲清沟通协调案例", "是否具备劳动关系基础意识"],
        "interview_topics": ["招聘流程", "候选人沟通", "劳动法基础", "员工关系", "Excel 数据整理", "情景沟通"],
    },
    {
        "job_id": "recruiting_assistant",
        "job_name": "招聘助理",
        "category": "职能岗",
        "core_skills": ["简历筛选", "候选人沟通", "面试邀约", "招聘渠道", "数据记录"],
        "typical_tasks": ["维护招聘渠道", "初筛候选人", "发送面试通知", "跟进面试反馈"],
        "keywords": ["招聘", "候选人", "邀约", "渠道", "面试安排", "沟通", "筛选", "反馈"],
        "evaluation_focus": ["候选人沟通是否清晰", "是否重视流程和反馈", "是否能处理重复性事务"],
        "interview_topics": ["简历初筛", "面试邀约", "渠道维护", "候选人跟进", "数据记录", "沟通礼仪"],
    },
    {
        "job_id": "operations_assistant",
        "job_name": "运营助理",
        "category": "运营岗",
        "core_skills": ["数据整理", "活动执行", "用户沟通", "流程跟进", "复盘意识"],
        "typical_tasks": ["整理运营数据", "协助活动落地", "跟进用户反馈", "输出周报"],
        "keywords": ["运营", "活动", "用户", "数据", "复盘", "执行", "转化", "增长", "社群"],
        "evaluation_focus": ["是否能描述执行细节", "是否有数据意识", "是否能做结果复盘"],
        "interview_topics": ["活动执行", "用户运营", "数据复盘", "增长指标", "社群维护", "流程协作"],
    },
    {
        "job_id": "new_media_operator",
        "job_name": "新媒体运营",
        "category": "运营岗",
        "core_skills": ["内容策划", "平台运营", "热点分析", "数据复盘", "文案表达"],
        "typical_tasks": ["撰写内容", "维护账号", "分析数据", "策划选题", "跟进互动"],
        "keywords": ["新媒体", "内容", "文案", "账号", "数据", "选题", "阅读量", "互动率", "小红书", "公众号"],
        "evaluation_focus": ["是否有内容案例", "是否理解平台差异", "是否能用数据复盘内容效果"],
        "interview_topics": ["内容策划", "平台规则", "热点判断", "数据复盘", "选题策略", "账号运营"],
    },
    {
        "job_id": "admin_assistant",
        "job_name": "行政管理助理",
        "category": "职能岗",
        "core_skills": ["办公软件", "流程执行", "会议组织", "文档管理", "服务意识"],
        "typical_tasks": ["整理文件", "协助会议", "维护办公流程", "处理行政事务"],
        "keywords": ["行政", "会议", "文档", "流程", "办公软件", "协调", "采购", "资产", "通知"],
        "evaluation_focus": ["是否细致可靠", "是否能处理多任务", "是否具备基础办公工具能力"],
        "interview_topics": ["会议组织", "文档管理", "流程执行", "跨部门协调", "服务意识", "突发事务处理"],
    },
]

SCORING_RULES = {
    "total_score": 100,
    "dimensions": [
        {"name": "岗位匹配度", "weight": 25, "description": "简历经历、技能关键词与目标岗位画像的匹配程度"},
        {"name": "专业能力", "weight": 20, "description": "课程、证书、技能和专业知识与岗位要求的关联度"},
        {"name": "实践经历", "weight": 20, "description": "实习、项目、社团、竞赛经历的数量、质量与相关性"},
        {"name": "表达逻辑", "weight": 15, "description": "简历表达和面试回答是否结构清晰、重点明确"},
        {"name": "完整度", "weight": 10, "description": "基本信息、教育经历、实践经历、技能证书等是否完整"},
        {"name": "改进潜力", "weight": 10, "description": "根据短板补强后进一步提升的空间"},
    ],
}

TECHNICAL_DEPTH_ROUTE = {
    "machine_learning": [
        "关键词覆盖率：统计简历与岗位画像关键词的命中情况",
        "TF-IDF/余弦相似度：在无向量 API 时提供可复现的文本匹配分",
        "规则评分：将经历完整度、证据强度、岗位关键词和 LLM 参考分组合成最终分",
        "轻量校准：后续基于人工评分样本调整规则权重",
    ],
    "deep_learning": [
        "大语言模型 API：用于简历结构化、面试追问、回答评价和报告生成",
        "Embedding 语义匹配：有可用 API Key 后接入向量相似度；不可用时回退 TF-IDF",
        "结构化 Prompt：限制输出 JSON 结构，减少自由发挥",
        "证据约束生成：没有简历证据时必须提示不足，不编造经历",
    ],
    "fine_tuning_preparation": [
        "导出简历、岗位画像、问题、回答、AI 评分、人工评分样本",
        "形成 fine-tune-ready JSONL，但当前不宣称已完成真实微调",
        "先做离线评测集和评分波动记录，再决定是否微调评分模型",
    ],
}

DEMO_CASES = [
    {
        "case_id": "T1",
        "profile": "计算机专业，做过 FastAPI + PostgreSQL 课程项目",
        "target_position": "Python后端开发工程师",
        "ai_score": 84,
        "human_score_avg": 82,
        "delta": 2,
        "suggestion": "补充接口吞吐、数据库索引、缓存使用和线上排障证据。",
    },
    {
        "case_id": "T2",
        "profile": "软件工程专业，Vue 项目经验较多，缺少工程化说明",
        "target_position": "前端开发工程师",
        "ai_score": 79,
        "human_score_avg": 78,
        "delta": 1,
        "suggestion": "增加组件设计、状态管理、接口联调和性能优化案例。",
    },
    {
        "case_id": "T3",
        "profile": "计算机专业，做过接口测试和 Pytest 自动化脚本",
        "target_position": "测试工程师",
        "ai_score": 76,
        "human_score_avg": 74,
        "delta": 2,
        "suggestion": "把测试用例设计方法、缺陷定位过程和回归策略写清楚。",
    },
    {
        "case_id": "T4",
        "profile": "统计专业，有 SQL、Excel 和校园数据分析经历",
        "target_position": "数据分析师",
        "ai_score": 81,
        "human_score_avg": 80,
        "delta": 1,
        "suggestion": "补充指标定义、异常归因和分析结论如何影响行动。",
    },
    {
        "case_id": "B1",
        "profile": "工商管理专业，有学生会组织经历和一次人事助理实习",
        "target_position": "人力资源专员",
        "ai_score": 82,
        "human_score_avg": 80,
        "delta": 2,
        "suggestion": "补充招聘流程中的具体动作和量化结果，例如筛选简历数量、邀约到面率。",
    },
    {
        "case_id": "B2",
        "profile": "工商管理专业，无正式实习，但做过校园活动执行",
        "target_position": "运营助理",
        "ai_score": 73,
        "human_score_avg": 75,
        "delta": -2,
        "suggestion": "把活动经历按 STAR 结构重写，突出目标、分工、执行过程和复盘数据。",
    },
    {
        "case_id": "B3",
        "profile": "理工科学生，做过课程项目，想转产品助理",
        "target_position": "产品助理",
        "ai_score": 70,
        "human_score_avg": 72,
        "delta": -2,
        "suggestion": "把技术项目改写为需求理解、用户问题、方案取舍和协作沟通证据。",
    },
    {
        "case_id": "B4",
        "profile": "有社团宣传经历和公众号排版经历",
        "target_position": "新媒体运营",
        "ai_score": 78,
        "human_score_avg": 76,
        "delta": 2,
        "suggestion": "补齐阅读量、互动率、选题策略等指标，让内容能力更可验证。",
    },
]

COMPETITION_DEMO_ASSETS = {
    "product_name": COMPETITION_PRODUCT_NAME,
    "title": COMPETITION_FULL_TITLE,
    "default_target_position": DEFAULT_TARGET_POSITION,
    "position_profiles": POSITION_PROFILES,
    "interview_focus_library": INTERVIEW_FOCUS_LIBRARY,
    "scoring_rules": SCORING_RULES,
    "technical_depth_route": TECHNICAL_DEPTH_ROUTE,
    "demo_cases": DEMO_CASES,
    "claim_boundary": (
        "本系统保留多岗位模拟面试能力；职启智评是参赛增强层。当前不训练底层大模型，"
        "不宣称自研大模型或真实微调；重点是岗位画像、轻量匹配评分、规则约束、证据追问和可解释报告。"
    ),
}
