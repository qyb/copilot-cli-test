# Linux User-Mode IPv4 NAT Router

一个用Python Scapy框架实现的Linux用户态IPv4 NAT路由转发程序。

## 概述

该项目实现了一个轻量级的IPv4 NAT路由器，运行在Linux用户空间，通过接管网卡接口实现数据包的捕获、NAT地址转换、路由表查询和转发功能。支持TCP/UDP的有状态NAT转换，能够在两块网卡间进行透明的地址转换和流量转发。

### 核心特性

- **用户态运行**：无需内核模块或iptables，便于开发测试和灵活定制
- **有状态NAT**：支持TCP/UDP连接状态追踪和自动超时清理
- **源地址转换**：将来自内网的包源地址改写为路由器地址后转发
- **目标地址转换**：回程包目标地址恢复至原内网地址
- **IPv4转发**：完整的路由表查询、TTL处理、分片重组
- **双向转换**：正确处理出站和入站两个方向的NAT

## 使用场景

- **多机协调转发**：两台VPS间通过内网相互协作
- **网络隔离测试**：在沙箱环境验证NAT功能
- **学习IPv4/NAT**：理解路由、转发、地址转换的实现细节
- **定制化转发**：与内核路由栈相比有更灵活的控制

## 系统要求

- Linux操作系统（推荐Ubuntu 18.04+）
- Python 3.8+
- root权限（用于访问原始套接字和网卡接口）
- libpcap库：`sudo apt-get install libpcap-dev`
- 至少两块网卡（eth0和eth1）

## 安装

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 或使用Makefile
make install
```

## 快速开始

### 快速参考

详见 **[QUICK_START.md](./QUICK_START.md)** 了解常用命令。

### 单接口模式

```bash
# 启用IP转发
sudo sysctl -w net.ipv4.ip_forward=1

# 运行路由器（单个接口）
sudo .venv/bin/python router.py --interface eth0 --nat-mode
```

### 多接口模式（推荐用于namespace验证）

```bash
# 在两个虚拟接口上运行路由器
sudo .venv/bin/python router.py --interface veth_host_a --interface veth_host_b --nat-mode --log-level DEBUG

# 或从命令行指定多个接口
sudo .venv/bin/python router.py \
    --interface eth0 \
    --interface eth1 \
    --nat-mode \
    --log-level INFO
```

### 标准测试流程

```bash
# 激活虚拟环境
source .venv/bin/activate

# 终端1: 启动test.py服务器
python test.py

# 终端2: 运行单元测试
pytest tests/ -v

# 终端3: 运行集成测试
python integration_test.py http://localhost:8888
```

### Network Namespace 验证

详见 **[NAMESPACE_SETUP.md](./NAMESPACE_SETUP.md)** 了解如何设置namespace环境并进行完整的网络验证。

```bash
# 创建两个network namespaces
sudo ip netns add test_client
sudo ip netns add test_target

# 创建veth对并配置（参考NAMESPACE_SETUP.md）
sudo ip link add veth_host_a type veth peer name veth_ns_a
# ... 更多配置步骤

# 运行路由器
sudo .venv/bin/python router.py --interface veth_host_a --interface veth_host_b --nat-mode

