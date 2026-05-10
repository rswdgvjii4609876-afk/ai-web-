from __future__ import annotations

from typing import Any, Dict, List


AI_LEARNING_LOOP = [
    "生成理论材料",
    "完成 Demo 或练习",
    "学习理论并记录问题",
    "实操练习并补充注释",
    "更新学习进度和下一步薄弱项",
]


PYTHON_BACKEND_ROUTE_SOURCE = "project_builtin_python_backend_route"
PYTHON_BASIC_ROUTE_SOURCE = "project_builtin_python_basic_route"
JAVA_BACKEND_ROUTE_SOURCE = "project_builtin_java_backend_route"
FRONTEND_ROUTE_SOURCE = "project_builtin_frontend_route"
QA_ROUTE_SOURCE = "project_builtin_qa_route"
ALGORITHM_ROUTE_SOURCE = "project_builtin_algorithm_route"
DATA_ANALYST_ROUTE_SOURCE = "project_builtin_data_analyst_route"
PRODUCT_ROUTE_SOURCE = "project_builtin_product_position_route"
OPERATIONS_ROUTE_SOURCE = "project_builtin_operations_route"
NEW_MEDIA_ROUTE_SOURCE = "project_builtin_new_media_route"
HR_ROUTE_SOURCE = "project_builtin_hr_route"
RECRUITING_ROUTE_SOURCE = "project_builtin_recruiting_route"
ADMIN_ROUTE_SOURCE = "project_builtin_admin_route"
TECH_GENERAL_ROUTE_SOURCE = "project_builtin_tech_general_route"
FUNCTIONAL_GENERAL_ROUTE_SOURCE = "project_builtin_functional_general_route"
GENERAL_ROUTE_SOURCE = "project_builtin_general_position_route"


def _stage(
    route_source: str,
    route_stage: str,
    title: str,
    material_type: str,
    task_type: str,
    estimated_minutes: int,
    keywords: List[str],
    material: str,
) -> Dict[str, Any]:
    return {
        "route_source": route_source,
        "route_stage": route_stage,
        "title": title,
        "material_type": material_type,
        "task_type": task_type,
        "estimated_minutes": estimated_minutes,
        "keywords": keywords,
        "material": material,
    }


PYTHON_BACKEND_ROUTE_STAGES: List[Dict[str, Any]] = [
    _stage(PYTHON_BASIC_ROUTE_SOURCE, "python_basic", "Python 基础与编程思维", "python_basic_route", "theory_demo", 180, ["python", "语法", "函数", "oop", "装饰器", "迭代器", "异常", "文件", "类型"], "项目内置学习路线：python基础学习路线.md；重点补 Python 语法、函数、OOP、异常处理和文件处理。"),
    _stage(PYTHON_BACKEND_ROUTE_SOURCE, "web_api_foundation", "Web 与 REST API 基础", "python_backend_route", "theory_demo", 150, ["http", "rest", "api", "接口", "认证", "jwt", "cors", "网络"], "项目内置学习路线：python后端学习路线.md；重点补 HTTP、RESTful API、认证授权和接口设计。"),
    _stage(PYTHON_BACKEND_ROUTE_SOURCE, "database_orm", "数据库、SQL 与 ORM", "python_backend_route", "demo_practice", 210, ["sql", "mysql", "postgres", "数据库", "索引", "事务", "orm", "sqlalchemy", "alembic"], "项目内置学习路线：python后端学习路线.md；重点补 SQL、索引、事务、SQLAlchemy 和 Alembic。"),
    _stage(PYTHON_BACKEND_ROUTE_SOURCE, "fastapi_framework", "FastAPI 框架与工程结构", "python_backend_route", "demo_practice", 240, ["fastapi", "pydantic", "depends", "异步", "swagger", "中间件", "路由"], "项目内置学习路线：python后端学习路线.md；重点补 FastAPI、Pydantic、依赖注入、异步接口和项目分层。"),
    _stage(PYTHON_BACKEND_ROUTE_SOURCE, "middleware_engineering", "Redis、Celery、Docker 与部署", "python_backend_route", "project_practice", 240, ["redis", "缓存", "celery", "docker", "部署", "异步", "队列", "排障"], "项目内置学习路线：python后端学习路线.md；重点补 Redis 缓存、Celery 异步任务、Docker 部署和线上排障。"),
    _stage(PYTHON_BACKEND_ROUTE_SOURCE, "project_review", "项目实战与面试复盘", "python_backend_route", "project_review", 180, ["项目", "复盘", "排障", "性能", "上线", "证据", "面试"], "项目内置学习路线：python后端学习路线.md；重点把学习结果整理成项目证据和面试表达。"),
]

