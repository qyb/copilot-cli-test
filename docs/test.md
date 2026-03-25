# 测试套件使用指南

本文档说明如何使用test.py和测试框架验证IPv4 NAT路由器的功能。

## 概述

`test.py` 是一个运行在VPS B（测试/源端机器）上的HTTP测试控制器，提供RESTful API让你可以远程或本地执行各种NAT验证测试。

### 核心测试场景

test.py实现了7个核心测试用例，覆盖第一版路由器需要通过的所有主要功能：

1. **route_table** - 验证路由表配置
2. **network_connectivity** - 验证到路由器的网络连接
3. **basic_nat** - 验证基本NAT源地址转换
4. **tcp_connection** - 验证TCP连接的NAT状态追踪
5. **udp_packet** - 验证UDP包的NAT转换
6. **fragmentation** - 验证大包分片处理
7. **tcp_urg** - 验证TCP紧急标志的NAT处理

## 快速开始

### 1. 在VPS B上启动test.py

```bash
cd /home/admin/copilot-cli-test
source .venv/bin/activate

# 默认监听 0.0.0.0:8888
python test.py

# 或指定特定主机和端口
python test.py --host localhost --port 8888 --debug
```

### 2. 验证HTTP服务器正常运行

```bash
# 从任何可访问VPS B的机器执行
curl http://172.16.39.47:8888/health
```

预期响应：

```json
{
  "status": "ok",
  "timestamp": "2026-03-24T08:00:00.000000",
  "test_machine_ip": "172.16.39.47",
  "router_ip": "172.16.35.103"
}
```

## HTTP API 端点

### 配置管理

#### GET /config
获取当前测试配置

```bash
curl http://172.16.39.47:8888/config
```

```json
{
  "test_machine_ip": "172.16.39.47",
  "router_ip": "172.16.35.103",
  "target_network": "125.39.61.0/24",
  "target_ip": "125.39.61.75",
  "test_timeout": 5
}
```

#### PUT /config
更新测试配置

```bash
curl -X PUT http://172.16.39.47:8888/config \
  -H "Content-Type: application/json" \
  -d '{
    "router_ip": "172.16.35.103",
    "test_machine_ip": "172.16.39.47",
    "target_network": "192.168.100.0/24",
    "target_ip": "192.168.100.1",
    "test_timeout": 10
  }'
```

### 测试执行

#### POST /test/all
运行所有7个测试用例

```bash
curl -X POST http://172.16.39.47:8888/test/all
```

响应格式：

```json
{
  "timestamp": "2026-03-24T08:00:00.000000",
  "total": 7,
  "passed": 6,
  "failed": 1,
  "tests": [
    {
      "name": "route_table",
      "description": "Verify route table configuration",
      "passed": true,
      "duration_ms": 45.2,
      "details": {
        "target_route_exists": true,
        "routes": ["default via 172.16.35.103 dev eth0", ...]
      },
      "timestamp": "2026-03-24T08:00:00.000000"
    },
    ...
  ]
}
```

#### 单个测试端点

```bash
# 路由表测试
curl -X POST http://172.16.39.47:8888/test/route_table

# 网络连接测试
curl -X POST http://172.16.39.47:8888/test/connectivity

# 基本NAT测试
curl -X POST http://172.16.39.47:8888/test/basic_nat

# TCP连接测试
curl -X POST http://172.16.39.47:8888/test/tcp

# UDP包测试
curl -X POST http://172.16.39.47:8888/test/udp

# 分片测试
curl -X POST http://172.16.39.47:8888/test/fragmentation
```

每个测试端点返回格式相同，单个测试对象：

```json
{
  "name": "tcp_connection",
  "description": "Verify TCP connection NAT state tracking",
  "passed": true,
  "duration_ms": 234.5,
  "details": {...},
  "timestamp": "2026-03-24T08:00:00.000000"
}
```

### 结果查询

#### GET /test/status
获取当前测试状态

```bash
curl http://172.16.39.47:8888/test/status
```

返回内容：

```json
{
  "test_state": {
    "running": false,
    "last_test": {...},
    "test_results": [],
    "packets_sent": 12,
    "packets_received": 8,
    "errors": []
  }
}
```

#### GET /test/results
获取最后一次测试的完整结果

```bash
curl http://172.16.39.47:8888/test/results
```

### 调试接口

#### GET /debug/routes
查看当前路由表

```bash
curl http://172.16.39.47:8888/debug/routes
```

#### GET /debug/interfaces
查看网络接口配置

```bash
curl http://172.16.39.47:8888/debug/interfaces
```

#### GET /debug/processes
检查router.py进程

```bash
curl http://172.16.39.47:8888/debug/processes
```

## 单元测试

### 运行pytest单元测试

```bash
cd /home/admin/copilot-cli-test

# 运行所有单元测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_api.py -v

# 生成覆盖率报告
pytest tests/ --cov=test --cov-report=html
```

### 单元测试内容

单元测试位于 `tests/test_api.py`，包括：

- **TestNATTestCases**: 验证7个测试用例的结构和初始化
- **TestTestResults**: 验证测试结果的格式和必需字段
- **TestTestSuite**: 验证测试套件工厂函数
- **TestConfigValues**: 验证配置值的有效性

## 测试执行示例

### 场景1：快速验证路由器是否运行

```bash
# 1. 在VPS A上启动router.py
ssh vpsA "sudo .venv/bin/python router.py --interface eth0 --nat-mode"

# 2. 在VPS B上启动test.py
python test.py

# 3. 运行快速测试
curl -X POST http://localhost:8888/test/connectivity
curl -X POST http://localhost:8888/test/route_table

# 4. 检查结果
curl http://localhost:8888/test/status
```

