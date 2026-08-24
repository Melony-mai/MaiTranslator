import ctypes
import json
import logging
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from . import config
from .paths import find_model, server_exe

log = logging.getLogger(__name__)

_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JobObjectExtendedLimitInformation = None


def _make_kill_on_close_job():
    global _JobObjectExtendedLimitInformation
    kernel32 = ctypes.windll.kernel32

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.POINTER(ctypes.c_uint64)),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job = kernel32.CreateJobObjectW(None, None)
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
        job, 9, ctypes.byref(info), ctypes.sizeof(info)
    ):
        return None
    return job


def kill_stale_servers(model_path: str) -> int:
    killed = 0
    try:
        import os

        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | "
             "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()
        if not out:
            return 0
        items = json.loads(out)
        if isinstance(items, dict):
            items = [items]
        needle = Path(model_path).name.lower()
        for it in items or []:
            cmd = (it.get("CommandLine") or "").lower()
            pid = int(it.get("ProcessId") or 0)
            if needle in cmd and "--port" in cmd and pid != os.getpid():
                try:
                    os.kill(pid, 9)
                    killed += 1
                except (OSError, ValueError):
                    pass
    except Exception as e:
        log.debug("清理残留进程失败: %s", e)
    return killed

FAIL_MARKERS = [
    "failed to initialize",
    "cuda error",
    "out of memory",
    "ggml_backend_alloc",
    "error loading model",
    "no cuda driver",
    "wddm",
    "unknown argument",
    "invalid argument",
    "error: failed to load model",
]
VRAM_MARKERS = ["out of memory", "ggml_backend_alloc", "cuda malloc", "not enough memory"]
CUDA_FAIL_MARKERS = [
    "failed to initialize cuda",
    "no cuda driver",
    "cuda error: no kernel image",
    "gpu not found",
    "no devices",
]


