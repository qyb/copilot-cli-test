# Linux User-Mode IPv4 Router

一个用Python Scapy框架实现的Linux用户态IPv4路由转发程序。

## 概述

该项目实现了一个轻量级的IPv4路由器，运行在Linux用户空间，通过接管网卡接口实现数据包的捕获、路由表查询和转发功能。

### 核心特性

- **用户态运行**：无需内核模块，便于开发和测试
- **IPv4路由转发**：支持标准的路由表查询和转发
- **Packet Crafting**：使用Scapy库灵活处理网络数据包
- **动态路由配置**：支持运行时路由表修改

## 系统要求

- Linux操作系统（推荐Ubuntu 18.04+）
- Python 3.8+
- root权限（用于访问原始套接字和网卡接口）
- libpcap库：`sudo apt-get install libpcap-dev`

## 安装

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 快速开始

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行路由器（需要root权限）
sudo ./.venv/bin/python router.py
```

## 项目结构

```
├── router.py           # 主程序入口
├── router/             # 路由器核心模块
│   ├── __init__.py
│   ├── forwarding.py   # 转发逻辑
│   ├── route_table.py  # 路由表管理
│   └── packet_handler.py # 数据包处理
├── tests/              # 单元测试
├── README.md           # 本文件
├── requirements.txt    # Python依赖
└── .gitignore          # Git忽略配置
```

## 使用示例

详见 `AGENTS.md` 中的使用指南。

## 技术架构

### 数据流

1. **包捕获**：使用Scapy sniff()监听网卡
2. **路由查询**：在本地路由表中查询目标网络
3. **转发决策**：根据查询结果转发、丢弃或本地处理
4. **包修改**：调整TTL、重计算校验和、修改MAC地址
5. **包发送**：通过目标网卡发出修改后的包

### 关键模块

- **route_table.py**：维护IPv4路由表，支持CIDR匹配
- **forwarding.py**：实现IPv4转发逻辑和TTL处理
- **packet_handler.py**：数据包捕获、解析和发送

## 注意事项

- 必须以root权限运行以访问原始套接字
- 可能与系统内核路由栈产生冲突，建议在隔离环境测试
- 某些操作系统可能需要禁用内核路由或使用网络命名空间隔离

## 贡献

欢迎提交issues和pull requests！

## 许可

MIT License
