#!/usr/bin/env python3
"""
Security Audit for Equipment Scripts - Phase 3C
Checks for:
- Command injection vulnerabilities
- Path traversal issues
- Unsafe file operations
- Hardcoded credentials
- SQL injection
"""

import sys
import re
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SecurityAuditor:
    """Security auditor for equipment scripts"""

    def __init__(self):
        self.issues = []

    def audit_file(self, file_path: Path):
        """Audit a single Python file for security issues"""
        print(f"\n审计文件: {file_path.name}")
        print("-" * 60)

        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')

            # Check for command injection
            self._check_command_injection(file_path, content, lines)

            # Check for path traversal
            self._check_path_traversal(file_path, content, lines)

            # Check for hardcoded credentials
            self._check_hardcoded_credentials(file_path, content, lines)

            # Check for unsafe file operations
            self._check_unsafe_file_ops(file_path, content, lines)

            # Check for SQL injection
            self._check_sql_injection(file_path, content, lines)

            if not any(issue['file'] == str(file_path) for issue in self.issues):
                print("✓ 未发现安全问题")

        except Exception as e:
            print(f"✗ 审计失败: {e}")
            self.issues.append({
                'file': str(file_path),
                'type': 'audit_error',
                'severity': 'error',
                'message': f"无法审计文件: {e}"
            })

    def _check_command_injection(self, file_path: Path, content: str, lines: list):
        """Check for command injection vulnerabilities"""
        # Dangerous patterns: os.system, subprocess with shell=True, eval, exec
        dangerous_patterns = [
            (r'os\.system\s*\(', 'os.system() 调用'),
            (r'subprocess\.[^(]*\([^)]*shell\s*=\s*True', 'subprocess with shell=True'),
            (r'eval\s*\(', 'eval() 调用'),
            (r'exec\s*\(', 'exec() 调用'),
            (r'__import__\s*\(', '__import__() 动态导入'),
        ]

        for pattern, description in dangerous_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1].strip()

                # Check if user input is used (params, args, etc.)
                if re.search(r'(params|args|input|user)', line_content, re.IGNORECASE):
                    self.issues.append({
                        'file': str(file_path),
                        'type': 'command_injection',
                        'severity': 'critical',
                        'line': line_num,
                        'message': f"潜在命令注入: {description}",
                        'code': line_content
                    })
                    print(f"✗ [CRITICAL] 第 {line_num} 行: 潜在命令注入 ({description})")
                    print(f"    {line_content}")

    def _check_path_traversal(self, file_path: Path, content: str, lines: list):
        """Check for path traversal vulnerabilities"""
        # Check for file operations with user-controlled paths
        file_ops = [
            (r'open\s*\([^)]*\bparams', 'open() with params'),
            (r'Path\s*\([^)]*\bparams', 'Path() with params'),
            (r'\.read_text\s*\([^)]*\bparams', 'read_text() with params'),
            (r'\.write_text\s*\([^)]*\bparams', 'write_text() with params'),
        ]

        for pattern, description in file_ops:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1].strip()

                # Check if there's path validation
                context_start = max(0, line_num - 5)
                context = '\n'.join(lines[context_start:line_num])

                if 'resolve()' not in context and 'is_relative_to' not in context:
                    self.issues.append({
                        'file': str(file_path),
                        'type': 'path_traversal',
                        'severity': 'high',
                        'line': line_num,
                        'message': f"潜在路径遍历: {description} 缺少路径验证",
                        'code': line_content
                    })
                    print(f"✗ [HIGH] 第 {line_num} 行: 潜在路径遍历 ({description})")
                    print(f"    {line_content}")

    def _check_hardcoded_credentials(self, file_path: Path, content: str, lines: list):
        """Check for hardcoded credentials"""
        credential_patterns = [
            (r'password\s*=\s*["\'][^"\']{1,}["\']', '硬编码密码'),
            (r'api_key\s*=\s*["\'][^"\']{10,}["\']', '硬编码 API Key'),
            (r'secret\s*=\s*["\'][^"\']{10,}["\']', '硬编码 Secret'),
            (r'token\s*=\s*["\'][^"\']{10,}["\']', '硬编码 Token'),
        ]

        for pattern, description in credential_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1].strip()

                # Ignore test/example values
                if any(test_val in line_content.lower() for test_val in ['test', 'example', 'dummy', 'fake']):
                    continue

                self.issues.append({
                    'file': str(file_path),
                    'type': 'hardcoded_credential',
                    'severity': 'critical',
                    'line': line_num,
                    'message': f"{description}",
                    'code': line_content
                })
                print(f"✗ [CRITICAL] 第 {line_num} 行: {description}")
                print(f"    {line_content}")

    def _check_unsafe_file_ops(self, file_path: Path, content: str, lines: list):
        """Check for unsafe file operations"""
        # Check for file deletion without validation
        if 'os.remove' in content or 'unlink()' in content or 'rmtree' in content:
            matches = re.finditer(r'(os\.remove|\.unlink\(\)|rmtree)\s*\(', content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1].strip()

                # Check if there's a confirmation or validation
                context_start = max(0, line_num - 5)
                context = '\n'.join(lines[context_start:line_num])

                if 'exists()' not in context and 'is_file()' not in context:
                    self.issues.append({
                        'file': str(file_path),
                        'type': 'unsafe_file_operation',
                        'severity': 'medium',
                        'line': line_num,
                        'message': "文件删除操作缺少验证",
                        'code': line_content
                    })
                    print(f"✗ [MEDIUM] 第 {line_num} 行: 文件删除操作缺少验证")
                    print(f"    {line_content}")

    def _check_sql_injection(self, file_path: Path, content: str, lines: list):
        """Check for SQL injection vulnerabilities"""
        # Check for string formatting in SQL queries
        sql_patterns = [
            (r'execute\s*\([^)]*%s[^)]*\)', 'SQL 字符串格式化'),
            (r'execute\s*\([^)]*\.format\(', 'SQL .format() 调用'),
            (r'execute\s*\(\s*f["\']', 'SQL f-string'),
        ]

        for pattern, description in sql_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1].strip()

                # Check if parameterized query (safe)
                if '?' in match.group(0) or re.search(r',\s*\([^)]+\)\s*\)', match.group(0)):
                    continue  # Parameterized query is safe

                # Skip if in comment or docstring
                if line_content.startswith('#') or '"""' in line_content or "'''" in line_content:
                    continue

                self.issues.append({
                    'file': str(file_path),
                    'type': 'sql_injection',
                    'severity': 'critical',
                    'line': line_num,
                    'message': f"潜在 SQL 注入: {description}",
                    'code': line_content
                })
                print(f"✗ [CRITICAL] 第 {line_num} 行: 潜在 SQL 注入 ({description})")
                print(f"    {line_content}")

    def generate_report(self):
        """Generate security audit report"""
        print("\n" + "="*60)
        print("安全审计报告")
        print("="*60)

        if not self.issues:
            print("\n✓ 未发现安全问题")
            return True

        # Group by severity
        critical = [i for i in self.issues if i['severity'] == 'critical']
        high = [i for i in self.issues if i['severity'] == 'high']
        medium = [i for i in self.issues if i['severity'] == 'medium']
        low = [i for i in self.issues if i['severity'] == 'low']

        print(f"\n问题统计:")
        print(f"  严重 (Critical): {len(critical)}")
        print(f"  高危 (High):     {len(high)}")
        print(f"  中危 (Medium):   {len(medium)}")
        print(f"  低危 (Low):      {len(low)}")

        if critical or high:
            print("\n✗ 发现严重或高危安全问题")
            print("\n详细问题列表:")
            for issue in critical + high:
                print(f"\n[{issue['severity'].upper()}] {issue['file']}:{issue.get('line', '?')}")
                print(f"  类型: {issue['type']}")
                print(f"  描述: {issue['message']}")
                if 'code' in issue:
                    print(f"  代码: {issue['code']}")
            return False
        elif medium or low:
            print("\n⚠ 发现中低危安全问题")
            return True

        return True


def main():
    """Main security audit function"""
    print("="*60)
    print("Phase 3C Equipment - 安全审计")
    print("="*60)

    scripts_dir = Path(__file__).parent / "equipment" / "scripts"
    auditor = SecurityAuditor()

    # Audit all Python scripts
    for script_file in scripts_dir.glob("*.py"):
        if script_file.name == "__init__.py":
            continue
        auditor.audit_file(script_file)

    # Generate report
    success = auditor.generate_report()

    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 审计异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
