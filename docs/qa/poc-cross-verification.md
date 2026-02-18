## QA 交叉验证报告

**日期**: 2026-02-19
**QA Manager**: Quality Guardian
**范围**: Manager A（架构）、Manager B（权限）、Manager C（工程）三份 PoC 交付物
**版本**: 1.0

---

### 一、一致性检查

| # | 检查项 | 预期（设计文档） | 实际（代码） | 判定 |
|---|--------|----------------|-------------|------|
| 1 | State Schema 字段对齐 | Manager A 定义 `NEXUSState`：含 contract_id, work_order_id, thread_id, raw_user_message, session_id, status(ContractStatus 枚举含12种状态), current_node, priority, ceo_analysis, ceo_decision, ceo_clarification_question, modules, target_manager, context_budget, subtasks(Annotated[list[SubTask],add]), worker_outputs(Annotated[list,add]), escalation_chain, qa_retry_count, qa_results(Annotated[list[QAResult],add]), qa_overall_passed, final_output, delivery_method, error, audit_trail(Annotated[list,add]) -- 共 24 个字段 | Manager C 定义 `NexusContractState`：含 contract_id, task_description, priority, department, current_phase, worker_output(str), qa_verdict(str), qa_report(str), attempt_count(int), max_attempts(int), subtasks(list[str]), manager_instruction(str), mail_log(Annotated[list,add]), final_result(str), ceo_approved(bool), escalated(bool) -- 共 16 个字段 | **PARTIAL** |
| 2 | roles.yaml 工具列表 vs *_tools.py 实际工具 | roles.yaml 定义 9 个角色（ceo, it_manager, hr_manager, product_manager, backend_worker, frontend_worker, devops_worker, qa_worker, research_worker），每个角色有详细工具列表，tool_catalog 定义 30+ 工具 | permissions.py 只定义 4 个简化角色（ceo, manager, worker, qa），工具列表为简化版：ceo=[generate_contract,send_mail,write_note,read_reports]; manager=[break_down_task,assign_worker,review_report,send_mail,escalate]; worker=[write_code,run_tests,git_commit,read_file,send_mail]; qa=[review_code,run_linter,run_tests,write_verdict,send_mail] | **PARTIAL** |
| 3 | Graph 结构（节点和边）匹配 | Manager A 定义 7 个节点：INTAKE, CEO, MANAGER, WORKER, QA, DELIVER, CLARIFY。条件边：CEO 后三路（approve/clarify/reject），QA 后三路（passed/retry_worker/escalate）。Worker 使用 Send API 并发。固定边含 CLARIFY->CEO 回路 | Manager C 定义 7 个节点：ceo_dispatch, manager_plan, worker_execute, qa_review, manager_review_after_qa, ceo_approve, ceo_handle_escalation。条件边只在 manager_review_after_qa 后（ceo_approve/worker_execute/ceo_handle_escalation）。无 INTAKE, DELIVER, CLARIFY 节点，无 Send API 并发，无 interrupt | **PARTIAL** |
| 4 | Chain of Command 规则 C-01 ~ C-07 落地 | C-01: CEO 只联系 L2 Manager; C-02: Manager 联系本部门 Worker+CEO+条件跨部门; C-03: Worker 只联系直属 Manager; C-04: Worker 间不可通信; C-05: 跨部门通过 Manager 中继; C-06: 违规拦截记录 mail_rejections; C-07: 合同只向下传递 | permissions.py 的 ALLOWED_MAIL_ROUTES 实现了简化版：(ceo,manager),(manager,ceo),(manager,worker),(manager,qa),(worker,manager),(qa,manager)。C-01 部分落地（但 ceo 的 allowed_contacts 额外含 "manager" 泛化角色）；C-02 简化为 manager 可联系 worker/qa/ceo；C-03/C-04/C-05 通过 ALLOWED_MAIL_ROUTES 不含 (worker,worker)/(worker,qa)/(worker,ceo) 实现；C-06 未实现（无 mail_rejections 表/日志记录，异常直接 raise）；C-07 未在 create_contract 工具中实现（工程代码中无 create_contract 工具，只有 generate_contract） | **PARTIAL** |
| 5 | mail-protocol.yaml 邮件类型覆盖 | 定义 12 种邮件类型：contract, report, approval_request, info, escalation, question, verdict, staffing_request, tool_request, tech_review, requirement_clarification, deployment_approval。每种类型有 allowed_senders、allowed_receivers、required_fields 约束 | state.py 的 MailMessage.type 只定义 5 种：contract, report, approval_request, info, escalation。mail.py 的 send_mail 接受任意 msg_type 字符串，不做类型校验。无 per-type 的 sender/receiver 校验逻辑 | **PARTIAL** |

