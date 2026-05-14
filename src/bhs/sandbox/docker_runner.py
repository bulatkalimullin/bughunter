from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    import docker
except ImportError:  # pragma: no cover
    docker = None  # type: ignore

from pydantic import BaseModel


class SandboxResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    oom: bool = False
    signal: str | None = None


def _which_bin(name: str) -> str | None:
    return shutil.which(name)


class SandboxRunner:
    """
    Ephemeral container runs with Docker/Podman limits (cgroups),
    no-new-privileges, network none, optional seccomp profile.
    """

    def __init__(
        self,
        image: str | None = None,
        seccomp_profile: str | None = None,
        use_podman: bool | None = None,
    ) -> None:
        self.image = image or os.environ.get("BHS_SANDBOX_IMAGE", "bughunter-sandbox:local")
        self.seccomp_profile = seccomp_profile or os.environ.get("BHS_SECCOMP_PROFILE", "")
        if use_podman is None:
            use_podman = os.environ.get("BHS_CONTAINER_RUNTIME", "").lower() == "podman"
        self.use_podman = bool(
            use_podman or (_which_bin("podman") is not None and _which_bin("docker") is None)
        )
        self._docker = None
        if docker and not self.use_podman:
            try:
                self._docker = docker.from_env()
            except Exception:  # pragma: no cover
                self._docker = None

    def run_command(
        self,
        command: list[str],
        workdir_host: str,
        limits: dict[str, Any],
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        if os.environ.get("BHS_SANDBOX_MODE", "").lower() == "local":
            return self._run_local(command, workdir_host, limits, env)

        mem_mb = int(limits.get("memory_mb", 4096))
        pids_max = int(limits.get("pids_max", 256))
        timeout = float(limits.get("cpu_seconds", 300.0)) + 10.0

        if self._docker is not None and not self.use_podman:
            return self._run_docker_sdk(command, workdir_host, mem_mb, pids_max, limits, env)

        return self._run_cli(command, workdir_host, mem_mb, pids_max, timeout, env, limits)

    def _run_docker_sdk(
        self,
        command: list[str],
        workdir_host: str,
        mem_mb: int,
        pids_max: int,
        limits: dict[str, Any],
        env: dict[str, str] | None,
    ) -> SandboxResult:
        sec: list[str] = []
        if self.seccomp_profile and Path(self.seccomp_profile).is_file():
            sec = [f"seccomp={self.seccomp_profile}"]

        nano_cpus: int | None = None
        raw_cpu = limits.get("cpu_cores")
        if raw_cpu is not None:
            try:
                nano_cpus = int(float(raw_cpu) * 1e9)
            except (TypeError, ValueError):
                nano_cpus = None

        t0 = time.perf_counter()
        try:
            run_kw: dict[str, Any] = dict(
                remove=True,
                network_mode="none",
                mem_limit=f"{mem_mb}m",
                pids_limit=pids_max,
                security_opt=["no-new-privileges:true", *sec],
                cap_drop=["ALL"],
                volumes={workdir_host: {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                environment=env or {},
                stdout=True,
                stderr=True,
                detach=False,
                user="nobody",
            )
            if nano_cpus and nano_cpus > 0:
                run_kw["nano_cpus"] = nano_cpus
            out = self._docker.containers.run(self.image, command, **run_kw)  # type: ignore[union-attr]
            raw = out.decode(errors="replace") if isinstance(out, (bytes, bytearray)) else str(out)
            dt = time.perf_counter() - t0
            return SandboxResult(exit_code=0, stdout=raw, stderr="", duration_sec=dt)
        except docker.errors.ContainerError as e:  # type: ignore[attr-defined]
            dt = time.perf_counter() - t0
            stderr = ""
            stdout = ""
            exit_code = 1
            if e.stderr:
                stderr = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr)
            if e.stdout:
                stdout = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else str(e.stdout)
            if hasattr(e, "exit_status"):
                exit_code = int(e.exit_status)
            oom = "OOM" in stderr or "Killed" in stderr
            return SandboxResult(
                exit_code=exit_code, stdout=stdout, stderr=stderr, duration_sec=dt, oom=oom
            )
        except Exception as e:  # pragma: no cover
            dt = time.perf_counter() - t0
            return SandboxResult(
                exit_code=127,
                stdout="",
                stderr=str(e),
                duration_sec=dt,
            )

    def _run_cli(
        self,
        command: list[str],
        workdir_host: str,
        mem_mb: int,
        pids_max: int,
        timeout: float,
        env: dict[str, str] | None,
        limits: dict[str, Any],
    ) -> SandboxResult:
        bin_name = "podman" if self.use_podman and _which_bin("podman") else "docker"
        if _which_bin(bin_name) is None:
            return SandboxResult(
                exit_code=127,
                stdout="",
                stderr=f"No container runtime ({bin_name}) available",
                duration_sec=0.0,
            )
        cmd: list[str] = [
            bin_name,
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            f"{mem_mb}m",
            "--pids-limit",
            str(pids_max),
            "--security-opt",
            "no-new-privileges:true",
            "--cap-drop",
            "ALL",
            "-v",
            f"{workdir_host}:/workspace:rw",
            "-w",
            "/workspace",
            "--user",
            "nobody",
        ]
        if limits.get("cpu_cores") is not None:
            try:
                cmd.extend(["--cpus", str(float(limits["cpu_cores"]))])
            except (TypeError, ValueError):
                pass
        if self.seccomp_profile and Path(self.seccomp_profile).is_file():
            cmd.extend(["--security-opt", f"seccomp={self.seccomp_profile}"])
        for k, v in (env or {}).items():
            cmd.extend(["-e", f"{k}={v}"])
        cmd.append(self.image)
        cmd.extend(command)

        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            dt = time.perf_counter() - t0
            oom = "OOM" in (proc.stderr or "") or "Killed" in (proc.stderr or "")
            return SandboxResult(
                exit_code=int(proc.returncode),
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                duration_sec=dt,
                oom=oom,
            )
        except subprocess.TimeoutExpired as e:
            dt = time.perf_counter() - t0
            return SandboxResult(
                exit_code=124,
                stdout=e.stdout.decode(errors="replace") if e.stdout else "",
                stderr="timeout",
                duration_sec=dt,
            )

    def _run_local(
        self,
        command: list[str],
        workdir_host: str,
        limits: dict[str, Any],
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        timeout = float(limits.get("cpu_seconds", 300.0)) + 5.0
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                command,
                cwd=workdir_host,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env={**os.environ, **(env or {})},
            )
            dt = time.perf_counter() - t0
            return SandboxResult(
                exit_code=int(proc.returncode),
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                duration_sec=dt,
            )
        except subprocess.TimeoutExpired as e:
            dt = time.perf_counter() - t0
            out = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode(errors="replace") if e.stdout else "")
            return SandboxResult(
                exit_code=124,
                stdout=out,
                stderr="timeout",
                duration_sec=dt,
            )