JAVA_BACKEND_ROUTE_STAGES = [
    _stage(JAVA_BACKEND_ROUTE_SOURCE, "java_foundation", "Java 基础、集合与异常", "java_backend_route", "theory_demo", 180, ["java", "集合", "异常", "泛型", "stream", "面向对象"], "岗位画像知识库：重点补 Java 基础、集合、异常、泛型和常见业务代码表达。"),
    _stage(JAVA_BACKEND_ROUTE_SOURCE, "spring_boot_api", "Spring Boot 与接口开发", "java_backend_route", "demo_practice", 210, ["spring", "springboot", "bean", "接口", "mvc", "参数校验"], "岗位画像知识库：重点补 Spring Boot、Bean 生命周期、REST 接口、参数校验和分层结构。"),
    _stage(JAVA_BACKEND_ROUTE_SOURCE, "java_database_cache", "MySQL 事务与 Redis 缓存", "java_backend_route", "demo_practice", 240, ["mysql", "数据库", "事务", "索引", "redis", "缓存", "一致性"], "岗位画像知识库：重点补事务隔离、索引设计、缓存击穿/穿透/雪崩和缓存一致性。"),
    _stage(JAVA_BACKEND_ROUTE_SOURCE, "jvm_concurrency_ops", "JVM、并发与线上排障", "java_backend_route", "project_review", 240, ["jvm", "线程", "并发", "线程池", "锁", "排障", "日志"], "岗位画像知识库：重点补 JVM 基础、线程池、锁、接口变慢排查和项目复盘表达。"),
]

FRONTEND_ROUTE_STAGES = [
    _stage(FRONTEND_ROUTE_SOURCE, "frontend_language_foundation", "JavaScript/TypeScript 基础", "frontend_route", "theory_demo", 180, ["javascript", "typescript", "闭包", "异步", "promise", "类型"], "岗位画像知识库：重点补 JS/TS 基础、异步、类型、模块化和常见手写题思路。"),
    _stage(FRONTEND_ROUTE_SOURCE, "frontend_framework_component", "Vue/React 与组件设计", "frontend_route", "demo_practice", 210, ["vue", "react", "组件", "状态", "路由", "响应式"], "岗位画像知识库：重点补 Vue/React 组件拆分、状态管理、权限路由和复用设计。"),
    _stage(FRONTEND_ROUTE_SOURCE, "frontend_engineering", "Vite、工程化与接口联调", "frontend_route", "project_practice", 210, ["vite", "工程化", "构建", "联调", "mock", "环境变量"], "岗位画像知识库：重点补构建配置、接口联调、异常兜底、Mock 和前后端协作。"),
    _stage(FRONTEND_ROUTE_SOURCE, "frontend_performance_review", "浏览器、性能优化与项目复盘", "frontend_route", "project_review", 180, ["浏览器", "性能", "首屏", "缓存", "渲染", "复盘"], "岗位画像知识库：重点补浏览器渲染、首屏优化、资源缓存和项目问题复盘。"),
]

