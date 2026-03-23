# 网络验证指南

本文档详细说明如何在真实VPS环境中验证IPv4 NAT路由器的功能。

## 网络拓扑

```
┌─────────────────────────────────────────────────────────────────────┐
│                        云服务商公网/云内网                           │
└──────────────┬──────────────────────────────────────────┬───────────┘
               │                                          │
         ┌─────▼──────┐  eth0                     ┌──────▼─────┐  eth0
         │   VPS A    │  (无公网IP)              │   VPS B    │  (无公网IP)
         │ 路由器     │                           │  源端/测试 │
         └─────┬──────┘                           └──────┬─────┘
               │                                         │
               │ eth1                              eth1 │
               │ 10.0.0.10 (示例)                  10.0.0.20 (示例)
               │                                         │
               └─────────────────┬─────────────────────┘
                        私网 10.0.0.0/24
```

## 环境配置步骤

### 1. VPS A 配置（路由器机器）

#### 1.1 网卡配置

```bash
# 查看现有网卡
ip link show

# 配置内网网卡（eth1），假设私网网段为 10.0.0.0/24
sudo ip addr add 10.0.0.10/24 dev eth1
sudo ip link set eth1 up

# 验证
ip addr show eth1
```

#### 1.2 启用IP转发

```bash
# 临时启用（重启后失效）
sudo sysctl -w net.ipv4.ip_forward=1

# 永久启用
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

#### 1.3 运行路由器程序

```bash
cd /path/to/project
source .venv/bin/activate

# 以root权限运行路由器（需要访问raw socket）
sudo -E .venv/bin/python router.py --interface eth1 --nat-mode
```

### 2. VPS B 配置（源端机器）

#### 2.1 网卡配置

```bash
# 配置内网网卡（eth1）
sudo ip addr add 10.0.0.20/24 dev eth1
sudo ip link set eth1 up

# 验证
ip addr show eth1
```

#### 2.2 配置路由表

```bash
# 添加默认路由指向VPS A的内网IP
# 示例：将目标网络 192.168.1.0/24 的流量通过VPS A转发
sudo ip route add 192.168.1.0/24 via 10.0.0.10

# 查看路由表
ip route show

# （可选）如果需要所有流量都通过VPS A作为网关
# sudo ip route add 0.0.0.0/0 via 10.0.0.10
```

## 验证场景

### 场景1：基本NAT转换验证

#### 目标
验证从VPS B发出的包，通过VPS A的NAT转换后，源地址被正确修改。

#### 步骤

**VPS A上（准备抓包）**：
```bash
# 在eth1上抓取通过转发的包
sudo tcpdump -i eth1 -n "ip src 10.0.0.20" -w /tmp/outgoing.pcap

# 另一个终端实时查看
sudo tcpdump -i eth1 -n "ip src 10.0.0.20"
```

**VPS B上（发送测试包）**：
```bash
# 发送测试包到目标网络 192.168.1.100
ping -c 3 192.168.1.100

# 或使用curl测试HTTP
curl http://192.168.1.100:80
```

#### 预期结果
- VPS A上能捕获来自B的包
- 转发出去的包源地址应为 10.0.0.10（而非10.0.0.20）
- 回程包目标地址应被改回 10.0.0.20

### 场景2：TCP连接NAT验证

#### 目标
验证TCP连接的全生命周期NAT转换。

#### 步骤

**VPS A上**：
```bash
# 启用NAT连接状态追踪日志
sudo python router.py --interface eth1 --nat-mode --debug

# 抓取TCP流
sudo tcpdump -i eth1 -n "tcp" -w /tmp/tcp_flow.pcap
```

**VPS B上**：
```bash
# 建立TCP连接（以nc或telnet为例）
nc -zv 192.168.1.100 80

# 或HTTP连接
curl -v http://192.168.1.100/
```

#### 验证项
- [ ] 初始SYN包源地址被改为10.0.0.10
- [ ] SYN+ACK回程包目标地址被改回10.0.0.20
- [ ] 后续数据包源地址一致为10.0.0.10
- [ ] FIN/RST包的地址转换保持一致

### 场景3：性能验证

#### 目标
验证NAT转换的吞吐量和延迟。

#### 步骤

**VPS A上**：
```bash
# 启动iperf3服务器
iperf3 -s -B 192.168.1.100 &

# 监控转发性能
watch -n 1 'ip -s link show eth1'
```

**VPS B上**：
```bash
# 运行iperf3客户端
iperf3 -c 192.168.1.100 -t 30 -R

# 查看性能指标（吞吐量、延迟）
```

### 场景4：调试包转发

#### 启用详细日志

```bash
# 在VPS A上运行路由器时启用调试
sudo python router.py \
    --interface eth1 \
    --nat-mode \
    --debug \
    --log-level DEBUG \
    --log-file /tmp/router.log

# 实时查看日志
tail -f /tmp/router.log

# 搜索特定源IP的转换
grep "10.0.0.20" /tmp/router.log
```

## 故障排查

### 问题1：B无法到达目标网络

```bash
# VPS B上检查
ip route show        # 确认路由规则存在
ping -c 1 10.0.0.10  # 确认能reach VPS A

# VPS A上检查
sudo tcpdump -i eth1 -n  # 查看是否收到包
```

### 问题2：NAT转换不生效

```bash
# VPS A上查看NAT状态表
sudo python -c "from router import nat_table; print(nat_table.get_connections())"

# 确认路由器正常运行
ps aux | grep router.py

# 查看网卡上的流量统计
ip -s link show eth1
```

### 问题3：包丢失或乱序

```bash
# 检查路由器日志中的丢包统计
grep -i "drop\|error" /tmp/router.log

# 用tcpdump追踪完整流程
sudo tcpdump -i any -n "ip" -w /tmp/full_trace.pcap
# 然后用Wireshark分析
```

## 高级验证

### 验证连接超时处理

```bash
# VPS B上连接后立即断开
nc 192.168.1.100 80 < /dev/null

# VPS A上监测NAT表清理
sudo python router.py --interface eth1 --nat-mode --debug | grep "timeout\|cleanup"
```

### 验证UDP NAT转换

```bash
# VPS B上发送UDP包
echo "test" | nc -u 192.168.1.100 53

# VPS A上抓包确认
sudo tcpdump -i eth1 -n "udp"
```

### 验证大包分片处理

```bash
# VPS B上发送超过MTU的ping
ping -s 2000 192.168.1.100

# VPS A上确认分片和重组
sudo tcpdump -i eth1 -n "ip[6:2] & 0x1fff != 0"
```

## 性能基准参考

期望的NAT转换性能指标：

| 指标 | 目标 |
|------|------|
| 吞吐量 | > 1 Gbps (取决于VPS配置) |
| 延迟增加 | < 1 ms |
| 每秒连接数 | > 10,000 |
| NAT表条目 | 支持 > 100,000 并发连接 |

## 生产验证清单

- [ ] 路由器能捕获从B发出的所有包
- [ ] NAT源地址正确转换
- [ ] NAT回程目标地址正确转换
- [ ] TCP连接状态正确追踪
- [ ] UDP包正确转换
- [ ] 连接超时自动清理
- [ ] 大包分片正确处理
- [ ] 吞吐量达到预期目标
- [ ] 无包丢失或乱序
- [ ] 日志记录完整无遗漏