#### 一致性差异详细说明

**1. State Schema 差异分析**

Manager C 采取了合理的 PoC 简化策略，将 Manager A 的复杂 State 精简为 16 个核心字段。关键差异：

- Manager A 的 `work_order_id` / `thread_id` / `session_id` / `raw_user_message` 等基础设施字段被省略（PoC 不需要 PG/Redis 集成）
- Manager A 的 `ContractStatus` 12 种枚举被简化为 `current_phase` 自由字符串
- Manager A 的 `SubTask(TypedDict)` 结构体被简化为 `subtasks: list[str]`
- Manager A 的 `QAResult(TypedDict)` 被简化为 `qa_verdict: str` + `qa_report: str`
- Manager A 的 `worker_outputs: Annotated[list, add]` 被简化为 `worker_output: str`（单 Worker，非并发）
- Manager A 的 `audit_trail` 审计字段未实现，但 `mail_log: Annotated[list, add]` 起到了部分审计作用
- Manager C 新增了 Manager A 未定义的字段：`department`, `max_attempts`, `manager_instruction`, `ceo_approved`, `escalated`

**结论**：字段不对齐，但 Manager C 的简化在 PoC 阶段合理。核心语义（合同生命周期追踪）保持一致。

**2. 工具列表差异分析**

Manager B 的 roles.yaml 定义了 9 个细粒度角色和 30+ 工具，Manager C 将其简化为 4 个泛化角色和约 15 个工具。具体对应关系：

| roles.yaml 角色 | permissions.py 角色 | 工具覆盖 |
|-----------------|-------------------|----------|
| ceo | ceo | 4/4 匹配（generate_contract, send_mail, write_note, read_reports） |
| it_manager / hr_manager / product_manager | manager | 5 个泛化工具，部分匹配（break_down_task 对应 roles.yaml 无直接等价但语义合理，escalate 匹配） |
| backend_worker / frontend_worker / devops_worker | worker | 5 个泛化工具（write_code/run_tests/git_commit/read_file/send_mail），覆盖了 backend_worker 的核心能力 |
| qa_worker | qa | 5 个工具（review_code/run_linter/run_tests/write_verdict/send_mail），与 roles.yaml 高度匹配 |
| research_worker | 未实现 | 0/6 |

**结论**：CEO 和 QA 工具高度一致；Manager 和 Worker 合理简化；research_worker 完全缺失（PoC 范围外）。

**3. Graph 结构差异分析**

| Manager A 设计 | Manager C 实现 | 说明 |
|---------------|---------------|------|
| INTAKE 节点 | 未实现 | PoC 直接从 ceo_dispatch 开始，无需 Admin 预处理 |
| CEO 节点（含 interrupt + clarify 路由） | ceo_dispatch + ceo_approve + ceo_handle_escalation（3 个节点，无 interrupt） | 语义拆分为 3 个独立节点，比 Manager A 的单 CEO 节点更清晰 |
| MANAGER 节点 | manager_plan + manager_review_after_qa（2 个节点） | Manager C 额外引入了 QA 后的 Manager 审阅节点，比 Manager A 设计更完善 |
| WORKER 节点（Send API 并发） | worker_execute（单次顺序执行） | 无并发，PoC 合理简化 |
| QA 节点 | qa_review | 一致 |
| DELIVER 节点 | 未实现（ceo_approve 直接输出 final_result） | PoC 简化 |
| CLARIFY 节点 | 未实现 | PoC 无 interrupt，不需要 |
| CEO 后条件边（approve/clarify/reject） | 无（ceo_dispatch 固定边到 manager_plan） | CEO 在 PoC 中无决策分支，自动下发 |
| QA 后条件边（passed/retry/escalate） | manager_review_after_qa 后条件边（ceo_approve/worker_execute/ceo_handle_escalation） | 路由逻辑等价，但放在 manager_review_after_qa 而非 qa_review 后面（设计更合理，Manager 先审阅再路由） |

**结论**：Graph 核心流转逻辑一致（CEO->Manager->Worker->QA->重试/通过/上报），但节点粒度和高级特性（interrupt、Send API、CLARIFY 回路）未实现。

