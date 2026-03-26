# 关键信息 - Agent 工作须知

## 1. 严格禁止 git commit
agent **不得自行 git commit**，除非用户明确要求。所有代码变动应通过用户确认。

## 2. Agent 环境能力
- Agent 当前开发机器上已经被赋予 **sudo 能力**
- 可以直接执行需要 root 权限的命令 /usr/bin/tcpdump, /usr/sbin/ip, /usr/sbin/sysctl, /usr/bin/watch, /usr/bin/ps, /usr/bin/kill, /usr/bin/tail, /usr/bin/grep, .venv/bin/python3
- 无需额外输入密码

## 3. Python 环境路径
- Python 解释器路径：`.venv/bin/python3`
- 所有 Python 脚本执行都应使用此路径
- 示例：`sudo .venv/bin/python3 router.py --interface veth_host_a --interface veth_host_b --nat-mode --log-level INFO`

## 4. 网络拓扑 - 需更新
**基于 NAMESPACE_SETUP.md 的完整拓扑：**

```
┌─────────────────────────────────────────────────────────────────┐
│                  宿主环境 (host namespace)                       │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │            router.py 程序 (运行中)                        │ │
│  │  - NAT转发逻辑                                           │ │
│  │  - 处理 veth 接口的数据包                               │ │
│  │  - 解析 ip route 并自动监听默认路由接口                  │ │
│  │  - 将目标为外部网络的流量转发到默认网关                 │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  veth_host_a ←→ veth_ns_a        veth_host_b ←→ veth_ns_b     │
│  10.0.0.1/24                     10.0.1.1/24                  │
│                                                                 │
│  eth3 (Gateway Interface) - 缺省路由接口                        │
│  └─ 用于将外部网络流量转发至默认网关                           │
│                                                                 │
└──────────────┬─────────────────────────────┬──────────────────┘
               │                             │
           ┌───▼──────────┐        ┌────────▼──┐
           │ test_client  │        │test_target│
           │ namespace    │        │ namespace │
           │              │        │           │
           │ veth_ns_a    │        │ veth_ns_b │
           │ 10.0.0.2/24  │        │10.0.1.2/24│
           └────────────────┘       └───────────┘
               (发包端)              (接收端)
```

**关键点：**
- Gateway Interface 是系统默认路由指向的网卡
- 用于将 target 为外部网络的流量通过默认网关转发
- Router 需自动解析系统路由表，识别默认网关和关联接口