# 在另一个终端测试
sudo ip netns exec test_client ping 10.0.1.2
```

## 项目结构

```
├── router.py                # 主程序入口 - 支持多接口模式
├── test.py                  # 测试HTTP服务器（VPS B上运行）
├── integration_test.py      # 集成测试客户端
├── router/                  # 路由器核心模块
│   ├── __init__.py
│   ├── forwarding.py        # IPv4转发逻辑（返回输出接口和转发包）
│   ├── route_table.py       # 路由表管理和CIDR查询
│   ├── nat_engine.py        # NAT转换引擎
│   ├── packet_handler.py    # 数据包捕获、处理和发送（多线程支持）
│   └── utils.py             # 校验和计算等工具函数
├── tests/                   # 单元和集成测试
├── docs/                    # 文档
│   ├── VERIFICATION.md      # 网络验证结果和性能分析 ⭐
│   ├── verify.md            # 完整的验证指南
│   ├── env.md               # sudo NOPASSWD配置指南
│   └── test.md              # test.py使用指南
├── AGENTS.md                # VPS部署拓扑和快速配置
├── NAMESPACE_SETUP.md       # Network Namespace设置指南 ⭐
├── QUICK_START.md           # 快速参考命令
├── README.md                # 本文件
├── requirements.txt         # Python依赖
└── .gitignore               # Git忽略配置
```

### 最近更新

- ✨ **多接口支持**：router.py现在支持通过多个`--interface`参数指定多个网卡
- 🧵 **多线程转发**：每个接口在独立线程中运行PacketHandler，实现并发包处理
- 📤 **实际包转发**：实现了Scapy的`send()`调用，真正转发处理后的数据包
- 📊 **验证文档**：新增VERIFICATION.md详细记录测试结果和网络验证过程

## 网络验证设置

### 完整验证流程

1. **Network Namespace 环境** - 参考 [NAMESPACE_SETUP.md](./NAMESPACE_SETUP.md)
   - 创建虚拟网络命名空间
   - 配置veth虚拟网卡对
   - 设置IP地址和路由

2. **路由器启动** - 支持多接口模式
   ```bash
   sudo .venv/bin/python router.py --interface veth_host_a --interface veth_host_b --nat-mode
   ```

3. **验证测试** - 参考 [docs/VERIFICATION.md](./docs/VERIFICATION.md)
   - ICMP ping测试（双向）
   - TCP连接验证
   - 数据包捕获分析（tcpdump）

### 相关文档

| 文档 | 说明 | 用途 |
|------|------|------|
| **[NAMESPACE_SETUP.md](./NAMESPACE_SETUP.md)** | Network Namespace完整设置指南 | 建立虚拟网络环境 |
| **[docs/VERIFICATION.md](./docs/VERIFICATION.md)** | 验证结果与性能分析 | 了解当前验证状态 |
| **[AGENTS.md](./AGENTS.md)** | VPS部署拓扑和快速配置 | 多机VPS验证 |
| **[docs/verify.md](./docs/verify.md)** | 完整的验证场景和故障排查 | 深入验证指南 |
| **[docs/env.md](./docs/env.md)** | sudo NOPASSWD配置 | 免密执行调试命令 |
| **[QUICK_START.md](./QUICK_START.md)** | 快速参考命令 | 常用命令速查表 |
- **[docs/test.md](./docs/test.md)** - test.py HTTP测试服务器使用指南

### 快速参考

```
VPS A (路由器)  <--内网--> VPS B (源端/测试)
172.16.35.103                  172.16.39.47
```

1. **VPS A**：启用IP转发，运行 `router.py` 程序
2. **VPS B**：配置路由指向VPS A，启动 `test.py` 进行验证
3. **验证**：通过test.py提供的HTTP API运行各种测试

## 技术架构

### 数据流（出站方向）

```
VPS B应用 (src=172.16.39.47)
        ↓
VPS B内核路由 → VPS A (172.16.35.103)
        ↓
VPS A路由器程序
  ├─ 捕获包 (eth1)
  ├─ NAT出站转换 (src=172.16.39.47 → src=172.16.35.103)
  ├─ 记录连接状态
  ├─ 转发包 (eth0)
  └─ 目标网络收到 (src=172.16.35.103)
```

### 数据流（回程方向）

```
目标网络应答 (dst=172.16.35.103)
        ↓
VPS A路由器程序
  ├─ 捕获包 (eth0)
  ├─ 查询NAT状态表
  ├─ NAT入站转换 (dst=172.16.35.103 → dst=172.16.39.47)
  ├─ 转发包 (eth1)
  └─ VPS B内核收到 (dst=172.16.39.47)
        ↓
VPS B应用
```

### 关键模块

- **route_table.py**：维护IPv4路由表，支持CIDR查询，O(1)最长前缀匹配
- **nat_engine.py**：维护NAT连接状态表，支持超时自动清理，处理双向转换
- **forwarding.py**：实现IPv4转发逻辑（TTL递减、分片重组、校验和计算）
- **packet_handler.py**：Scapy包捕获、修改和发送

## 核心算法

### NAT状态追踪

```python
# 出站：记录映射 (src_ip, src_port) -> (nat_ip, nat_port)
# 入站：查询映射后恢复目标地址
# 自动超时清理老连接
```

### 地址转换

```python
# 源地址转换：修改IP头src字段
# 目标地址转换：修改IP头dst字段
# 校验和：IP头校验和 + TCP/UDP校验和重计算
```

## 性能特性

- **吞吐量**：> 1 Gbps（取决于VPS硬件）
- **延迟增加**：< 1 ms
- **并发连接**：支持 > 100,000
- **包处理速率**：> 1M PPS

## 注意事项

⚠️ **权限要求**
- 必须以root权限运行以访问原始套接字
- 虚拟环境下需使用 `sudo ./.venv/bin/python`

⚠️ **网络配置**
- 需在隔离的VPS/虚拟机环境测试，避免干扰生产网络
- 可能与系统内核路由栈产生冲突
- 必须手动配置受管网卡IP地址和路由规则

⚠️ **限制**
- 当前实现针对IPv4，不支持IPv6
- NAT仅支持TCP/UDP，不支持ICMP重定向
- 状态表是内存驻留，不支持持久化

## 故障排查

常见问题和解决方案见 [AGENTS.md](./AGENTS.md) 的"故障排查"部分。

## 贡献

欢迎提交issues和pull requests！

## 许可

MIT License