---

### 二、Bootstrap 顺序

- **判定：N/A（不适用）**

- **说明**：

Manager C 的 demo.py 不涉及 HR/IT 的 agent 实例创建顺序问题。demo.py 的启动流程如下：

1. 构建 `MemorySaver` checkpointer
2. 调用 `build_graph(checkpointer)` 编译 Graph（此时注册所有节点函数引用，不创建 agent 实例）
3. 构建 `initial_state`（填入合同元信息）
4. 调用 `graph.stream(initial_state, config)` 开始执行

当前 PoC 架构中，节点函数（ceo_dispatch, manager_plan 等）是纯函数，不依赖预创建的 agent 实例。角色身份通过 `role` 字符串参数传入工具函数，而非通过 agent 对象。因此不存在 "CEO 先于 HR/IT 启动会卡死" 的问题。

**但需注意**：当未来迁移到真实 LLM agent（每个节点绑定独立 agent 实例 + tool binding）时，Manager A 的架构文档未明确 agent 创建顺序依赖。如果 CEO agent 创建时需要查询 HR 的 org.yaml 或 IT 的工具注册表，则确实需要先创建 HR/IT agent。这是一个**潜在的未来风险**，建议在 Phase L2 文档中补充。

---

### 三、代码质量

#### 3.1 测试结果

```
测试结果：40/40 PASS（0.24 秒完成）
```

测试覆盖 7 个测试类：
- TestPermissionEnforcement: 12 个测试 -- 权限矩阵严格执行
- TestMailRouting: 10 个测试 -- Chain of Command 邮件路由
- TestContractPipeline: 3 个测试 -- 完整 PASS 流程端到端
- TestQARetry: 2 个测试 -- FAIL + 重试机制
- TestMaxAttemptsEscalation: 3 个测试 -- 超出重试上限上报
- TestWorkerConstraints: 3 个测试 -- Worker 分支保护
- TestBreakDownTask + TestQAVerdictLogic: 7 个测试 -- 工具单元测试

#### 3.2 安全风险

**风险 1：权限校验可被绕过（中等风险）**

`permissions.py` 中的 `check_tool_permission()` 和 `check_mail_permission()` 是独立函数，不是装饰器或中间件。工具函数通过主动调用来校验：

```python
# ceo_tools.py
def generate_contract(role, ...):
    check_tool_permission(role, "generate_contract")  # 主动调用
    ...
```

如果开发者新增工具时忘记调用 `check_tool_permission()`，该工具就没有权限校验。这是一个**约定而非强制**的模式。

**建议**：后续可用装饰器模式改造：
```python
@require_permission("generate_contract")
def generate_contract(role, ...):
    ...
```

**风险 2：mail.py 的 from_role 由调用方传入（中等风险）**

`send_mail(from_role, to_role, ...)` 的 `from_role` 参数是由节点代码显式传入的，而非由系统自动填充。

对比 Manager B 的 mail-protocol.yaml 设计：
```yaml
enforced_overrides:
  from: "SYSTEM_SET:caller_agent_id"  # cannot be spoofed
```

Manager B 明确要求 `from` 字段必须由系统自动设置，不能由 agent 伪造。而 Manager C 的实现中，如果节点代码写错 `from_role`（例如 worker 节点传入 `from_role="ceo"`），权限校验会阻止（因为 `check_mail_permission("ceo", "manager")` 会通过），但语义上是伪造了发件人。

**当前缓解**：在 PoC 阶段，节点代码由开发者编写（非 LLM 生成），因此 `from_role` 不会被恶意篡改。但这**不满足 Manager B 的安全设计要求**。

**建议**：`send_mail` 应从执行上下文自动获取 caller 身份，而非依赖参数传入。

**风险 3：role 参数信任问题（低风险）**

所有工具函数依赖 `role` 参数来做权限判断，但 `role` 是由上层节点代码传入的。如果 LLM 在生产环境控制了节点逻辑，理论上可以传入错误的 role 绕过校验。

**当前缓解**：PoC 阶段节点函数是硬编码的，不由 LLM 动态生成。

#### 3.3 代码质量优点