### 场景2：完整验证流程

```bash
# 1. 配置测试参数
curl -X PUT http://localhost:8888/config \
  -H "Content-Type: application/json" \
  -d '{
    "target_ip": "125.39.61.75",
    "target_network": "125.39.61.0/24"
  }'

# 2. 验证配置
curl http://localhost:8888/config

# 3. 运行完整测试套件
curl -X POST http://localhost:8888/test/all

# 4. 分析结果
curl http://localhost:8888/test/results | jq '.tests[] | {name, passed, details}'
```

### 场景3：持续集成（CI）集成

```bash
#!/bin/bash
# 脚本：ci_test.sh

BASE_URL="http://172.16.39.47:8888"

echo "Running NAT router tests..."
RESULT=$(curl -s -X POST $BASE_URL/test/all)

PASSED=$(echo $RESULT | jq '.passed')
FAILED=$(echo $RESULT | jq '.failed')
TOTAL=$(echo $RESULT | jq '.total')

echo "Test Results: $PASSED/$TOTAL passed, $FAILED failed"

if [ "$FAILED" -gt 0 ]; then
  echo "Test failures detected:"
  echo $RESULT | jq '.tests[] | select(.passed == false)'
  exit 1
fi

exit 0
```

## 性能测试

test.py也支持简单的性能指标收集：

```bash
# 运行测试并记录包计数
curl -X POST http://localhost:8888/test/all

# 查看性能指标
curl http://localhost:8888/test/status | jq '.test_state | {packets_sent, packets_received, errors}'
```

## 故障排查

### 问题1: 连接被拒绝

```
curl: (7) Failed to connect to 172.16.39.47 port 8888: Connection refused
```

**解决方案：**
- 验证test.py是否运行：`ps aux | grep test.py`
- 检查防火墙规则：`sudo ufw allow 8888`
- 验证网络连接到VPS B：`ping 172.16.39.47`

### 问题2: 所有测试都失败

```json
{
  "total": 7,
  "passed": 0,
  "failed": 7,
  "tests": [...]
}
```

**解决方案：**
- 检查VPS B的网络配置：`ip addr show eth0`
- 检查到路由器的连接：`ping 172.16.35.103`
- 查看调试信息：`curl http://localhost:8888/debug/routes`
- 检查router.py是否运行在VPS A

### 问题3: 某些测试超时

检查test.py日志中的超时错误，可能是网络延迟。增加timeout：

```bash
curl -X PUT http://localhost:8888/config \
  -H "Content-Type: application/json" \
  -d '{"test_timeout": 10}'
```

## 关键配置说明

### 内网IP配置

test.py默认假设：
- VPS A (路由器): 172.16.35.103
- VPS B (测试机): 172.16.39.47
- 目标网络: 125.39.61.0/24
- 目标IP: 125.39.61.75

如果你的环境不同，使用PUT /config更新这些值。

### 网络路由配置

确保VPS B已配置指向VPS A的路由：

```bash
# 在VPS B上添加路由
sudo ip route add 125.39.61.0/24 via 172.16.35.103

# 验证路由
ip route show
```

## 与docs/verify.md的关系

`test.py` 提供自动化API来执行 `docs/verify.md` 中描述的验证场景。具体对应关系：

| test.py 测试 | docs/verify.md 场景 |
|---|---|
| basic_nat | 场景1: 基本NAT转换验证 |
| tcp_connection | 场景2: TCP连接NAT验证 |
| udp_packet | 高级验证: UDP NAT转换 |
| fragmentation | 高级验证: 大包分片处理 |
| route_table | 全部场景的前置条件 |
| network_connectivity | 全部场景的前置条件 |

## 开发和扩展

### 添加新的测试用例

在 `test.py` 中：

```python
class MyCustomTest(NATTestCase):
    def __init__(self):
        super().__init__("my_test", "Description of my test")
    
    def run(self) -> bool:
        self.start_time = datetime.now()
        try:
            # Implement your test logic
            self.result = True  # or False based on test outcome
        finally:
            self.end_time = datetime.now()
        return self.result

# 将新测试添加到 get_all_tests()
def get_all_tests() -> List[NATTestCase]:
    return [
        # ... existing tests ...
        MyCustomTest(),
    ]

# 添加HTTP端点
@app.route("/test/my_test", methods=["POST"])
def test_my_test():
    if test_state["running"]:
        return jsonify({"error": "Tests already running"}), 409
    
    test = MyCustomTest()
    test.run()
    result = test.get_result()
    
    test_state["last_test"] = result
    return jsonify(result), (200 if result["passed"] else 400)
```

### 集成到CI/CD

示例GitHub Actions工作流：

```yaml
name: NAT Router Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run NAT router tests
        run: |
          # 启动测试服务器
          python test.py &
          sleep 2
          
          # 运行完整测试套件
          curl -X POST http://localhost:8888/test/all > results.json
          
          # 检查结果
          FAILED=$(jq '.failed' results.json)
          if [ "$FAILED" -gt 0 ]; then
            jq '.tests[]' results.json
            exit 1
          fi
```

## 环境需求

- Python 3.8+
- Flask 3.0.0
- requests 2.31.0
- Scapy 2.5.0
- pytest 7.4.0 (用于单元测试)

见 [requirements.txt](../requirements.txt) 获取完整依赖列表。

## 许可证

与主项目相同：MIT License