QA_ROUTE_STAGES = [
    _stage(QA_ROUTE_SOURCE, "qa_case_design", "测试用例设计方法", "qa_route", "case_practice", 150, ["测试用例", "等价类", "边界值", "场景", "异常流程"], "岗位画像知识库：重点补等价类、边界值、异常流程、业务场景和测试覆盖说明。"),
    _stage(QA_ROUTE_SOURCE, "qa_api_sql", "接口测试与 SQL 验证", "qa_route", "demo_practice", 180, ["接口测试", "postman", "sql", "状态码", "断言", "数据校验"], "岗位画像知识库：重点补接口请求、断言、数据库校验和测试数据准备。"),
    _stage(QA_ROUTE_SOURCE, "qa_automation", "自动化测试与回归策略", "qa_route", "project_practice", 210, ["自动化", "pytest", "脚本", "回归", "ci"], "岗位画像知识库：重点补 Pytest/自动化脚本、适用边界、回归策略和 CI 测试。"),
    _stage(QA_ROUTE_SOURCE, "qa_bug_review", "缺陷定位与质量复盘", "qa_route", "project_review", 150, ["bug", "缺陷", "复现", "优先级", "定位", "复盘"], "岗位画像知识库：重点补 Bug 复现、日志/数据定位、优先级判断和推动修复过程。"),
]

ALGORITHM_ROUTE_STAGES = [
    _stage(ALGORITHM_ROUTE_SOURCE, "ml_foundation", "机器学习基础与指标", "algorithm_route", "theory_demo", 210, ["机器学习", "precision", "recall", "f1", "指标", "过拟合"], "岗位画像知识库：重点补训练/验证/测试划分、过拟合、Precision/Recall/F1 和实验解释。"),
    _stage(ALGORITHM_ROUTE_SOURCE, "data_feature_engineering", "数据处理与特征工程", "algorithm_route", "demo_practice", 210, ["数据", "清洗", "特征", "样本", "数据泄漏"], "岗位画像知识库：重点补数据来源、清洗、特征构造、数据泄漏和可复现实验记录。"),
    _stage(ALGORITHM_ROUTE_SOURCE, "deep_learning_embedding", "深度学习、Embedding 与 RAG", "algorithm_route", "demo_practice", 240, ["深度学习", "pytorch", "embedding", "rag", "向量", "微调"], "岗位画像知识库：重点补深度学习框架、Embedding、RAG、微调数据准备和评估方式。"),
    _stage(ALGORITHM_ROUTE_SOURCE, "experiment_deployment_review", "实验复现与模型上线风险", "algorithm_route", "project_review", 180, ["实验", "复现", "部署", "上线", "风险", "监控"], "岗位画像知识库：重点补实验记录、模型为什么有效、上线风险和模型监控表达。"),
]

DATA_ANALYST_ROUTE_STAGES = [
    _stage(DATA_ANALYST_ROUTE_SOURCE, "data_sql_processing", "SQL、Excel 与数据处理", "data_analyst_route", "demo_practice", 180, ["sql", "excel", "pandas", "清洗", "缺失值", "异常值"], "岗位画像知识库：重点补 SQL 查询、Excel/Pandas 清洗、缺失值和异常值处理。"),
    _stage(DATA_ANALYST_ROUTE_SOURCE, "metric_system", "业务指标体系", "data_analyst_route", "case_practice", 150, ["指标", "留存", "转化", "漏斗", "复购", "客单价"], "岗位画像知识库：重点补留存、转化、漏斗、复购、客单价等业务指标含义。"),
    _stage(DATA_ANALYST_ROUTE_SOURCE, "visualization_report", "可视化与报告表达", "data_analyst_route", "document_output", 150, ["可视化", "报表", "图表", "dashboard", "汇报"], "岗位画像知识库：重点补图表选择、报表结构、结论表达和面向业务方沟通。"),
    _stage(DATA_ANALYST_ROUTE_SOURCE, "business_diagnosis", "业务归因与行动建议", "data_analyst_route", "case_practice", 180, ["业务", "归因", "建议", "策略", "a/b", "验证"], "岗位画像知识库：重点补异常波动归因、假设验证、A/B 测试和行动建议。"),
]

