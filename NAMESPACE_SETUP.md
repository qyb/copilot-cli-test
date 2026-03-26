# Network Namespace 验证环境设置指南

## 拓扑概览

```
┌─────────────────────────────────────────────────────────────┐
│                     宿主环境 (host namespace)                 │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              router.py 程序 (运行中)                  │   │
│  │  - NAT转发逻辑                                      │   │
│  │  - 处理 veth 接口的数据包                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  veth_host_a ←→ veth_ns_a                veth_host_b ←→ veth_ns_b
│  10.0.0.1/24                              10.0.1.1/24      │
│                                                              │
└──────────────┬──────────────────────────────┬────────────────┘
               │                              │
          ┌────▼──────────┐          ┌───────▼─────┐
          │ test_client   │          │ test_target │
          │ namespace     │          │ namespace   │
          │               │          │             │
          │ veth_ns_a     │          │ veth_ns_b   │
          │ 10.0.0.2/24   │          │ 10.0.1.2/24 │
          └────────────────┘          └─────────────┘
               (发包端)                   (接收端)
```

## 环境信息

- **开发机**: 单台主机
- **宿主 namespace**: 运行 router.py 程序
- **test_client namespace**: 模拟源端，从 10.0.0.2 发包
- **test_target namespace**: 模拟目标端，在 10.0.1.2 接收包
- **veth 对**:
  - veth_a: 宿主端 (veth_host_a) ↔ 客户端 namespace (veth_ns_a)
  - veth_b: 宿主端 (veth_host_b) ↔ 目标端 namespace (veth_ns_b)

## 前置条件

- 需要 `root` 权限（执行 `sudo`）
- 已安装: `ip`, `tcpdump`, `ping`, `netcat` 等网络工具
- router.py 已准备好并能在宿主环境运行

---

## 设置步骤

### 第1步：创建 Network Namespaces

创建两个隔离的网络命名空间用于测试。

```bash
# 创建客户端命名空间
sudo ip netns add test_client

# 创建目标端命名空间
sudo ip netns add test_target

# 验证创建成功
sudo ip netns list
```

**预期输出:**
```
test_client
test_target
```

---

### 第2步：创建 Veth 对

创建两对虚拟网络接口，连接宿主与各个命名空间。

```bash
# 创建 veth 对 A：用于 test_client 连接
sudo ip link add veth_host_a type veth peer name veth_ns_a

# 创建 veth 对 B：用于 test_target 连接
sudo ip link add veth_host_b type veth peer name veth_ns_b

# 将 veth_ns_a 移入 test_client namespace
sudo ip link set veth_ns_a netns test_client

# 将 veth_ns_b 移入 test_target namespace
sudo ip link set veth_ns_b netns test_target

# 验证接口创建
ip link show | grep veth
```

**预期输出：** 应该看到 veth_host_a 和 veth_host_b

---

### 第3步：配置宿主端 IP 地址

```bash
# 为宿主端 veth 接口配置 IP
sudo ip addr add 10.0.0.1/24 dev veth_host_a
sudo ip addr add 10.0.1.1/24 dev veth_host_b

# 启用接口
sudo ip link set veth_host_a up
sudo ip link set veth_host_b up

# 验证
ip addr show veth_host_a
ip addr show veth_host_b
```

---

### 第4步：配置客户端 Namespace

```bash
# 进入 test_client 命名空间并配置网络
sudo ip netns exec test_client ip addr add 10.0.0.2/24 dev veth_ns_a
sudo ip netns exec test_client ip link set veth_ns_a up
sudo ip netns exec test_client ip link set lo up

# 配置默认路由：所有流量通过网关 10.0.0.1
sudo ip netns exec test_client ip route add default via 10.0.0.1

# 验证配置
sudo ip netns exec test_client ip addr show
sudo ip netns exec test_client ip route show
```

**预期输出（路由）：**
```
default via 10.0.0.1 dev veth_ns_a
10.0.0.0/24 dev veth_ns_a proto kernel scope link src 10.0.0.2
```

---

### 第5步：配置目标端 Namespace

```bash
# 进入 test_target 命名空间并配置网络
sudo ip netns exec test_target ip addr add 10.0.1.2/24 dev veth_ns_b
sudo ip netns exec test_target ip link set veth_ns_b up
sudo ip netns exec test_target ip link set lo up

# 配置默认路由：所有流量通过网关 10.0.1.1
sudo ip netns exec test_target ip route add default via 10.0.1.1

# 验证配置
sudo ip netns exec test_target ip addr show
sudo ip netns exec test_target ip route show
```

---

### 第6步：验证基础连通性（可选，setup前测试）

```bash
# 测试宿主能否 ping 通两个 namespace
ping -c 2 10.0.0.2
ping -c 2 10.0.1.2

# 测试客户端能否 ping 通宿主
sudo ip netns exec test_client ping -c 2 10.0.0.1

# 测试客户端能否 ping 通目标端（通过宿主转发）
sudo ip netns exec test_client ping -c 2 10.0.1.1
```

