"""One bounded schematic task in an explicitly owned CST environment.

The executor owns no CST environment. The supervisor can stop only the exact
environment delegated by the MCP client (PID + process creation time).
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import time
import uuid

TERMINAL = {"succeeded", "failed", "terminated"}


def write(path: Path, value: dict):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def start_task(client, task: str, max_seconds: int = 3600, max_rss_gb: float = 24, domain: str = "schematic") -> dict:
    import psutil
    if not client._owns_environment or not client.has_project:
        raise ValueError("Task execution requires an owned CST instance and an open working copy")
    if getattr(client, "_task_job", None) and task_status(client)["state"] not in TERMINAL:
        raise ValueError("A schematic task is already active")
    if not 10 <= max_seconds <= 3600 or not 1 <= max_rss_gb <= 24:
        raise ValueError("Current limits: 10–3600 seconds, 1–24 GiB RSS")
    if domain not in ("3d", "schematic"):
        raise ValueError("Unknown execution domain")
    pid = client._de.pid()
    process = psutil.Process(pid)
    job = Path(client.checked_project_path(client.project_path)).parent / "jobs" / uuid.uuid4().hex
    job.mkdir(parents=True)
    saved = client.save_project()
    if saved.get("status") != "saved":
        return saved
    record = {"job_id": job.name, "domain": domain, "task": task,
              "project": client.project_path, "owned_pid": pid, "process_created": process.create_time(),
              "controller_pid": os.getpid(), "max_seconds": max_seconds, "max_rss_gb": max_rss_gb,
              "created_at": time.time(), "state": "queued", "human_acceptance": "pending",
              "numerical_acceptance": "pending"}
    write(job / "request.json", record)
    write(job / "status.json", record)
    shutil.copy2(__file__, job / "runner.py")
    # Freeze the executor for this attempt and preserve its import environment.
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in sys.path if p)}
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (job / "supervisor.log").open("wb") as log:
        supervisor = subprocess.Popen([sys.executable, str(job / "runner.py"), "watch", str(job)],
                                      stdout=log, stderr=subprocess.STDOUT, creationflags=flags, env=env)
    client._task_job = job
    client._task_supervisor = supervisor
    return {"status": "requested", **record, "receipt": str(job / "status.json")}


def task_status(client) -> dict:
    value = json.loads((client._task_job / "status.json").read_text(encoding="utf-8"))
    return {"status": "unknown" if value["state"] == "unknown" else "ok", **value,
            "running": None if value["state"] == "unknown" else value["state"] not in TERMINAL}


def cancel_task(client) -> dict:
    return request_cancellation(client._task_job)


def request_cancellation(job: Path) -> dict:
    """Shared MCP/viewer stop path; no CST connection or provider is required."""
    state = json.loads((job / "status.json").read_text(encoding="utf-8"))
    if state["state"] in TERMINAL:
        return state
    if state["state"] == "unknown":
        return {"status": "unknown", **state,
                "message": "Process ownership/state needs investigation; no unverified process was stopped"}
    try:
        with (job / "cancel.json").open("x", encoding="utf-8") as stream:
            json.dump({"requested_at": time.time(), "reason": "user_stop"}, stream)
    except FileExistsError:
        pass
    return {"status": "requested", "command": "stop", "job_id": state["job_id"],
            "message": "Stop requested; inspect status for confirmed process termination or task completion"}


def same_process(request: dict, process) -> bool:
    return process.pid == request["owned_pid"] and abs(process.create_time() - request["process_created"]) < .01


def terminate_owned(request: dict) -> dict:
    """Terminate only a still-identical delegated root and its actual descendants."""
    import psutil
    owner = psutil.Process(request["owned_pid"])
    if not same_process(request, owner):
        raise RuntimeError("PID was reused; refusing termination")
    killed = []
    for process in reversed([owner, *owner.children(recursive=True)]):
        try:
            process.kill(); killed.append(process)
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(killed, timeout=5)
    return {"state": "terminated" if not alive else "unknown",
            "termination_mode": "owned_process_tree", "remaining_pids": [p.pid for p in alive],
            "terminated_pids": [p.pid for p in killed]}


def execute(job: Path, abort: bool = False):
    import cst.interface as ci
    import psutil
    request = json.loads((job / "request.json").read_text(encoding="utf-8"))
    output = job / ("abort.json" if abort else "execution.json")
    value = {"started_at": time.time(), "state": "executing"}
    write(output, value)
    try:
        if not same_process(request, psutil.Process(request["owned_pid"])):
            raise RuntimeError("CST process identity changed")
        de = ci.DesignEnvironment.connect(request["owned_pid"])
        project = de.get_open_project(request["project"])
        if Path(project.filename()).resolve() != Path(request["project"]).resolve():
            raise RuntimeError("Project identity mismatch")
        if abort:
            project.model3d.abort_solver(timeout=10)
            value["state"] = "abort_requested"
        else:
            value["messages_before"] = project.get_messages() or []
            if request["domain"] == "3d":
                result = project.model3d.run_solver()
            else:
                task = project.schematic.SimulationTask
                task.Reset(); task.Name(request["task"])
                if not task.DoesExist():
                    raise ValueError("Named task does not exist")
                task.ValidateSetup()
                result = task.Update()
            value["messages"] = project.get_messages() or []
            old = value["messages_before"]
            new = value["messages"][len(old):] if value["messages"][:len(old)] == old else value["messages"]
            value["new_messages"] = new
            if result is False or any(str(m.get("type", "")).lower() == "error" for m in new):
                raise RuntimeError("CST reported a task error; inspect messages and DS logs")
            project.save(request["project"], include_results=True, allow_overwrite=True)
            value["state"] = "succeeded"
    except Exception as exc:
        value.update(state="failed", error=str(exc))
    value["ended_at"] = time.time()
    write(output, value)
    # Native SDK finalizers can wait after the remote DE has gone. This short-lived
    # borrowed connection must never close the DE or block delivery of its receipt.
    os._exit(0 if value["state"] in ("succeeded", "abort_requested") else 1)


def supervise(job: Path):
    import psutil
    request = json.loads((job / "request.json").read_text(encoding="utf-8"))
    record = dict(request, state="executing", started_at=time.time(), peak_rss_bytes=0)
    write(job / "status.json", record)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (job / "executor.log").open("wb") as log:
        worker = subprocess.Popen([sys.executable, str(job / "runner.py"), "execute", str(job)],
                                  stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
    aborter = None
    cancellation = None
    try:
        while worker.poll() is None:
            owner = psutil.Process(request["owned_pid"])
            if not same_process(request, owner):
                raise RuntimeError("CST process identity changed; refusing to terminate another process")
            processes = [owner, *owner.children(recursive=True)]
            rss = 0
            for process in processes:
                try:
                    rss += process.memory_info().rss
                except psutil.NoSuchProcess:
                    pass
            record["peak_rss_bytes"] = max(record["peak_rss_bytes"], rss)
            reason = "user_stop" if (job / "cancel.json").exists() else None
            if time.time() - record["started_at"] > request["max_seconds"]:
                reason = "time_limit"
            if rss > request["max_rss_gb"] * 1024 ** 3:
                reason = "memory_limit"
            if reason and cancellation is None:
                cancellation = time.time()
                record.update(state="stopping", stop_reason=reason, stop_requested_at=cancellation)
                with (job / "abort.log").open("wb") as log:
                    aborter = subprocess.Popen([sys.executable, str(job / "runner.py"), "abort", str(job)],
                                               stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
            if cancellation is not None and time.time() - cancellation >= 15:
                # Preserve request, saved project and partial outputs. Never kill services,
                # another CST environment, or children not belonging to the owned root.
                record.update(terminate_owned(request))
                worker.kill(); worker.wait(timeout=5)
                break
            record["updated_at"] = time.time()
            write(job / "status.json", record)
            time.sleep(1)
        else:
            execution = json.loads((job / "execution.json").read_text(encoding="utf-8"))
            record.update(state=execution["state"], execution=execution)
            if cancellation is not None:
                record["stop_outcome"] = "execution_ended_after_request; inspect task result"
    except Exception as exc:
        record.update(state="unknown", error=str(exc))
        # A broken supervisor must not abandon an unbounded solver. If identity is
        # still provable, stop the owned tree; a reused PID is never touched.
        try:
            record.update(terminate_owned(request), stop_reason="supervisor_error")
            if worker.poll() is None:
                worker.kill(); worker.wait(timeout=5)
        except Exception as recovery_error:
            record["recovery_error"] = str(recovery_error)
    finally:
        if aborter is not None and aborter.poll() is None:
            aborter.kill(); aborter.wait(timeout=5)
        record["ended_at"] = time.time()
        write(job / "status.json", record)


if __name__ == "__main__":
    mode, directory = sys.argv[1:]
    if mode == "watch":
        supervise(Path(directory))
    else:
        execute(Path(directory), abort=mode == "abort")
