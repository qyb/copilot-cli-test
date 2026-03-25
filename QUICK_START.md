# 快速参考 - test.py HTTP API和单元测试

本文件提供快速命令参考。详细说明请见 [docs/test.md](./docs/test.md)。

## 安装

```bash
# 创建虚拟环境和安装依赖
make install

# 或手动安装
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行test.py服务器

```bash
# 标准启动
python test.py

# 指定主机和端口
python test.py --host 0.0.0.0 --port 8888

# 调试模式
python test.py --debug

# 使用启动脚本（推荐）
./start_test_server.sh
```

## HTTP API - 快速命令

### 基础命令

```bash
# 健康检查
curl http://10.0.0.20:8888/health

# 获取配置
curl http://10.0.0.20:8888/config

# 获取最后的测试结果
curl http://10.0.0.20:8888/test/results

# 获取测试状态
curl http://10.0.0.20:8888/test/status
```

### 运行测试

```bash
# 运行所有测试
curl -X POST http://10.0.0.20:8888/test/all

# 单个测试
curl -X POST http://10.0.0.20:8888/test/route_table
curl -X POST http://10.0.0.20:8888/test/connectivity
curl -X POST http://10.0.0.20:8888/test/basic_nat
curl -X POST http://10.0.0.20:8888/test/tcp
curl -X POST http://10.0.0.20:8888/test/udp
curl -X POST http://10.0.0.20:8888/test/fragmentation
```

### 调试命令

```bash
# 查看路由表
curl http://10.0.0.20:8888/debug/routes

# 查看网络接口
curl http://10.0.0.20:8888/debug/interfaces

# 检查router进程
curl http://10.0.0.20:8888/debug/processes
```

### 更新配置

```bash
curl -X PUT http://10.0.0.20:8888/config \
  -H "Content-Type: application/json" \
  -d '{
    "router_ip": "10.0.0.10",
    "test_machine_ip": "10.0.0.20",
    "target_network": "192.168.1.0/24",
    "target_ip": "192.168.1.100"
  }'
```

## 单元测试 - 快速命令

```bash
# 运行所有单元测试
make test

# 或直接使用pytest
pytest tests/ -v

# 快速测试（仅结构）
make test-fast

# 详细输出
make test-verbose

# 覆盖率报告
make test-coverage
```

## 集成测试

```bash
# 使用integration_test.py（需要test.py正在运行）
make test-integration

# 或直接运行
python integration_test.py http://10.0.0.20:8888
```

## 完整工作流示例

### 场景1：本地开发与测试

```bash
# 终端1：启动测试服务器
python test.py

# 终端2：运行单元测试
pytest tests/ -v

# 终端3：运行集成测试
python integration_test.py http://localhost:8888
```

### 场景2：完整验证

```bash
# 1. 确保路由已配置
sudo ip route add 192.168.1.0/24 via 10.0.0.10
ip route show

# 2. 启动test.py
python test.py

# 3. 运行完整测试套件
curl -X POST http://localhost:8888/test/all | jq

# 4. 查看详细结果
curl http://localhost:8888/test/results | jq '.tests[] | {name, passed, duration_ms}'
```

### 场景3：持续集成

```bash
# 运行所有测试
make test test-coverage

# 生成覆盖率报告
cat htmlcov/index.html
```

## Makefile 便捷命令

```bash
make help              # 显示所有可用命令
make install           # 安装依赖
make test              # 运行单元测试
make test-coverage     # 生成覆盖率报告
make run-test-server   # 启动test.py
make test-integration  # 运行集成测试
make clean             # 清理临时文件
make docs              # 显示文档导航
```

## 7个核心测试用例

| 测试名 | 端点 | 描述 |
|---|---|---|
| route_table | `/test/route_table` | 验证路由表配置 |
| connectivity | `/test/connectivity` | 验证到路由器的连接 |
| basic_nat | `/test/basic_nat` | 验证NAT源地址转换 |
| tcp | `/test/tcp` | 验证TCP NAT状态 |
| udp | `/test/udp` | 验证UDP NAT转换 |
| fragmentation | `/test/fragmentation` | 验证大包分片 |
| tcp_urg | 不可直接调用 | 验证TCP URG标志 |

## 常见问题

### Q: test.py启动失败，提示"No module named flask"

**A:** 运行 `make install` 或 `pip install -r requirements.txt`

### Q: 所有测试都失败

**A:** 检查：
```bash
curl http://localhost:8888/debug/routes
curl http://localhost:8888/debug/interfaces
ping 10.0.0.10
ip route show
```

### Q: 测试超时

**A:** 更新超时配置：
```bash
curl -X PUT http://localhost:8888/config \
  -H "Content-Type: application/json" \
  -d '{"test_timeout": 10}'
```

## 文档导航

- **[docs/test.md](./docs/test.md)** - 完整的test.py使用指南
- **[docs/verify.md](./docs/verify.md)** - 验证场景和故障排查
- **[docs/env.md](./docs/env.md)** - sudo配置
- **[AGENTS.md](./AGENTS.md)** - VPS部署拓扑
- **[README.md](./README.md)** - 项目概述