---

## 启动 Router 和测试

### 步骤 7：启用宿主 IP 转发

```bash
# 启用 IP 转发
sudo sysctl -w net.ipv4.ip_forward=1

# 验证
sysctl net.ipv4.ip_forward
```

**预期输出:** `net.ipv4.ip_forward = 1`

---

### 步骤 8：启动 Router 程序

在宿主环境运行 router，监听 veth_host_a 和 veth_host_b：

```bash
cd /home/qyb/copilot-test

# 在独立终端运行 router（使用宿主所有网络接口）
sudo .venv/bin/python router.py --interface veth_host_a --interface veth_host_b --nat-mode --loglevel DEBUG

# 或者简化版：自动扫描本地接口
sudo .venv/bin/python router.py --nat-mode --loglevel DEBUG
```

**预期：** Router 程序正常启动，输出日志信息

---

### 步骤 9：准备 Tcpdump 监控（每个终端一个）

在三个不同的终端中分别运行以下命令：

**终端 1 - 监控宿主 veth_host_a（入站）**
```bash
sudo tcpdump -i veth_host_a -n -v 'ip or arp' 2>&1 | tee /tmp/tcpdump_host_a.log
```

**终端 2 - 监控宿主 veth_host_b（出站）**
```bash
sudo tcpdump -i veth_host_b -n -v 'ip or arp' 2>&1 | tee /tmp/tcpdump_host_b.log
```

**终端 3 - 监控客户端内部流量**
```bash
sudo ip netns exec test_client tcpdump -i veth_ns_a -n -v 'ip or arp' 2>&1 | tee /tmp/tcpdump_client.log
```

**终端 4 - 监控目标端内部流量**
```bash
sudo ip netns exec test_target tcpdump -i veth_ns_b -n -v 'ip or arp' 2>&1 | tee /tmp/tcpdump_target.log
```

---

### 步骤 10：运行测试（新终端）

**测试 1 - 基础 Ping 测试**
```bash
# 从客户端 namespace ping 目标端
sudo ip netns exec test_client ping -c 4 10.0.1.2
```

**测试 2 - TCP 连接测试**

在目标端启动简单的 nc 服务器：
```bash
# 在目标端监听端口 8888
sudo ip netns exec test_target nc -l -p 8888
```

从客户端发起连接：
```bash
# 从客户端连接到目标端
sudo ip netns exec test_client nc -zv 10.0.1.2 8888
```

**测试 4 - HTTP 测试**

使用已有的 test.py HTTP 服务：
```bash
# 在宿主启动 test.py HTTP 服务（如需要）
# 或在目标端启动 HTTP 服务
sudo ip netns exec test_target python3 -m http.server 8080

# 从客户端访问
sudo ip netns exec test_client curl -v http://10.0.1.2:8080/
```

---

## 故障排查

### 问题 1：veth 接口不显示
**解决:**
```bash
ip link show
sudo ip netns exec test_client ip link show
```

### 问题 2：无法 ping 通
**检查列表：**
```bash
# 1. 检查 IP 地址配置
ip addr show
sudo ip netns exec test_client ip addr show

# 2. 检查路由表
ip route show
sudo ip netns exec test_client ip route show

# 3. 检查接口状态
ip link show
sudo ip netns exec test_client ip link show

# 4. 检查 IP 转发
sysctl net.ipv4.ip_forward
```

### 问题 3：Router 程序无法接收包
**检查：**
```bash
# 查看 router 日志
sudo tail -f /var/log/router.log  # 如果有日志

# 用 tcpdump 验证包是否到达
sudo tcpdump -i veth_host_a -n
```

---

## 后续实验任务

1. ✅ 创建 namespaces 和 veth（用户执行）
2. ✅ 配置 IP 地址（用户执行）
3. ✅ 启动 Router 和 tcpdump 监控（用户执行）
4. ⏳ 运行测试并收集数据包（等待用户通知）
5. 分析 tcpdump 输出，验证 NAT 转换正确性
6. 测试各种场景（TCP/UDP/ICMP/分片等）
7. 生成验证报告

---

## 所需时间估计

- **初始设置**: 5-10 分钟
- **验证基础连通性**: 5 分钟
- **启动 Router + tcpdump**: 2 分钟
- **运行测试**: 10-20 分钟（取决于测试数量）

---

## 检查清单

在通知我准备完成前，请确保：

- [ ] 两个 namespaces 已创建
- [ ] 四个 veth 接口已创建并分配到正确的 namespace
- [ ] 所有 IP 地址已正确配置
- [ ] IP 转发已启用
- [ ] 基础连通性测试通过（至少能 ping 通）
- [ ] Router 程序已启动
- [ ] tcpdump 监控终端已就绪
- [ ] 准备好运行实际测试