PRODUCT_ROUTE_STAGES = [
    _stage(PRODUCT_ROUTE_SOURCE, "product_requirement_analysis", "需求分析与用户场景", "product_position_route", "case_practice", 150, ["产品", "需求", "用户", "场景", "痛点"], "岗位画像知识库：重点补用户场景、痛点识别、需求拆解和问题定义。"),
    _stage(PRODUCT_ROUTE_SOURCE, "prd_prototype", "PRD、原型与流程表达", "product_position_route", "document_output", 180, ["prd", "原型", "流程图", "用户故事", "验收标准"], "岗位画像知识库：重点补 PRD、原型、流程图、用户故事和验收标准。"),
    _stage(PRODUCT_ROUTE_SOURCE, "product_metric_review", "指标验证与上线复盘", "product_position_route", "case_practice", 150, ["指标", "转化", "留存", "点击", "复盘", "a/b"], "岗位画像知识库：重点补上线后指标、数据复盘、A/B 验证和改进建议。"),
    _stage(PRODUCT_ROUTE_SOURCE, "product_collaboration", "跨部门协作与推进", "product_position_route", "scenario_practice", 120, ["开发", "测试", "协作", "推进", "排期", "沟通"], "岗位画像知识库：重点补开发测试协作、排期跟进、风险沟通和需求变更处理。"),
]

OPERATIONS_ROUTE_STAGES = [
    _stage(OPERATIONS_ROUTE_SOURCE, "operation_execution", "活动执行与流程跟进", "operations_route", "scenario_practice", 120, ["活动", "执行", "流程", "排期", "落地"], "岗位画像知识库：重点补活动目标、执行排期、流程跟进和异常处理。"),
    _stage(OPERATIONS_ROUTE_SOURCE, "user_feedback", "用户沟通与反馈整理", "operations_route", "document_output", 120, ["用户", "反馈", "社群", "沟通", "互动"], "岗位画像知识库：重点补用户反馈收集、社群沟通、问题分类和跟进记录。"),
    _stage(OPERATIONS_ROUTE_SOURCE, "operation_data_review", "运营数据与复盘", "operations_route", "case_practice", 150, ["数据", "复盘", "转化", "留存", "增长", "周报"], "岗位画像知识库：重点补运营日报/周报、指标变化、复盘结论和下一步动作。"),
    _stage(OPERATIONS_ROUTE_SOURCE, "operation_growth_plan", "增长假设与小实验", "operations_route", "case_practice", 150, ["增长", "假设", "实验", "策略", "优化"], "岗位画像知识库：重点补增长假设、活动优化、小实验设计和结果判断。"),
]

NEW_MEDIA_ROUTE_STAGES = [
    _stage(NEW_MEDIA_ROUTE_SOURCE, "content_planning", "内容选题与平台理解", "new_media_route", "case_practice", 120, ["内容", "选题", "平台", "热点", "账号"], "岗位画像知识库：重点补平台规则、用户画像、选题逻辑和热点判断。"),
    _stage(NEW_MEDIA_ROUTE_SOURCE, "copywriting_output", "文案表达与内容产出", "new_media_route", "document_output", 150, ["文案", "标题", "排版", "脚本", "表达"], "岗位画像知识库：重点补标题、正文结构、排版、脚本和内容表达。"),
    _stage(NEW_MEDIA_ROUTE_SOURCE, "media_data_review", "内容数据复盘", "new_media_route", "case_practice", 150, ["阅读量", "互动率", "涨粉", "转化", "复盘"], "岗位画像知识库：重点补阅读量、互动率、涨粉、转化和内容复盘。"),
    _stage(NEW_MEDIA_ROUTE_SOURCE, "account_iteration", "账号定位与迭代策略", "new_media_route", "case_practice", 150, ["定位", "迭代", "调整", "策略", "下降"], "岗位画像知识库：重点补账号定位、数据下降原因分析和后续迭代策略。"),
]

HR_ROUTE_STAGES = [
    _stage(HR_ROUTE_SOURCE, "hr_recruitment_process", "招聘流程与简历初筛", "hr_route", "scenario_practice", 120, ["招聘", "简历", "筛选", "流程", "面试"], "岗位画像知识库：重点补招聘流程、简历初筛、面试安排和反馈闭环。"),
    _stage(HR_ROUTE_SOURCE, "hr_communication", "候选人与员工沟通", "hr_route", "scenario_practice", 120, ["沟通", "候选人", "员工", "协调", "反馈"], "岗位画像知识库：重点补候选人沟通、员工沟通、冲突协调和服务意识。"),
    _stage(HR_ROUTE_SOURCE, "hr_labor_compliance", "劳动关系与合规基础", "hr_route", "theory_case", 150, ["劳动法", "合同", "试用期", "入离职", "合规"], "岗位画像知识库：重点补劳动合同、试用期、入离职手续和基础合规风险。"),
    _stage(HR_ROUTE_SOURCE, "hr_data_office", "Excel、档案与数据记录", "hr_route", "document_output", 120, ["excel", "数据", "档案", "记录", "表格"], "岗位画像知识库：重点补 Excel 数据整理、员工档案、招聘台账和流程文档。"),
]

