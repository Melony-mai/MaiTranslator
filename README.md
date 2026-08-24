# MaiTranslator

完全离线的本地中英互译 Windows 应用。基于 **HY-MT1.5-7B** 翻译大模型（GGUF 量化）与 [llama.cpp](https://github.com/ggml-org/llama.cpp) 推理引擎，所有翻译均在本地完成。

> **隐私承诺**：MaiTranslator 不连接互联网、不调用云端 API、无遥测、不上传任何数据。翻译内容、词表、历史记录仅保存在你自己的电脑上。

## 功能特性

| 功能 | 说明 |
| --- | --- |
| 完全离线推理 | 仅使用本地 HY-MT1.5-7B GGUF 模型，GPU 加速优先，显存不足自动降级至 CPU |
| 自动方向检测 | 自动识别中文/英文并选择翻译方向，也可手动指定 |
| 全局划词翻译 | 任意程序中选中文本，按 `Alt + F` 即可翻译，译文自动复制到剪贴板 |
| 悬浮翻译窗 | 展示原文/译文；`Enter` 复制译文，`Esc` 关闭 |
| 本地术语词表 | 自定义术语翻译时优先参考（基于官方术语干预模板） |
| 格式保护 | Markdown、代码块、URL、邮箱、数字、换行等在译文中原样保留 |
| 历史记录 | 本地 SQLite 存储，支持搜索、复制、删除、清空 |
| 浅色 / 深色主题 | 默认跟随系统，可手动切换，即时生效 |
| 右键菜单集成 | 任意文件右键“使用 MaiTranslator 翻译”（HKCU 注册，无需管理员） |
| 系统托盘 | 托盘快捷翻译剪贴板、开机自启开关、引擎状态显示 |
| 日志轮转 | 单文件超过 100 MB 自动轮转覆盖 |

## 系统要求

- Windows 10 / 11（x64）
- NVIDIA GPU（8 GB 显存可完整载入默认模型；显存不足时自动减少 GPU 层数，直至 CPU 回退）
- 无需联网。首次构建/安装依赖包时需要联网下载，之后运行完全离线

## 快速开始（便携版）

1. 下载发布包 `MaiTranslator-*-win64-portable.zip` 并解压
2. 双击 `MaiTranslator.exe`，等待托盘提示“引擎就绪”（首次加载约 10–30 秒）
3. 在任意程序选中文字，按 **Alt + F**
4. 悬浮窗显示译文并已自动复制；`Enter` 再复制，`Esc` 关闭

## 从源码构建

### 1. 环境准备

- Python 3.10+（建议 3.12）
- PowerShell 5.1+（Windows 自带）

### 2. 获取依赖（模型 + 推理引擎）

```powershell
git clone https://github.com/<your-name>/MaiTranslator.git
cd MaiTranslator
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File tools\setup_deps.ps1
```

`tools\setup_deps.ps1` 会自动下载（支持断点续传）：

- [llama.cpp](https://github.com/ggml-org/llama.cpp/releases) CUDA 12.4 预编译二进制 → `vendor\llamacpp\`
- [tencent/HY-MT1.5-7B-GGUF](https://huggingface.co/tencent/HY-MT1.5-7B-GGUF) Q4_K_M 量化模型（约 4.4 GB）→ `models\`

### 3. 运行

```powershell
.venv\Scripts\python app\main.py
```

### 4. 打包发布

```powershell
powershell -ExecutionPolicy Bypass -File tools\build.ps1
```

产物：`dist\MaiTranslator\`（目录）与 `dist\MaiTranslator-1.0.0-win64-portable.zip`

## 使用说明

| 操作 | 方式 |
| --- | --- |
| 划词翻译 | 任意程序选中文本 → `Alt + F` |
| 翻译剪贴板 | 托盘右键 → “翻译剪贴板内容” |
| 翻译文件 | 右键任意文件 → “使用 MaiTranslator 翻译”（首次需在设置页安装右键菜单） |
| 复制译文 | 悬浮窗内按 `Enter`，或点击“复制译文” |
| 关闭悬浮窗 | `Esc` |
| 切换主题 | 设置 → 界面主题（跟随系统 / 浅色 / 深色） |
| 恢复默认参数 | 设置 → “恢复默认参数”（不影响模型路径与开机自启） |
| 术语词表 | 词表页添加“源术语 → 目标译法”，翻译时自动优先参考，支持 JSON 导入导出 |

## 配置与数据

所有用户数据保存在 `%APPDATA%\MaiTranslator\`：

```
%APPDATA%\MaiTranslator\
├── config.json      应用配置
├── glossary.json    术语词表
├── history.db       翻译历史（SQLite）
├── icons\           应用图标
└── logs\            运行日志（100 MB 自动轮转）
```

### 主要参数（设置页）

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| 加速模式 | 自动 | GPU 优先，失败逐级回退（999 → 32 → 16 → 0 层）→ CPU |
| 上下文长度 | 8192 | 长文档可调大；显存不足时调小 |
| KV 缓存精度 | q8_0 | 配合 Flash Attention 显著节省显存 |
| 采样参数 | 0.7 / 20 / 0.6 / 1.05 | 官方推荐值（temperature / top_k / top_p / repeat_penalty） |
| 界面主题 | 跟随系统 | 浅色 / 深色 / 跟随系统 |

## 工作原理

```
┌──────────────┐   127.0.0.1 HTTP    ┌───────────────────┐
│ MaiTranslator │ ──────────────────> │ llama-server.exe  │
│  (PySide6 UI) │   /v1/chat/…       │  llama.cpp CUDA   │
└──────────────┘                     │  HY-MT1.5-7B GGUF │
                                     └───────────────────┘
```

- 应用启动时拉起 `llama-server.exe` 子进程（仅监听 127.0.0.1，不对外网开放），通过本地 HTTP 调用 OpenAI 兼容接口完成推理
- 使用官方提示词模板（ZH⇄XX / XX⇄ZH / 术语干预）
- 翻译前对代码块、URL、邮箱、数字等做占位符保护，翻译后精确还原，保证格式不被破坏
- 引擎异常时自动按 GPU 层数阶梯降级重启；主进程退出时通过 Job Object 确保子进程同步退出

## 项目结构

```
MaiTranslator/
├── app/
│   ├── main.py              程序入口（托盘、单实例、IPC）
│   ├── controller.py        热键 → 剪贴板捕获 → 翻译 → 悬浮窗 流程控制
│   ├── core/
│   │   ├── engine.py        llama-server 进程管理、健康检查、自动降级
│   │   ├── translator.py    提示词构建、翻译工作线程
│   │   ├── textguard.py     占位符保护/还原（代码、URL、数字等）
│   │   ├── langdetect.py    中英文检测与方向选择
│   │   ├── glossary.py      术语词表
│   │   ├── history.py       历史记录（SQLite）
│   │   ├── config.py        配置读写
│   │   ├── hotkey.py        全局热键（RegisterHotKey）
│   │   ├── clipboard.py     剪贴板读写与 Ctrl+C 模拟
│   │   ├── logger.py        日志（100 MB 轮转）
│   │   └── paths.py         路径解析
│   ├── ui/
│   │   ├── main_window.py   主窗口（翻译/历史/词表/设置）
│   │   ├── floating.py      悬浮翻译窗
│   │   ├── theme.py         浅色/深色主题系统
│   │   └── icons.py         图标生成
│   └── integrations/
│       ├── contextmenu.py   右键菜单注册表
│       └── startup.py       开机自启注册表
├── tools/                   构建、依赖下载、测试脚本
├── vendor/                  llama.cpp 二进制（setup_deps.ps1 下载）
├── models/                  GGUF 模型（setup_deps.ps1 下载）
└── MaiTranslator.spec       PyInstaller 打包配置
```

## 测试

```powershell
.venv\Scripts\python tools\test_core.py             # 核心逻辑（格式保护、词表、历史等）
.venv\Scripts\python tools\test_engine.py           # 引擎端到端（需模型就绪）
.venv\Scripts\python tools\test_theme.py            # 主题切换
.venv\Scripts\python tools\test_restore_defaults.py # 恢复默认参数
.venv\Scripts\python tools\test_gui.py              # GUI 冒烟测试
.venv\Scripts\python tools\test_hotkey_e2e.py       # 全局热键端到端（需应用已运行）
```

## 故障排除

| 现象 | 解决方法 |
| --- | --- |
| 热键无响应 | 其他程序可能占用了 `Alt + F`，查看托盘提示；可在设置页临时禁用排查冲突 |
| 提示显存不足 | 程序会自动降级重试；也可在设置中手动选择“仅 CPU”或调小上下文长度 |
| 提示未找到模型 | 在设置页指定 GGUF 模型文件路径，或重新运行 `tools\setup_deps.ps1` |
| 引擎启动失败 | 查看 `%APPDATA%\MaiTranslator\logs\maitranslator.log`；设置页可重启引擎 |
| 翻译质量/术语不生效 | 确认词表中“源术语”与原文一致；词表命中时悬浮窗会显示“词表已生效” |

## 致谢

- [Tencent HY-MT1.5-7B](https://huggingface.co/tencent/HY-MT1.5-7B-GGUF) — 翻译模型（WMT25 冠军模型升级版）
- [llama.cpp](https://github.com/ggml-org/llama.cpp) — 本地 GGUF 推理引擎
- [PySide6 / Qt](https://www.qt.io/) — 图形界面框架