1. **清晰的分层架构**：state.py / graph.py / permissions.py / mail.py / nodes/ / tools/ 职责分明
2. **Annotated reducer 正确使用**：`mail_log: Annotated[list[MailMessage], add]` 确保并行节点的邮件追加语义
3. **完善的测试覆盖**：40 个测试涵盖权限、路由、端到端、重试、上报各场景
4. **demo.py 三场景演示**：PASS / FAIL+重试 / 上报 三个场景均可运行，支持 monkey-patch 切换
5. **日志完备**：所有工具和节点都有 logging 输出，便于调试
6. **类型注解完整**：TypedDict、Literal、Annotated 使用规范

---

### 四、缺失功能

#### 4.1 Ownership 机制

- **判定：未实现**

CEO 要求"合同收到后必须回复（Accept/Reject），不回复算违规"。

Manager B 的 mail-protocol.yaml 中定义了合同状态机：
```
pending → accepted → in_progress → review → passed/failed
```
其中 `pending → accepted` 的转换触发条件是 "worker reads and acknowledges contract"。

Manager C 的实现中，合同下发后 Worker 直接开始执行（`worker_execute` 节点），没有 Accept/Reject 步骤。`NexusContractState` 中也没有 `ownership_status` 或 `accepted` 字段。

#### 4.2 DoubleCheck 模式

- **判定：未实现**

CEO 要求"合同可以设置 check_after 定时回查"。

三份交付物中均未提及 `check_after` 字段或定时回查机制。Manager A 的 State Schema 中没有 `check_after` 字段，Manager B 的 mail-protocol.yaml 的合同状态机也没有定时检查逻辑，Manager C 的代码更是完全没有涉及。

---

### 五、总体判定：CONDITIONAL PASS

三份交付物展示了完整的 PoC 设计-实现链路，架构设计（Manager A）提供了清晰的目标蓝图，权限系统（Manager B）定义了严格的安全边界，工程实现（Manager C）交付了可运行、全测试通过的代码。

核心能力（CEO->Manager->Worker->QA 流转、权限矩阵、邮件路由、重试/上报机制）在 PoC 层面验证成功。

但存在设计与实现的粒度差异（PoC 简化是合理的），以及 2 个 CEO 明确要求的功能缺失。

---

### 六、需要修复的项目列表

#### 必须修复（Blocker）

| # | 项目 | 负责 Manager | 说明 |
|---|------|-------------|------|
| B-01 | mail.py 的 from_role 应由系统自动填充 | Manager C | 当前 from_role 由调用方传入，不满足 Manager B 的 `SYSTEM_SET:caller_agent_id` 安全要求。建议在节点注册时绑定 role，send_mail 从上下文获取 |
| B-02 | 违规通信审计记录缺失（C-06） | Manager C | Manager B 要求违规通信记录到 mail_rejections，当前只是 raise PermissionError，没有审计日志 |

#### 应该修复（Major）

| # | 项目 | 负责 Manager | 说明 |
|---|------|-------------|------|
| M-01 | Ownership 机制 | Manager A + C | 需要在 State 中加入 contract_accepted 字段，Worker 节点增加 Accept/Reject 逻辑 |
| M-02 | DoubleCheck 模式 | Manager A + C | 需要在 State 中加入 check_after 字段，Graph 中加入定时触发的回查节点或边 |
| M-03 | 邮件类型校验缺失 | Manager C | mail-protocol.yaml 定义 12 种邮件类型及其 sender/receiver 约束，代码中 msg_type 为自由字符串，无校验 |
| M-04 | 权限校验改为装饰器模式 | Manager C | 避免新工具遗漏 check_tool_permission 调用，改为 @require_permission 装饰器强制 |

#### 建议改进（Minor）

| # | 项目 | 负责 Manager | 说明 |
|---|------|-------------|------|
| m-01 | State Schema 对齐文档 | Manager A + C | 建议 Manager C 补充一份 PoC-to-Production 的字段映射表，说明哪些 Manager A 字段在后续 Phase 中补充 |
| m-02 | roles.yaml 到 permissions.py 的自动加载 | Manager C | 当前 permissions.py 硬编码角色，建议后续从 roles.yaml 动态加载，确保单一 source of truth |
| m-03 | create_contract 工具实现（C-07） | Manager C | roles.yaml 定义了 create_contract（Manager 级别），但代码中 Manager 使用的是 assign_worker，无 create_contract 工具 |
| m-04 | current_phase 改为枚举类型 | Manager C | 当前 current_phase 是自由字符串，建议改为 Literal 枚举，与 Manager A 的 ContractStatus 对齐 |

---

*报告结束。如有疑问请通过合同系统联系 QA Manager。*