RECRUITING_ROUTE_STAGES = [
    _stage(RECRUITING_ROUTE_SOURCE, "recruiting_channel", "招聘渠道与岗位发布", "recruiting_route", "document_output", 120, ["渠道", "招聘", "岗位", "发布", "jd"], "岗位画像知识库：重点补渠道维护、岗位发布、JD 关键信息和候选人来源记录。"),
    _stage(RECRUITING_ROUTE_SOURCE, "resume_screening", "简历筛选与匹配判断", "recruiting_route", "case_practice", 150, ["简历", "筛选", "匹配", "关键词", "候选人"], "岗位画像知识库：重点补简历筛选标准、岗位关键词、候选人匹配理由和风险点。"),
    _stage(RECRUITING_ROUTE_SOURCE, "interview_invitation", "面试邀约与反馈跟进", "recruiting_route", "scenario_practice", 120, ["邀约", "面试安排", "反馈", "跟进", "沟通"], "岗位画像知识库：重点补邀约话术、时间协调、面试反馈跟进和候选人体验。"),
    _stage(RECRUITING_ROUTE_SOURCE, "recruiting_data_record", "招聘数据记录与复盘", "recruiting_route", "document_output", 120, ["数据", "台账", "转化", "到面率", "复盘"], "岗位画像知识库：重点补招聘台账、到面率、转化率、渠道效果和周报复盘。"),
]

ADMIN_ROUTE_STAGES = [
    _stage(ADMIN_ROUTE_SOURCE, "admin_office_tools", "办公软件与文档处理", "admin_route", "document_output", 120, ["办公软件", "excel", "word", "文档", "表格"], "岗位画像知识库：重点补 Word/Excel/表格、会议纪要、通知和文档归档。"),
    _stage(ADMIN_ROUTE_SOURCE, "admin_process_execution", "流程执行与事务跟进", "admin_route", "scenario_practice", 120, ["流程", "执行", "跟进", "事务", "登记"], "岗位画像知识库：重点补事务登记、流程跟进、节点提醒和执行闭环。"),
    _stage(ADMIN_ROUTE_SOURCE, "admin_meeting_event", "会议组织与活动支持", "admin_route", "scenario_practice", 120, ["会议", "活动", "组织", "物资", "协调"], "岗位画像知识库：重点补会议组织、物资准备、现场协调和异常处理。"),
    _stage(ADMIN_ROUTE_SOURCE, "admin_service_compliance", "服务意识与规则合规", "admin_route", "theory_case", 120, ["服务", "合规", "制度", "保密", "沟通"], "岗位画像知识库：重点补服务意识、制度执行、保密意识和沟通边界。"),
]

TECH_GENERAL_ROUTE_STAGES = [
    _stage(TECH_GENERAL_ROUTE_SOURCE, "tech_foundation", "技术基础补强", "tech_general_route", "theory_demo", 150, ["基础", "语言", "框架", "工具"], "岗位画像知识库：先补目标岗位语言、框架和工具链基础。"),
    _stage(TECH_GENERAL_ROUTE_SOURCE, "tech_project_practice", "项目练习与证据整理", "tech_general_route", "project_practice", 180, ["项目", "demo", "实践", "证据"], "岗位画像知识库：完成一个可展示练习，并沉淀项目证据。"),
    _stage(TECH_GENERAL_ROUTE_SOURCE, "tech_debug_review", "问题定位与复盘", "tech_general_route", "project_review", 150, ["问题", "bug", "排障", "复盘"], "岗位画像知识库：补充问题定位、修复过程和复盘表达。"),
    _stage(TECH_GENERAL_ROUTE_SOURCE, "tech_interview_expression", "技术面试表达", "tech_general_route", "project_review", 120, ["面试", "表达", "追问", "解释"], "岗位画像知识库：把技术练习整理成可被追问的面试表达。"),
]

