# 环境配置 - sudo NOPASSWD设置

调试中需要执行多个root权限命令（tcpdump、ip、sysctl等），为避免反复输入密码，建议配置sudo NOPASSWD以允许特定命令免密执行。

## 配置方法

### 方案1：允许特定命令免密执行（推荐用于调试）

编辑sudoers文件：

```bash
sudo visudo
```

在文件末尾添加以下行：

```sudoers
# IPv4 NAT Router debugging commands
Defaults:$USER env_keep+="VIRTUAL_ENV PATH PYTHONPATH"

# Python router execution
%sudo ALL=(ALL) NOPASSWD: /usr/bin/python3
%sudo ALL=(ALL) NOPASSWD: /usr/bin/python

# Network diagnosis and packet capture
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/tcpdump
%sudo ALL=(ALL) NOPASSWD: /usr/bin/ip
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/sysctl
%sudo ALL=(ALL) NOPASSWD: /bin/watch

# Process management
%sudo ALL=(ALL) NOPASSWD: /bin/ps
%sudo ALL=(ALL) NOPASSWD: /bin/kill
%sudo ALL=(ALL) NOPASSWD: /bin/pkill

# File operations for debug
%sudo ALL=(ALL) NOPASSWD: /bin/cat
%sudo ALL=(ALL) NOPASSWD: /bin/tail
%sudo ALL=(ALL) NOPASSWD: /bin/grep
```

### 方案2：允许sudo组内的特定用户不输密码（宽松方案）

```bash
sudo usermod -aG sudo $(whoami)  # 确保当前用户在sudo组
```

然后编辑sudoers：

```bash
sudo visudo
```

添加：

```sudoers
%sudo ALL=(ALL) NOPASSWD: ALL
```

⚠️ **注意**：此方案允许所有sudo用户无密码执行任意命令，仅在可信的开发环境使用。

### 方案3：针对虚拟环境路径的免密配置

如果router.py运行在虚拟环境中（`.venv/bin/python`），需要特殊处理：

```bash
sudo visudo
```

添加：

```sudoers
# Virtual environment Python execution
%sudo ALL=(ALL) NOPASSWD: /home/*/copilot-cli-test/.venv/bin/python
%sudo ALL=(ALL) NOPASSWD: /home/*/copilot-cli-test/.venv/bin/python3

# All debugging commands
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/tcpdump, /usr/bin/ip, /usr/sbin/sysctl, /bin/watch, /bin/ps, /bin/kill, /bin/tail, /bin/grep
```

## 验证配置

配置完成后，验证特定命令可免密执行：

```bash
# 测试python（无密码提示）
sudo .venv/bin/python --version

# 测试tcpdump（无密码提示）
sudo tcpdump --version

# 测试ip（无密码提示）
sudo ip link show
```

## 安全建议

1. **最小权限原则**：仅添加必要命令的NOPASSWD规则
2. **定期审计**：检查sudoers文件中的NOPASSWD配置
3. **环境隔离**：在生产环境中使用更严格的权限控制
4. **文件权限**：确保sudoers文件权限为0440（`sudo chmod 0440 /etc/sudoers`）
5. **编辑工具**：始终使用`sudo visudo`编辑sudoers，避免直接编辑（防止语法错误导致系统无法sudo）

## 恢复默认配置

如需恢复为需要输密码的状态，编辑sudoers移除NOPASSWD行：

```bash
sudo visudo
# 删除或注释掉含有 NOPASSWD 的行
```

然后验证：

```bash
# 应该会提示输入密码
sudo ip link show
```