def pick_port() -> int:
    preferred = int(config.get("port") or 0)
    if 0 < preferred < 65536 and not _port_busy(preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


class LlamaServer(QObject):
    STATE_STOPPED = "stopped"
    STATE_LOADING = "loading"
    STATE_READY = "ready"
    STATE_ERROR = "error"

    stateChanged = Signal(str, str)
    request_restart = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proc: subprocess.Popen | None = None
        self._state = self.STATE_STOPPED
        self._error_msg = ""
        self._port = pick_port()
        self._ngl_attempts: list[int] = []
        self._attempt = 0
        self._start_time = 0.0
        self._stopping = False
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(600)
        self._health_timer.timeout.connect(self._check_health)
        self._reader_thread = None
        self._gpu_active = False
        self._job = None

    @property
    def state(self) -> str:
        return self._state

    @property
    def gpu_active(self) -> bool:
        return self._gpu_active

    @property
    def port(self) -> int:
        return self._port

    def _set_state(self, state: str, message: str = "") -> None:
        self._state = state
        self._error_msg = message
        self.stateChanged.emit(state, message)

    def start(self) -> None:
        if self._proc is not None:
            log.warning("引擎已在运行，忽略重复启动")
            return
        exe = server_exe()
        if exe is None:
            self._set_state(
                self.STATE_ERROR,
                "未找到 llama-server.exe，请确认 vendor\\llamacpp 目录完整。",
            )
            return
        model_path = find_model(config.get("model_path", ""))
        if model_path is None:
            self._set_state(
                self.STATE_ERROR,
                "未找到翻译模型 HY-MT1.5-7B GGUF，请在设置中选择模型文件。",
            )
            return

        gpu_mode = config.get("gpu_mode", "auto")
        if gpu_mode == "cpu":
            self._ngl_attempts = [0]
        elif gpu_mode == "gpu":
            self._ngl_attempts = [int(config.get("ngl", 999))]
        else:
            self._ngl_attempts = [int(config.get("ngl", 999)), 32, 16, 0]

        self._model_path = str(model_path)
        self._exe = exe
        self._port = pick_port()
        self._attempt = 0
        self._stopping = False
        self._safe_mode = False
        stale = kill_stale_servers(self._model_path)
        if stale:
            log.info("已清理 %d 个上次残留的 llama-server 进程", stale)
        log.info("启动推理引擎: %s 模型: %s 端口: %d", exe, model_path, self._port)
        self._launch()

    def _build_args(self, ngl: int) -> list[str]:
        ctx = int(config.get("context", 8192))
        threads = int(config.get("threads", 8))
        kv = config.get("kv_cache", "q8_0")
        args = [
            str(self._exe),
            "-m",
            self._model_path,
            "--host",
            "127.0.0.1",
            "--port",
            str(self._port),
            "-c",
            str(ctx),
            "-t",
            str(threads),
            "--parallel",
            "1",
            "--jinja",
            "--no-warmup",
            "--no-webui",
        ]
        if ngl > 0:
            args += ["-ngl", str(ngl)]
        if self._safe_mode:
            return args
        if config.get("flash_attn", True):
            args += ["--flash-attn", "on"]
            if kv and kv != "f16" and ngl > 0:
                args += ["--cache-type-k", kv, "--cache-type-v", kv]
        return args

    def _launch(self) -> None:
        ngl = self._ngl_attempts[self._attempt]
        self._gpu_active = ngl > 0
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self._proc = subprocess.Popen(
                self._build_args(ngl),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self._exe.parent),
                creationflags=creationflags,
            )
        except OSError as e:
            self._set_state(self.STATE_ERROR, f"无法启动 llama-server: {e}")
            return
        try:
            job = _make_kill_on_close_job()
            if job:
                ctypes.windll.kernel32.AssignProcessToJobObject(
                    job, int(self._proc._handle)
                )
                self._job = job
        except Exception as e:
            log.debug("Job Object 绑定失败（不影响运行）: %s", e)
        self._start_time = time.monotonic()
        mode_name = "GPU" if ngl > 0 else "CPU"
        self._set_state(self.STATE_LOADING, f"正在加载模型（{mode_name} 模式）…")
        if self._reader_thread is None or not self._reader_thread.is_alive():
            self._reader_thread = None
        self._start_reader()
        self._health_timer.start()

    def _start_reader(self) -> None:
        import threading

        proc = self._proc

        def reader():
            fatal = ""
            try:
                for line in proc.stdout or []:
                    line = line.rstrip()
                    if line:
                        log.debug("[llama-server] %s", line)
                        low = line.lower()
                        for marker in CUDA_FAIL_MARKERS + VRAM_MARKERS + FAIL_MARKERS:
                            if marker in low:
                                fatal = marker
                                break
                        if fatal:
                            break
            except Exception as e:
                log.debug("日志读取线程结束: %s", e)
            self._fatal_marker = fatal

        self._fatal_marker = ""
        t = threading.Thread(target=reader, daemon=True)
        self._reader_thread = t
        t.start()

    def _check_health(self) -> None:
        proc = self._proc
        if proc is None:
            self._health_timer.stop()
            return
        if proc.poll() is not None:
            self._health_timer.stop()
            self._on_process_exited()
            return
        elapsed = time.monotonic() - self._start_time
        try:
            url = f"http://127.0.0.1:{self._port}/health"
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
            if data.get("status") == "ok":
                self._health_timer.stop()
                mode = "GPU" if self._gpu_active else "CPU"
                log.info("引擎就绪 (%s)，耗时 %.1f 秒", mode, elapsed)
                self._set_state(self.STATE_READY, f"就绪 · {mode} 加速")
                return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        except Exception as e:
            log.debug("健康检查异常: %s", e)
        if elapsed > 240:
            self._health_timer.stop()
            self._retry_or_fail("模型加载超时")

    def _on_process_exited(self) -> None:
        if self._stopping:
            self._set_state(self.STATE_STOPPED)
            return
        marker = getattr(self, "_fatal_marker", "")
        code = self._proc.returncode if self._proc else -1
        log.warning("llama-server 提前退出 (code=%s, marker=%r)", code, marker)
        low = (marker or "").lower()
        if any(m in low for m in ("unknown argument", "invalid argument")):
            self._safe_mode = True
            config.set_key("flash_attn", False)
            log.warning("检测到不兼容启动参数，已降级为基础参数重试")
            self._retry_or_fail("启动参数不兼容，已调整后重试")
            return
        self._retry_or_fail(f"推理进程异常退出（代码 {code}）")

    def _retry_or_fail(self, reason: str) -> None:
        self._kill_proc()
        self._attempt += 1
        if self._attempt < len(self._ngl_attempts):
            next_ngl = self._ngl_attempts[self._attempt]
            mode = "GPU" if next_ngl > 0 else "CPU"
            log.warning("%s，切换到下一档（%s, ngl=%d）重试", reason, mode, next_ngl)
            self._launch()
        else:
            self._set_state(
                self.STATE_ERROR,
                f"{reason}。已尝试所有 GPU/CPU 兜底方案，请查看日志获取详情。",
            )

    def stop(self) -> None:
        self._stopping = True
        self._health_timer.stop()
        self._kill_proc()
        self._set_state(self.STATE_STOPPED)

    def restart(self) -> None:
        self.stop()
        self._stopping = False
        self.start()

    def _kill_proc(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        except Exception as e:
            log.warning("停止进程时出错: %s", e)
        finally:
            job, self._job = self._job, None
            if job:
                ctypes.windll.kernel32.CloseHandle(job)

    def chat(self, prompt: str, max_tokens: int | None = None, timeout: float = 600.0) -> str:
        if self._state != self.STATE_READY:
            raise RuntimeError("推理引擎未就绪")
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(config.get("temperature", 0.7)),
            "top_k": int(config.get("top_k", 20)),
            "top_p": float(config.get("top_p", 0.6)),
            "repeat_penalty": float(config.get("repeat_penalty", 1.05)),
            "max_tokens": max_tokens or int(config.get("max_tokens", 4096)),
            "stream": False,
        }
        url = f"http://127.0.0.1:{self._port}/v1/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, ConnectionError) or "connection" in str(reason).lower() or "refused" in str(reason).lower():
                log.error("与推理引擎的本地连接中断，正在自动重启引擎")
                self.request_restart.emit()
                raise RuntimeError("本地推理连接中断，正在自动重启引擎，请稍后重试。") from e
            raise RuntimeError(f"请求推理引擎失败: {e}") from e
        except socket.timeout as e:
            raise RuntimeError("推理超时，文本可能过长，请分段翻译。") from e
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        log.info(
            "推理完成: %.2fs, tokens(prompt/completion)=%s/%s",
            time.monotonic() - started,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )
        return content

    def shutdown(self) -> None:
        self.stop()
