# QA Validation Framework

`qa/` 提供一个轻量的 Python QA 验证框架，用于执行统一的三层检查：

1. 可运行性（`runnable`）
- 命令是否在超时时间内执行完成
- 退出码是否符合预期

2. 完整性（`completeness`）
- 输出是否包含必需内容
- 输出是否出现禁用内容（如 `Traceback`）

3. 格式正确性（`format`）
- 支持 `json` 与 `regex` 两种校验方式

## 目录

```text
qa/
├── runner.py                # QA CLI 入口
├── specs/
│   ├── sample_success.json  # 可直接运行的示例
│   └── work_order_template.json
└── tests/
    └── mock_task.py         # 本地 smoke 测试脚本
```

## 用法

```bash
python3 qa/runner.py --spec qa/specs/sample_success.json
```

生成机器可读报告：

```bash
python3 qa/runner.py \
  --spec qa/specs/sample_success.json \
  --report-json qa/reports/sample_success_report.json
```

显示被测命令完整输出：

```bash
python3 qa/runner.py --spec qa/specs/sample_success.json --show-output
```

## QA Spec 字段

必需字段：
- `name`: 用例名称
- `command`: 被测命令

可选字段：
- `timeout_seconds` (默认 `60`)
- `expected_exit_code` (默认 `0`)
- `use_shell` (默认 `false`)
- `completeness`
  - `source`: `stdout` / `stderr` / `combined`
  - `required_substrings`: 字符串数组
  - `forbidden_substrings`: 字符串数组
  - `required_regex`: 正则数组
- `format`
  - `type`: `none` / `json` / `regex`
  - `source`: `stdout` / `stderr` / `combined`
  - JSON 模式支持：`required_keys`, `required_paths`
  - Regex 模式支持：`pattern`

## 建议接入方式

1. 每个 agent 关键输出定义一个 spec 文件。
2. CI 中执行 `python3 qa/runner.py --spec ...`。
3. 失败时将 report 反馈回 agent，触发修复循环。
