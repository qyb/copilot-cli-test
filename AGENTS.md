# 网络验证指南 - VPS部署拓扑

本文档说明在真实VPS环境中验证IPv4 NAT路由器的网络拓扑和基础配置。

## 网络拓扑

两台VPS都处于同一私网中，云服务商代理公网连接。每台VPS只有一块eth0网卡连接到云内网。

```
┌─────────────────────────────────────────────────────────┐
│              云服务商公网/云内网  eth0                   │
│  VPS A (路由器)             VPS B (源端/测试)            │
│  10.0.0.10                 10.0.0.20                    │
│  • IP转发启用               • 配置路由指向VPS A          │
│  • 运行router程序           • 发送测试流量               │
└─────────────────────────────────────────────────────────┘
```

## 快速配置参考

### VPS A（路由器机器）

```bash
# 1. 启用IP转发
sudo sysctl -w net.ipv4.ip_forward=1

# 2. 运行路由器（需要root权限和sudo NOPASSWD配置）
sudo ./.venv/bin/python router.py --interface eth0 --nat-mode
```

### VPS B（源端机器）

```bash
# 1. 配置默认路由指向VPS A
# 示例：将目标网络 192.168.1.0/24 流量转发通过VPS A
sudo ip route add 192.168.1.0/24 via 10.0.0.10

# 2. 发送测试包
ping 192.168.1.100
curl http://192.168.1.100:80
```

## 相关文档

- **完整验证指南**：[docs/verify.md](./docs/verify.md) - 详细的验证场景、故障排查和性能测试指南
- **环境配置**：[docs/env.md](./docs/env.md) - 如何配置sudo NOPASSWD以免密执行调试命令
