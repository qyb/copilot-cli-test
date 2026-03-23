# Agent Development Guide

本文档指导使用GitHub Copilot CLI agent在此项目中的工作流程。

## 项目Agents

### 1. 项目探索与分析

**目的**：理解项目结构、依赖关系和设计决策

**用法**：
```bash
copilot explore "How does the routing table work?"
copilot explore "Explain the packet forwarding pipeline"
```

### 2. 代码审查与质量

**目的**：检查代码实现的正确性、安全性和性能

**用法**：
```bash
copilot code-review "Review changes in forwarding.py"
```

### 3. 测试与验证

**目的**：运行单元测试、集成测试和性能测试

**用法**：
```bash
copilot task "Run all unit tests"
copilot task "Test routing table insertion and lookup"
```

### 4. 文档生成

**目的**：生成API文档、架构图和设计说明

**用法**：
```bash
copilot doc "Generate API documentation for route_table.py"
```

## 开发工作流

### 新功能开发流程

1. **规划** - 使用 `copilot explore` 理解相关代码
2. **实现** - 编写代码并通过unit tests验证
3. **审查** - 使用 `copilot code-review` 检查质量
4. **集成** - 提交PR并运行集成测试

### 调试工作流

```bash
# 步骤1：查看错误
copilot explore "Why is packet forwarding failing?"

# 步骤2：找到相关代码
copilot explore "Find all references to packet_handler"

# 步骤3：运行诊断
copilot task "Run diagnostic tests for packet loss"
```

## 常见任务

### 修改路由表实现

```bash
# 1. 理解当前设计
copilot explore "How is the routing table currently organized?"

# 2. 查看实现细节
copilot explore "Show me the route lookup algorithm"

# 3. 进行更改
# ... 手动编辑代码 ...

# 4. 验证
copilot task "Run route_table tests"

# 5. 审查
copilot code-review "Review route_table.py changes"
```

### 优化转发性能

```bash
# 1. 分析当前性能
copilot explore "What are the performance bottlenecks?"

# 2. 查看转发逻辑
copilot explore "Explain the packet forwarding optimization opportunities"

# 3. 运行基准测试
copilot task "Run performance benchmarks"
```

### 添加新功能

```bash
# 1. 规划
copilot explore "Design a new feature: X"

# 2. 实现
# ... 创建新模块或修改现有模块 ...

# 3. 测试
copilot task "Write and run tests for new feature"

# 4. 集成
copilot explore "How does this integrate with existing code?"
```

## 最佳实践

1. **使用 explore agent 进行分析** - 比手动grep快且更准确
2. **在提交前进行代码审查** - 使用 code-review 找出潜在问题
3. **自动化测试** - 使用 task agent 运行测试
4. **文档同步** - 重要更改后更新相关文档

## 常用命令速查

| 任务 | 命令 |
|------|------|
| 项目概览 | `copilot explore "What is the project structure?"` |
| 模块理解 | `copilot explore "Explain the [module_name] module"` |
| 代码查找 | `copilot explore "Find all functions that handle [feature]"` |
| 问题诊断 | `copilot explore "Why does [issue] happen?"` |
| 代码审查 | `copilot code-review "[describe changes]"` |
| 运行测试 | `copilot task "Run tests for [module]"` |
| 构建项目 | `copilot task "Build the project"` |
| 性能分析 | `copilot task "Run performance profiling"` |

## 获取帮助

```bash
# 查看所有可用命令
copilot help

# 查看特定功能文档
copilot help explore
copilot help code-review
```