FUNCTIONAL_GENERAL_ROUTE_STAGES = [
    _stage(FUNCTIONAL_GENERAL_ROUTE_SOURCE, "functional_process", "流程理解与执行", "functional_general_route", "scenario_practice", 120, ["流程", "执行", "跟进", "记录"], "岗位画像知识库：先补岗位流程、关键节点和执行记录。"),
    _stage(FUNCTIONAL_GENERAL_ROUTE_SOURCE, "functional_communication", "沟通协作场景", "functional_general_route", "scenario_practice", 120, ["沟通", "协作", "反馈", "协调"], "岗位画像知识库：准备沟通协作案例和场景回答。"),
    _stage(FUNCTIONAL_GENERAL_ROUTE_SOURCE, "functional_document", "文档与数据记录", "functional_general_route", "document_output", 120, ["文档", "数据", "表格", "记录"], "岗位画像知识库：补齐文档、表格、台账或复盘记录能力。"),
    _stage(FUNCTIONAL_GENERAL_ROUTE_SOURCE, "functional_review", "结果复盘与改进", "functional_general_route", "case_practice", 120, ["复盘", "改进", "结果", "指标"], "岗位画像知识库：补充结果复盘、改进动作和可验证输出。"),
]

JOB_ROUTE_STAGES = {
    "python_backend": PYTHON_BACKEND_ROUTE_STAGES,
    "java_backend": JAVA_BACKEND_ROUTE_STAGES,
    "frontend_engineer": FRONTEND_ROUTE_STAGES,
    "qa_engineer": QA_ROUTE_STAGES,
    "algorithm_engineer": ALGORITHM_ROUTE_STAGES,
    "data_analyst": DATA_ANALYST_ROUTE_STAGES,
    "product_assistant": PRODUCT_ROUTE_STAGES,
    "operations_assistant": OPERATIONS_ROUTE_STAGES,
    "new_media_operator": NEW_MEDIA_ROUTE_STAGES,
    "hr_specialist": HR_ROUTE_STAGES,
    "recruiting_assistant": RECRUITING_ROUTE_STAGES,
    "admin_assistant": ADMIN_ROUTE_STAGES,
}

CATEGORY_ROUTE_STAGES = {
    "技术岗": TECH_GENERAL_ROUTE_STAGES,
    "数据岗": DATA_ANALYST_ROUTE_STAGES,
    "产品岗": PRODUCT_ROUTE_STAGES,
    "运营岗": OPERATIONS_ROUTE_STAGES,
    "职能岗": FUNCTIONAL_GENERAL_ROUTE_STAGES,
}


GENERAL_ROUTE_STAGE = {
    "route_stage": "general_position_improvement",
    "title": "岗位能力通用提升",
    "route_source": GENERAL_ROUTE_SOURCE,
    "material_type": "general_position_route",
    "task_type": "general_practice",
    "estimated_minutes": 120,
    "material": "岗位画像知识库：结合岗位要求、问答经验、能力模型和面试追问分区进行学习。",
}


def _match_from_stages(stages: List[Dict[str, Any]], normalized: str) -> Dict[str, Any]:
    for stage in stages:
        if any(keyword.lower() in normalized for keyword in stage.get("keywords", [])):
            return dict(stage)
    return dict(stages[-1])


def match_learning_route_stage(job_id: str, text: str, category: str | None = None) -> Dict[str, Any]:
    normalized = (text or "").lower()
    stages = JOB_ROUTE_STAGES.get(job_id)
    if stages:
        return _match_from_stages(stages, normalized)
    if "python" in normalized:
        return _match_from_stages(PYTHON_BACKEND_ROUTE_STAGES, normalized)
    if category and CATEGORY_ROUTE_STAGES.get(category):
        return _match_from_stages(CATEGORY_ROUTE_STAGES[category], normalized)
    return dict(GENERAL_ROUTE_STAGE)
