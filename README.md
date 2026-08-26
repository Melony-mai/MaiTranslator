# MaiTranslator

完全离线的本地中英互译 Windows 应用。基于 **HY-MT1.5-7B** 翻译大模型（GGUF 量化）与 [llama.cpp](https://github.com/ggml-org/llama.cpp) 推理引擎，所有翻译均在本地 GPU/CPU 上完成。

> **隐私承诺**：MaiTranslator 不连接互联网、不调用云端 API、无遥测、不上传任何数据。翻译内容、术语词表、历史记录仅保存在你自己的电脑上。

---

## 功能特性

| 功能 | 说明 |
| --- | --- |
| 完全离线推理 | 仅使用本地 HY-MT1.5-7B GGUF 模型；GPU 加速优先，显存不足自动逐级降级（999 → 32 → 16 → 0 层）直至 CPU 回退 |
| 自动方向检测 | 自动识别中文/英文并选择翻译方向，也可手动指定 |
| 全局划词翻译 | 任意程序中选中文本，按 `Alt + F` 即可翻译，译文自动复制到剪贴板 |
| 悬浮翻译窗 | 展示原文/译文与耗时；`Enter` 复制译文，`Esc` 关闭 |
| 主窗口翻译 | 直接粘贴长文本或拖入 txt/md 文件翻译，支持 6 万字符以内文档 |
| 本地术语词表 | 自定义术语在翻译时优先参考（官方术语干预模板），支持 JSON 导入导出 |
| 格式保护 | Markdown、代码块、URL、邮箱、数字等在译文中原样保留（占位符保护/精确还原） |
| 历史记录 | 本地 SQLite 存储；支持关键字搜索、多选删除、清空；**单击任意记录弹出详情窗，查看完整原文/译文并可一键复制** |
| 显存智能管理 | 空闲 N 分钟后自动释放显存转为内存驻留（默认 5 分钟，可调/可关闭），托盘一键手动释放 |
| 浅色 / 深色主题 | 默认跟随系统，可手动切换，即时生效 |
| 右键菜单集成 | 任意文件右键“使用 MaiTranslator 翻译”（HKCU 注册，无需管理员权限） |
| 系统托盘 | 托盘快捷翻译剪贴板、开机自启开关、引擎状态实时显示 |
| 单实例运行 | 重复启动自动唤起已有窗口；主进程退出时通过 Job Object 确保推理子进程同步退出 |
| 日志轮转 | 单文件超过 100 MB 自动轮转覆盖 |

## 系统要求

- Windows 10 / 11（x64）
- NVIDIA GPU（推荐 8 GB 显存以完整载入默认模型）；无独显或显存不足时自动回退 CPU 运行
- 无需联网。仅在首次构建/下载依赖时需要网络，之后运行完全离线

## 快速开始（便携版）

1. 下载发布包 `MaiTranslator-1.0.0-win64-portable.zip` 并解压到任意目录
2. 双击 `MaiTranslator.exe`，等待托盘提示引擎就绪（首次加载约 10–30 秒）
3. 在任意程序中选中文字，按 **Alt + F**
4. 悬浮窗显示译文并已自动复制到剪贴板；`Enter` 再次复制，`Esc` 关闭
5. 打开主窗口（托盘图标双击）可使用翻译页、历史记录、术语词表与全部设置

> 便携包已内置 llama.cpp 推理引擎与量化模型，解压即可用，无需安装 Python。

## 从源码构建

### 1. 环境准备

- Python 3.10+（建议 3.12）
- PowerShell 5.1+（Windows 自带）
- NVIDIA 驱动（CUDA 运行时已随 llama.cpp 二进制附带，无需单独安装 CUDA Toolkit）

### 2. 获取代码与依赖（模型 + 推理引擎）

```powershell
git clone https://github.com/<your-name>/MaiTranslator.git
cd MaiTranslator
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File tools\setup_deps.ps1
```

`tools\setup_deps.ps1` 会自动下载（支持断点续传）：

- [llama.cpp](https://github.com/ggml-org/llama.cpp/releases) CUDA 12.4 预编译二进制（约 1.5 GB）→ `vendor\llamacpp\`
- [tencent/HY-MT1.5-7B-GGUF](https://huggingface.co/tencent/HY-MT1.5-7B-GGUF) Q4_K_M 量化模型（约 4.4 GB）→ `models\`

### 3. 运行

```powershell
.venv\Scripts\python app\main.py
```

### 4. 打包发布

```powershell
powershell -ExecutionPolicy Bypass -File tools\build.ps1
```

脚本依次执行：生成应用图标（`tools\gen_icons.py`）→ 清理旧产物 → PyInstaller 按 `MaiTranslator.spec` 打包 → 复制 llama.cpp 二进制与 GGUF 模型进产物目录 → 压缩便携 zip。

产物：

```
dist\
├── MaiTranslator\                          免安装目录（含 MaiTranslator.exe）
│   ├── MaiTranslator.exe
│   ├── _internal\                          Python 运行时与应用资源
│   ├── vendor\llamacpp\                    llama.cpp CUDA 引擎
│   └── models\HY-MT1.5-7B-Q4_K_M.gguf      内置模型
└── MaiTranslator-1.0.0-win64-portable.zip  一键分发压缩包（约 5 GB）
```

## 使用说明

| 操作 | 方式 |
| --- | --- |
| 划词翻译 | 任意程序选中文本 → `Alt + F` |
| 翻译剪贴板 | 托盘右键 → “翻译剪贴板内容” |
| 翻译文件 | 右键任意文本文件 → “使用 MaiTranslator 翻译”（首次需在设置页安装右键菜单），或直接拖入主窗口 |
| 主窗口翻译 | 翻译页粘贴文本 → `Ctrl + Enter` 或点击“立即翻译” |
| 复制译文 | 悬浮窗内按 `Enter`；或点击“复制译文”按钮 |
| 关闭悬浮窗 | `Esc` |
| 查看历史详情 | 历史记录页单击任意记录 → 弹出完整原文/译文详情窗（`Shift`/`Ctrl`+单击仍为多选） |
| 删除历史 | 选中记录后 `Delete` 键或点击“删除所选”；详情窗内可直接复制原文/译文片段 |
| 释放显存 | 托盘右键 → “释放显存”，或在设置页配置空闲自动释放 |
| 切换主题 | 设置 → 界面主题（跟随系统 / 浅色 / 深色） |
| 恢复默认参数 | 设置 → “恢复默认参数”（不影响模型路径与开机自启） |
| 术语词表 | 词表页添加“源术语 → 目标译法”，翻译时自动优先参考；支持 JSON 导入导出 |

## 配置与数据

所有用户数据保存在 `%APPDATA%\MaiTranslator\`：

```
%APPDATA%\MaiTranslator\
├── config.json      应用配置（设置页各项即时保存）
├── glossary.json    术语词表
├── history.db       翻译历史（SQLite）
├── logs\            运行日志 maitranslator.log（100 MB 自动轮转）
└── crash.log        致命错误堆栈（仅在异常时生成）
```

### 主要参数（设置页）

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| 加速模式 | 自动 | GPU 优先，显存不足按 GPU 层数阶梯降级（999 → 32 → 16 → 0）后回退 CPU |
| 上下文长度 | 8192 tokens | 可选 2048–32768；长文档建议调大，显存紧张时调小 |
| KV 缓存精度 | q8_0 | 可选 f16 / q8_0 / q4_0，配合 Flash Attention 显著节省显存 |
| CPU 线程数 | 8 | CPU 推理线程数 |
| 空闲释放显存 | 5 分钟 | 空闲后自动卸载出显存转为内存驻留；设为 0 表示不自动释放 |
| 采样参数 | 0.7 / 20 / 0.6 / 1.05 | temperature / top_k / top_p / repeat_penalty（官方推荐值） |
| 数字保护 | 开启 | 严格保护数字/代码/链接不被翻译改动 |
| 自动复制 | 开启 | 翻译完成后自动复制译文到剪贴板 |

## 工作原理

```
┌───────────────┐   127.0.0.1 HTTP    ┌───────────────────┐
│ MaiTranslator │ ──────────────────> │ llama-server.exe  │
│  (PySide6 UI) │    /v1/chat/…      │  llama.cpp CUDA   │
└───────────────┘                     │  HY-MT1.5-7B GGUF │
                                      └───────────────────┘
```

- 应用启动时拉起 `llama-server.exe` 子进程（仅监听 `127.0.0.1` 随机端口，不对外网开放），通过本地 HTTP 调用 OpenAI 兼容接口完成推理
- 默认**内存驻留模式**启动：不预先占用显存，翻译时按需加载，空闲后自动释放
- 使用 HY-MT 官方提示词模板（ZH⇄XX / XX⇄ZH / 术语干预）
- 翻译前对代码块、URL、邮箱、数字等做占位符保护，翻译后精确还原，保证格式不被破坏
- 引擎异常时自动按 GPU 层数阶梯降级重启；主进程退出时通过 Job Object 确保子进程同步退出

## 项目结构

```
MaiTranslator/
├── app/
│   ├── main.py              程序入口（托盘、单实例 IPC、文件关联）
│   ├── controller.py        热键 → 剪贴板捕获 → 翻译 → 悬浮窗 流程控制
│   ├── core/
│   │   ├── engine.py        llama-server 进程管理、健康检查、自动降级、显存释放
│   │   ├── translator.py    提示词构建、翻译工作线程
│   │   ├── textguard.py     占位符保护/还原（代码、URL、数字等）
│   │   ├── langdetect.py    中英文检测与方向选择
│   │   ├── glossary.py      术语词表（JSON 导入导出）
│   │   ├── history.py       历史记录（SQLite 存取、单条详情查询）
│   │   ├── config.py        配置读写（原子写入）
│   │   ├── hotkey.py        全局热键（RegisterHotKey 线程）
│   │   ├── clipboard.py     剪贴板读写与 Ctrl+C 模拟（SendInput）
│   │   ├── logger.py        日志（100 MB 轮转）
│   │   └── paths.py         路径解析（开发/打包环境自适应）
│   ├── ui/
│   │   ├── main_window.py   主窗口（翻译/历史[含详情弹窗]/词表/设置）
│   │   ├── floating.py      悬浮翻译窗
│   │   ├── theme.py         浅色/深色主题系统（QSS + QPalette）
│   │   └── icons.py         应用图标加载
│   └── integrations/
│       ├── contextmenu.py   右键菜单注册表（HKCU）
│       └── startup.py       开机自启注册表（HKCU）
├── tools/                   构建、依赖下载、截图与测试脚本
├── vendor/                  llama.cpp 二进制（setup_deps.ps1 下载，不入库）
├── models/                  GGUF 模型（setup_deps.ps1 下载，不入库）
├── icon.ico / icon.png      应用图标源文件
├── MaiTranslator.spec       PyInstaller 打包配置
└── requirements.txt         Python 依赖（PySide6、PyInstaller）
```

## 测试

```powershell
.venv\Scripts\python tools\test_core.py               # 核心逻辑（格式保护、方向、词表、历史）
.venv\Scripts\python tools\test_clipboard.py          # 剪贴板读写
.venv\Scripts\python tools\test_history_selection.py  # 历史列表选择行为与详情弹窗
.venv\Scripts\python tools\test_theme.py              # 主题切换
.venv\Scripts\python tools\test_restore_defaults.py   # 恢复默认参数
.venv\Scripts\python tools\test_engine.py             # 引擎端到端（需模型就绪）
.venv\Scripts\python tools\test_vram_release.py       # 显存自动释放
.venv\Scripts\python tools\test_gui.py                # GUI 冒烟测试（会真实拉起引擎）
.venv\Scripts\python tools\test_hotkey_e2e.py         # 全局热键端到端（需应用已运行）
```

## 故障排除

| 现象 | 解决方法 |
| --- | --- |
| 热键无响应 | `Alt + F` 可能被其他程序占用（启动时托盘会有提示）；关闭占用程序后重启应用 |
| 提示显存不足 | 程序会自动降级重试；也可在设置中选择“仅 CPU”、调小上下文长度或降低 KV 缓存精度 |
| 提示未找到模型 | 在设置页指定 GGUF 模型路径，或重新运行 `tools\setup_deps.ps1` |
| 引擎启动失败 | 查看 `%APPDATA%\MaiTranslator\logs\maitranslator.log` 与设置页状态；可在设置页重启引擎 |
| 启动闪退 | 查看 `%APPDATA%\MaiTranslator\crash.log` 中的错误堆栈 |
| 翻译质量/术语不生效 | 确认词表中“源术语”与原文一致；命中时悬浮窗会显示“词表已生效：…” |
| 误删/误清空历史 | 历史记录删除与清空均有确认对话框；数据不可恢复，请谨慎操作 |

## License

本项目基于 [MIT License](LICENSE) 开源。第三方组件遵循其各自许可：

- [HY-MT1.5-7B](https://huggingface.co/tencent/HY-MT1.5-7B-GGUF) 模型许可见其模型主页
- [llama.cpp](https://github.com/ggml-org/llama.cpp) — MIT License
- [PySide6 / Qt](https://www.qt.io/) — LGPLv3（本工具以动态链接方式使用）

## 致谢

- [Tencent HY-MT1.5-7B](https://huggingface.co/tencent/HY-MT1.5-7B) — 翻译模型
- [llama.cpp](https://github.com/ggml-org/llama.cpp) — 本地 GGUF 推理引擎
- [PySide6 / Qt](https://www.qt.io/) — 图形界面框架
