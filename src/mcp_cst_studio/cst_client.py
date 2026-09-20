"""CST Studio connection manager with connected/offline modes."""

from __future__ import annotations

import logging
import os
import re
import time
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio.dialog_handler import DialogWatcher, dismiss_cst_dialogs, find_cst_dialogs

logger = logging.getLogger(__name__)

_PUBLIC_REMOTE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

# Try importing the official CST Python library
try:
    import cst.interface  # type: ignore[import-untyped]
    import cst.results  # type: ignore[import-untyped]
    CST_AVAILABLE = True
except ImportError:
    CST_AVAILABLE = False


class CSTClient:
    """Manages CST Studio Suite connection.

    In connected mode (Windows with CST), executes VBA directly.
    In offline mode (any OS), returns generated VBA scripts.
    """

    def __init__(self, config: CSTConfig | None = None) -> None:
        self._config = config or CSTConfig.from_env()
        self._de: Any = None  # cst.interface.DesignEnvironment
        self._project: Any = None  # Active project handle
        self._project_path: str | None = None
        self._owns_environment = False

    @property
    def connected(self) -> bool:
        return self._config.connected and CST_AVAILABLE

    @property
    def has_project(self) -> bool:
        return self._project is not None

    @property
    def project_path(self) -> str | None:
        return self._project_path

    @property
    def mode(self) -> str:
        if self.connected:
            return "connected"
        return "disconnected" if CST_AVAILABLE and self._config.connection_mode != "offline" else "offline"

    def connect(self) -> dict:
        """Connect to CST Design Environment.

        Create an isolated instance, or attach to an explicitly configured PID.
        Never select the first running environment or its first project.
        """
        if not CST_AVAILABLE or self._config.connection_mode == "offline":
            return {
                "status": "offline",
                "message": "CST Python library not available. Running in offline mode — "
                "VBA scripts will be generated but not executed.",
            }

        try:
            if self._de is not None:
                return {"status": "connected", "owned": self._owns_environment}
            if self._config.connection_mode == "attach":
                if self._config.pid is None:
                    raise ValueError("CST_PID is required for attach mode")
                self._de = cst.interface.DesignEnvironment.connect(self._config.pid)
            elif self._config.connection_mode == "new":
                self._de = cst.interface.DesignEnvironment(
                    # Quiet must apply during startup; setting it after connect is too late
                    # when a hidden startup dialog prevents API registration.
                    options=["-hide", "-quiet"] if self._config.hidden else ["-quiet"]
                )
                self._owns_environment = True
                self._de.set_quiet_mode(True)
            else:
                raise ValueError("CST_CONNECTION_MODE must be new, attach, or offline")
            self._config.connected = True
            return {"status": "connected", "pid": self._de.pid(),
                    "owned": self._owns_environment, "project_bound": False}
        except Exception as e:
            self._config.connected = False
            return {
                "status": "error",
                "message": f"Failed to connect to CST: {e}",
            }

    def disconnect(self) -> dict:
        """Disconnect from CST."""
        if getattr(self, "_task_job", None):
            from mcp_cst_studio.task_runner import task_status, TERMINAL
            state = task_status(self)["state"]
            if state not in TERMINAL:
                return {"status": "job_running", "message": "Owned CST retained under task supervisor"}
            if state == "terminated":
                self._de = self._project = self._project_path = None
                self._owns_environment = self._config.connected = False
                return {"status": "disconnected", "message": "Owned process was already terminated"}
        if self._de is not None:
            try:
                if self._owns_environment:
                    self._de.close()
            except Exception as exc:
                return {"status": "error", "message": str(exc)}
            self._de = None
            self._project = None
            self._project_path = None
            self._config.connected = False
            self._owns_environment = False
        return {"status": "disconnected"}

    # Maps project type codes to DesignEnvironment factory methods
    _PROJECT_FACTORIES: dict[str, str] = {
        "MWS": "new_mws",
        "EMS": "new_ems",
        "PS": "new_ps",
        "MPS": "new_mps",
        "CS": "new_cs",
        "DS": "new_ds",
        "PCB": "new_pcbs",
    }

    def checked_project_path(self, path: str) -> str:
        resolved = Path(path).resolve()
        if self._config.work_dir and not resolved.is_relative_to(Path(self._config.work_dir).resolve()):
            raise ValueError("Project must be inside CST_WORK_DIR; copy references first")
        return str(resolved)

    def new_project(self, path: str, project_type: str = "MWS") -> dict:
        """Create a new CST project.

        Starts a background dialog watcher before saving because
        ``project.save(path)`` can trigger a blocking modal dialog
        (e.g. overwrite confirmation).  The watcher auto-dismisses it.
        """
        if self._de is None and CST_AVAILABLE and self._config.connection_mode != "offline":
            connection = self.connect()
            if connection.get("status") == "error":
                return connection
        if self.connected and self._de is not None:
            try:
                path = self.checked_project_path(path)
                if Path(path).exists():
                    raise FileExistsError("New project destination already exists")
                factory_name = self._PROJECT_FACTORIES.get(project_type.upper())
                if factory_name is None:
                    raise ValueError(f"Unsupported project type: {project_type}")
                self._project = getattr(self._de, factory_name)()
                self._project.save(path)
                self._project_path = path
                return {"status": "created", "path": path, "type": project_type}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {
            "status": "offline",
            "path": path,
            "type": project_type,
            "message": "Project creation requires connected mode. "
            "Use the generated VBA scripts on a Windows machine with CST.",
        }

    def open_project(self, path: str) -> dict:
        """Open an existing CST project."""
        if self._de is None and CST_AVAILABLE and self._config.connection_mode != "offline":
            connection = self.connect()
            if connection.get("status") == "error":
                return connection
        if self.connected and self._de is not None:
            try:
                path = self.checked_project_path(path)
                if self._project is not None:
                    current = Path(self._project_path).resolve() if self._project_path else None
                    if current != Path(path).resolve():
                        raise ValueError("Close the current project before opening another")
                self._project = self._de.open_project(path)
                self._project_path = path
                return {"status": "opened", "path": path}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        self._project_path = path
        return {
            "status": "offline",
            "path": path,
            "message": "Project opened in offline reference mode.",
        }

    def save_project(self, path: str | None = None) -> dict:
        """Save the current project.

        Starts a background dialog watcher because ``project.save()``
        can trigger a blocking modal dialog (overwrite confirmation,
        file-in-use warning, etc.).  The watcher auto-dismisses it.
        """
        save_path = path or self._project_path
        if self.connected and self._project is not None:
            try:
                if save_path:
                    save_path = self.checked_project_path(save_path)
                    same_project = bool(self._project_path and Path(save_path).resolve() == Path(self._project_path).resolve())
                    self._project.save(save_path, allow_overwrite=same_project)
                else:
                    self._project.save()
                self._project_path = save_path
                return {"status": "saved", "path": save_path}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "offline", "message": "Save requires connected mode."}

    def close_project(self) -> dict:
        """Close the current project."""
        if self.connected and self._project is not None:
            try:
                self._project.close()
            except Exception:
                pass
            self._project = None
            self._project_path = None
            return {"status": "closed"}

        self._project = None
        self._project_path = None
        return {"status": "closed", "message": "Project reference cleared."}

    _history_counter: int = 0

    def execute_vba(self, vba_code: str, history_label: str | None = None) -> dict:
        """Execute once in the explicit 3D domain; never replay after partial failure."""
        if not self.connected or self._project is None:
            return {"status": "offline", "vba": vba_code,
                    "message": "VBA generated; no CST execution occurred."}
        if re.search(r"\b(?:MsgBox|InputBox)\b", vba_code, re.IGNORECASE):
            return {"status": "error", "message": "Interactive VBA prompts are disabled; use structured readback tools."}
        try:
            model = self._project.model3d
            if model is None:
                raise RuntimeError("No 3D interface; use the explicit schematic operation")
            CSTClient._history_counter += 1
            result = model.add_to_history(
                history_label or f"mcp_action_{CSTClient._history_counter}", vba_code
            )
            return {"status": "executed", "result": self._jsonable(result)}
        except Exception as exc:
            return {"status": "error", "message": str(exc), "vba": vba_code,
                    "partial_execution_possible": True}

    def read_parameters(self, name: str | None = None) -> dict:
        """Read stored expressions and evaluated values without executing a macro."""
        if not self.connected or self._project is None:
            return {"status": "offline"}
        try:
            model = self._project.model3d or self._project.schematic
            values = []
            for index in range(model.GetNumberOfParameters()):
                key = model.GetParameterName(index)
                if name is None or key == name:
                    values.append({"name": key, "expression": model.GetParameterSValue(index),
                                   "value": model.GetParameterNValue(index)})
            if name is not None and not values:
                raise ValueError(f"Parameter not found: {name}")
            return {"status": "ok", "project_path": self._project_path, "parameters": values}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def solver_status(self) -> dict:
        """A failed query is unknown, never evidence that a solver stopped."""
        if getattr(self, "_task_job", None):
            from mcp_cst_studio.task_runner import task_status
            return task_status(self)
        if not self.connected or self._project is None:
            return {"status": "offline", "running": None}
        try:
            model = self._project.model3d
            running = bool(model.is_solver_running(timeout=10))
            return {"status": "ok", "running": running,
                    "run_info": self._jsonable(model.get_solver_run_info(timeout=10)),
                    "project_path": self._project_path}
        except Exception as exc:
            return {"status": "unknown", "running": None, "message": str(exc)}

    def solver_command(self, command: str) -> dict:
        """Native asynchronous 3D controls. DS task execution has a separate contract."""
        if getattr(self, "_task_job", None):
            from mcp_cst_studio.task_runner import cancel_task, task_status, TERMINAL
            if command == "stop":
                return cancel_task(self)
            if task_status(self)["state"] not in TERMINAL:
                return {"status": "error", "message": "Schematic task active; use its status/stop control"}
            if command == "start":
                self._task_job = None
        if command == "start" and self._owns_environment:
            from mcp_cst_studio.task_runner import start_task
            state = self.solver_status()
            if state.get("status") != "ok":
                return state
            if state.get("running"):
                return {"status": "error", "message": "A solver is already running"}
            return start_task(self, "current 3D solver", domain="3d")
        if not self.connected or self._project is None:
            return {"status": "offline"}
        methods = {"start": "start_solver", "stop": "abort_solver",
                   "pause": "pause_solver", "resume": "resume_solver"}
        try:
            method = methods[command]
            state = self.solver_status()
            if state["status"] != "ok":
                return state
            if command == "start" and state["running"]:
                return {"status": "error", "message": "A solver is already running"}
            getattr(self._project.model3d, method)(timeout=30)
            return {"status": "requested", "command": command,
                    "observed": self.solver_status()}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def write_user_excitation_signal_file(self, signal_name: str, usf_code: str) -> dict:
        """Write a CST user-defined excitation ``.usf`` file next to the project.

        CST resolves a user excitation named ``signal1`` from
        ``<project-base>/Model/3D/signal1.usf`` where ``<project-base>`` is the
        saved project path without the ``.cst`` suffix.
        """
        if not self._project_path:
            return {
                "status": "error",
                "message": "A saved CST project path is required before writing a .usf file.",
            }

        try:
            project_path = Path(self._project_path)
            project_base = (
                project_path.with_suffix("")
                if project_path.suffix.lower() == ".cst"
                else project_path
            )
            usf_path = project_base / "Model" / "3D" / f"{signal_name}.usf"
            usf_path.parent.mkdir(parents=True, exist_ok=True)
            usf_path.write_text(usf_code, encoding="utf-8", newline="\n")
            return {
                "status": "written",
                "usf_path": str(usf_path),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _schematic(self) -> Any:
        """Return the active project schematic remote object."""
        if not self.connected or self._project is None:
            raise RuntimeError("Schematic access requires connected mode and an open project.")
        schematic = getattr(self._project, "schematic", None)
        if schematic is None:
            raise RuntimeError("The current CST project does not expose a schematic interface.")
        return schematic

    @staticmethod
    def _validate_remote_name(value: str, label: str) -> str:
        """Validate a public CST remote object or method name."""
        if not value or value.startswith("_") or not _PUBLIC_REMOTE_NAME_RE.match(value):
            raise RuntimeError(f"{label} must be a public CST remote name")
        return value

    @staticmethod
    def _jsonable(value: Any) -> Any:
        """Convert CST remote return values into JSON-friendly values."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple)):
            return [CSTClient._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): CSTClient._jsonable(item) for key, item in value.items()}
        return str(value)

    def schematic_create_rlc(
        self,
        *,
        name: str,
        block_type: str,
        property_name: str,
        value: str,
        unit: str,
        x: float | None = None,
        y: float | None = None,
        rotation: int | None = None,
    ) -> dict:
        """Create a Design Studio R/L/C block via the schematic Python API."""
        try:
            block = self._schematic().Block
            block.Reset()
            block.Name(name)
            block.Type(block_type)
            block.SetDoubleProperty(property_name, value)
            if x is not None and y is not None:
                block.Position(x, y)
            if rotation is not None:
                block.Rotate(rotation)
            block.Create()
            block.SetLocalUnitForProperty(property_name, unit)
            return {
                "status": "executed",
                "result": "ok",
                "interface": "schematic",
                "object": "Block",
                "name": name,
                "type": block_type,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def schematic_create_external_port(
        self,
        *,
        name: str,
        x: float | None = None,
        y: float | None = None,
        number: int | None = None,
        impedance: str | None = None,
        label: str | None = None,
    ) -> dict:
        """Create a Design Studio external port via the schematic Python API."""
        try:
            port = self._schematic().ExternalPort
            port.Reset()
            port.Name(name)
            if number is not None:
                port.Number(number)
            if x is not None and y is not None:
                port.Position(x, y)
            if impedance is not None:
                port.SetImpedance(impedance)
            if label:
                port.SetLabel(label)
            port.Create()
            return {
                "status": "executed",
                "result": "ok",
                "interface": "schematic",
                "object": "ExternalPort",
                "name": name,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def schematic_connect(
        self,
        *,
        net_name: str,
        ports: list[list[Any]],
        show_label: bool = False,
    ) -> dict:
        """Connect Design Studio block/external-port pins into one schematic net."""
        try:
            net = self._schematic().Net
            net.Reset()
            generated_name = net.AddComponentPorts("", ports, False)
            final_name = str(generated_name or net_name)
            if net_name and generated_name:
                net.Rename(generated_name, net_name)
                final_name = net_name
            if net_name:
                net.ShowNetNameLabel(net_name, show_label)
            net.Apply()
            return {
                "status": "executed",
                "result": "ok",
                "interface": "schematic",
                "object": "Net",
                "net_name": final_name,
                "ports": ports,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def schematic_create_transient_task(
        self,
        *,
        name: str = "Tran1",
        tmax: str = "250",
        samples: int = 1001,
        sampling_method: str = "Automatic",
        circuit_simulator: str = "cosimulation",
        sparameter_interpolation: str = "magnitude/phase",
        combine_results: bool = False,
        combine_block: str = "CSSCHEM1",
        update: bool = False,
    ) -> dict:
        """Create or update a Design Studio transient co-simulation task."""
        try:
            task = self._schematic().SimulationTask
            task.Reset()
            task.Name(name)
            exists = bool(task.DoesExist())

            if not exists:
                task.Reset()
                task.Type("transient")
                task.Name(name)
                task.Create()

            task.Reset()
            task.Name(name)
            task.SetProperty("tmax", str(tmax))
            task.SetProperty("circuit simulator", circuit_simulator)
            task.SetProperty("sampling method", sampling_method)
            task.SetProperty("nfdsamples", str(samples))
            task.SetProperty(
                "s-parameter interpolation scheme",
                sparameter_interpolation,
            )
            task.SetProperty("docombineresults", "True" if combine_results else "False")
            if combine_results:
                task.SetProperty("blocknameforcombineresults", combine_block)
            try:
                task.ValidateSetup()
            except Exception as exc:
                return {
                    "status": "error",
                    "message": f"SimulationTask.ValidateSetup failed: {exc}",
                    "task": name,
                }
            if update:
                task.Update()
            return {
                "status": "executed",
                "result": "ok",
                "interface": "schematic",
                "object": "SimulationTask",
                "task": name,
                "created": not exists,
                "updated": update,
                "settings": {
                    "tmax": str(tmax),
                    "samples": samples,
                    "sampling_method": sampling_method,
                    "circuit_simulator": circuit_simulator,
                    "sparameter_interpolation": sparameter_interpolation,
                    "combine_results": combine_results,
                    "combine_block": combine_block if combine_results else "",
                },
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def schematic_list(self) -> dict:
        """List available schematic blocks and nets from the active project."""
        try:
            schematic = self._schematic()
            blocks: list[dict[str, Any]] = []
            schematic.Block.StartBlockNameIteration()
            while True:
                block_name = schematic.Block.GetNextBlockName()
                if not block_name:
                    break
                schematic.Block.Reset()
                schematic.Block.Name(block_name)
                blocks.append(
                    {
                        "name": block_name,
                        "type_short": schematic.Block.GetTypeShortName(),
                        "type_name": schematic.Block.GetTypeName(),
                        "ports": schematic.Block.GetNumberOfPorts(),
                    }
                )

            nets: list[dict[str, Any]] = []
            schematic.Net.Reset()
            for index in range(schematic.Net.GetNumberOfNets()):
                net_name = schematic.Net.GetNetNameByIndex(index)
                nets.append(
                    {
                        "name": net_name,
                        "ports": schematic.Net.GetComponentPorts(net_name, -1),
                    }
                )

            return {
                "status": "ok",
                "interface": "schematic",
                "blocks": blocks,
                "nets": nets,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def schematic_list_objects(self) -> dict:
        """List public members exposed by project.schematic."""
        try:
            schematic = self._schematic()
            objects: list[dict[str, Any]] = []
            for name in sorted(n for n in dir(schematic) if not n.startswith("_")):
                try:
                    member = getattr(schematic, name)
                    methods = [m for m in dir(member) if not m.startswith("_")]
                    objects.append(
                        {
                            "name": name,
                            "type": type(member).__name__,
                            "method_count": len(methods),
                            "object_like": len(methods) > 0,
                        }
                    )
                except Exception as exc:
                    objects.append({"name": name, "error": str(exc)})
            return {
                "status": "ok",
                "interface": "schematic",
                "count": len(objects),
                "objects": objects,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def schematic_object_methods(self, object_name: str) -> dict:
        """List public methods exposed by one schematic remote object."""
        try:
            object_name = self._validate_remote_name(object_name, "object_name")
            schematic = self._schematic()
            obj = getattr(schematic, object_name)
            methods = sorted(name for name in dir(obj) if not name.startswith("_"))
            return {
                "status": "ok",
                "interface": "schematic",
                "object_name": object_name,
                "count": len(methods),
                "methods": methods,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def schematic_call(
        self,
        *,
        object_name: str,
        method_name: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        target_name: str | None = None,
    ) -> dict:
        """Call project.schematic.<object_name>.<method_name>(*args, **kwargs)."""
        try:
            object_name = self._validate_remote_name(object_name, "object_name")
            method_name = self._validate_remote_name(method_name, "method_name")
            args = args or []
            kwargs = kwargs or {}
            if not isinstance(args, list):
                raise RuntimeError("args must be a list")
            if not isinstance(kwargs, dict):
                raise RuntimeError("kwargs must be an object")
            schematic = self._schematic()
            obj = getattr(schematic, object_name)
            if object_name == "SimulationTask" and method_name == "Update":
                raise RuntimeError("Use cst_run_task so execution has durable status, limits and cancellation")
            if method_name == "Delete" and object_name in ("Block", "CircuitProbe", "SimulationTask") and not target_name:
                raise ValueError("Delete requires target_name; readback changes CST's current object selection")
            if target_name:
                if object_name not in ("Block", "CircuitProbe", "SimulationTask", "ExternalPort"):
                    raise ValueError("target_name is supported only for named schematic objects")
                obj.Reset()
                obj.Name(target_name)
                if not obj.DoesExist():
                    raise ValueError(f"Schematic target not found: {target_name}")
            method = getattr(obj, method_name)
            if not callable(method):
                raise RuntimeError(f"{object_name}.{method_name} is not callable")
            result = method(*args, **kwargs)
            return {
                "status": "executed",
                "interface": "schematic",
                "object_name": object_name,
                "method_name": method_name,
                "target_name": target_name,
                "result": self._jsonable(result),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def execute_vba_silent(self, vba_code: str) -> dict:
        """Execute only in the schematic domain, without automatic dialog acceptance."""
        if not self.connected or self._project is None:
            return {"status": "offline", "vba": vba_code,
                    "message": "VBA generated; no CST execution occurred."}
        try:
            self._schematic().execute_vba_code(vba_code)
            return {"status": "executed"}
        except Exception as exc:
            return {"status": "error", "message": str(exc), "vba": vba_code,
                    "partial_execution_possible": True}

    def is_solver_running(self) -> bool:
        """Legacy boolean API raises on unknown rather than reporting false."""
        if not self.connected or self._project is None:
            return False
        return bool(self._project.model3d.is_solver_running(timeout=10))

    def wait_for_solver(self, timeout: float = 600, poll_interval: float = 2.0) -> dict:
        """Wait for a running solver to finish.

        Returns immediately if no solver is running.
        """
        if not self.connected or self._project is None:
            return {"status": "offline"}

        deadline = time.monotonic() + timeout
        while self.is_solver_running():
            if time.monotonic() > deadline:
                return {"status": "error", "message": f"Solver still running after {timeout}s"}
            time.sleep(poll_interval)

        return {"status": "ok"}

    def run_solver(self) -> dict:
        """Run the solver via Python API (no VBA, no history entry).

        Uses ``model3d.run_solver()`` which blocks until complete.
        If a solver is already running, waits for it to finish first.
        """
        if self.connected and self._project is not None:
            try:
                # Wait for any in-progress solver before starting
                if self.is_solver_running():
                    logger.info("Solver already running — waiting for it to finish")
                    wait_result = self.wait_for_solver()
                    if wait_result.get("status") == "error":
                        return wait_result

                result = self._project.model3d.run_solver()
                return {"status": "executed", "result": str(result) if result else "ok"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "offline", "message": "Solver requires connected mode."}

    def export_result(self, tree_path: str, filepath: str) -> dict:
        """Export a result tree item to CSV via Python API (no history entry).

        Uses ``model3d.SelectTreeItem()`` + ``model3d.ASCIIExport`` Python
        methods directly — avoids VBA and history bloat.  Works regardless of
        the current CST view state.

        Validates that the output file was actually created after export.
        """
        if self.connected and self._project is not None:
            try:
                # Remove stale file if it exists
                safe_path = filepath.replace("\\", "/")
                if os.path.exists(safe_path):
                    os.remove(safe_path)

                m3d = self._project.model3d
                m3d.SelectTreeItem(tree_path)
                ae = m3d.ASCIIExport
                ae.Reset()
                ae.FileName(safe_path)
                ae.SetFileType("csv")
                ae.Execute()

                # Validate the file was actually created
                if not os.path.exists(safe_path):
                    return {
                        "status": "error",
                        "message": (
                            f"Export completed but file not found at "
                            f"'{safe_path}'. The tree item '{tree_path}' "
                            "may not exist or may be empty."
                        ),
                    }

                # Check file is non-empty
                if os.path.getsize(safe_path) == 0:
                    return {
                        "status": "error",
                        "message": (
                            f"Export produced empty file at '{safe_path}'. "
                            f"Tree item '{tree_path}' may have no data."
                        ),
                    }

                return {"status": "exported", "path": filepath}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {
            "status": "offline",
            "tree_path": tree_path,
            "message": "Result export requires connected mode.",
        }

    def get_result(self, tree_path: str, domain: str = "3d") -> dict:
        """Get a result from the CST result tree."""
        if self.connected and self._project is not None:
            try:
                if domain not in ("3d", "schematic"):
                    raise ValueError("domain must be 3d or schematic")
                # CST's interactive result reader prints a notice; stdout is the
                # MCP transport, so keep library diagnostics on stderr.
                with redirect_stdout(sys.stderr):
                    result = cst.results.ProjectFile(self._project_path, allow_interactive=True)
                module = result.get_3d() if domain == "3d" else result.get_schematic()
                item = module.get_result_item(tree_path)
                y = [complex(v) for v in item.get_ydata()]
                return {"status": "ok", "project": self._project_path, "domain": domain,
                        "tree_path": tree_path, "run_id": item.run_id,
                        "title": item.title, "xlabel": item.xlabel, "ylabel": item.ylabel,
                        "representation": "complex_cartesian", "data": {
                            "x": list(item.get_xdata()), "real": [v.real for v in y],
                            "imag": [v.imag for v in y]}}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {
            "status": "offline",
            "tree_path": tree_path,
            "message": "Result retrieval requires connected mode with a completed simulation.",
        }

    def list_results(self, domain: str = "3d") -> dict:
        if not self.connected or not self._project_path:
            return {"status": "offline"}
        try:
            with redirect_stdout(sys.stderr):
                project = cst.results.ProjectFile(self._project_path, allow_interactive=True)
            if domain not in ("3d", "schematic"):
                raise ValueError("domain must be 3d or schematic")
            module = project.get_3d() if domain == "3d" else project.get_schematic()
            return {"status": "ok", "project": self._project_path, "domain": domain,
                    "items": module.get_tree_items()}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def set_parameter(self, name: str, value: Any, description: str | None = None) -> dict:
        """Update the parameter table outside history, then rebuild and read it back."""
        if not self.connected or self._project is None:
            return {"status": "offline"}
        try:
            model = self._project.model3d
            model.StoreParameter(name, str(value))
            if description:
                model.SetParameterDescription(name, description)
            model.RebuildOnParametricChange(False, True)
            result = self.read_parameters(name)
            return {"status": "executed" if result["status"] == "ok" else "error",
                    "readback": result, "parameter": name, "value": value}
        except Exception as exc:
            return {"status": "error", "message": str(exc), "partial_execution_possible": True}

    def list_ports(self) -> dict:
        if not self.connected or self._project is None:
            return {"status": "offline"}
        try:
            model = self._project.model3d
            count = model.Solver.GetNumberOfPorts()
            if not 0 <= count <= 10000:
                raise ValueError("Invalid port iteration count")
            tree = model.get_tree_items(timeout=10)
            numbers = sorted({int(match.group(1)) for item in tree if item.startswith("Ports\\")
                              and (match := re.search(r"\\port(\d+)(?:\s|$)", item, re.IGNORECASE))})
            ports = []
            for number in numbers:
                item = {"number": number}
                try:
                    data = model.DiscretePort.GetProperties(str(number))
                    if len(data) == 8 and data[0]:
                        item.update(dict(zip(("type", "impedance", "current", "voltage",
                                             "voltage_impedance", "radius", "monitor"), data[1:])))
                    else:
                        item["properties_status"] = "not_discrete_or_unavailable"
                except Exception as exc:
                    item.update(properties_status="unavailable", detail=str(exc))
                ports.append(item)
            return {"status": "ok" if len(numbers) == count else "partial",
                    "project": self._project_path, "count": count, "ports": ports,
                    "listed_count": len(numbers), "enumeration_source": "actual project tree"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def delete_results(self) -> dict:
        """Delete solver results via ``model3d.DeleteResults()``.

        This is critical before rebuilding with new parameters — without
        deleting results first, the solver may return cached/stale data
        even after a ``Rebuild()``.

        Also dismisses any CST dialogs that may appear.
        """
        if not self.connected or self._project is None:
            return {"status": "offline", "message": "Delete results requires connected mode."}

        try:
            self._project.model3d.DeleteResults()
        except Exception as e:
            logger.warning("DeleteResults error (non-fatal): %s", e)

        # Dismiss any dialogs that may have appeared
        dismissed = self.dismiss_dialogs()
        return {"status": "ok", "method": "python_api", **dismissed}

    def set_params_rebuild_solve(
        self,
        params: dict[str, float],
        export_path: str | None = None,
        port: int = 1,
    ) -> dict:
        """Set parameters, rebuild geometry, solve, and optionally export S11.

        Uses the Python API directly (no VBA, no history entries).  The
        correct sequence to get fresh results after a parameter change is:

        1. ``StoreParameter`` — update parameter table
        2. ``DeleteResults`` — clear cached solver results
        3. ``Rebuild`` — rebuild geometry from history with new values
        4. ``run_solver`` — run a fresh simulation
        5. (optional) ``ASCIIExport`` — export S-parameter data

        Without ``DeleteResults`` before ``Rebuild``, the solver returns
        stale cached data even though the parameter values have changed.

        Returns dict with status and optional export path.
        """
        if not self.connected or self._project is None:
            return {"status": "offline", "message": "Requires connected mode."}

        m3d = self._project.model3d

        try:
            # 1. Store parameters
            for name, value in params.items():
                m3d.StoreParameter(name, str(value))

            # 2. Delete old results (critical!)
            m3d.DeleteResults()

            # 3. Dismiss any dialogs
            self.dismiss_dialogs()

            # 4. Rebuild geometry
            m3d.Rebuild()

            # 5. Dismiss any post-rebuild dialogs
            self.dismiss_dialogs()

            # 6. Run solver
            if self.is_solver_running():
                wait_result = self.wait_for_solver()
                if wait_result.get("status") == "error":
                    return wait_result
            m3d.run_solver()

            # 7. Export if requested
            if export_path:
                import os
                if os.path.exists(export_path):
                    os.remove(export_path)
                tree_path = f"1D Results\\S-Parameters\\S{port},{port}"
                m3d.SelectTreeItem(tree_path)
                ae = m3d.ASCIIExport
                ae.Reset()
                ae.FileName(export_path.replace("\\", "/"))
                ae.SetFileType("csv")
                ae.Execute()

            return {"status": "ok", "params": params, "export_path": export_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def read_project_messages(self) -> dict:
        """Read solver log and project status information.

        Scans the project results directory for log files and returns
        their contents along with current solver state.
        """
        info: dict[str, Any] = {"solver_running": False}

        if not self.connected or self._project is None:
            return {"status": "offline", "message": "Requires connected mode."}

        info["solver_running"] = self.is_solver_running()
        info["project_path"] = self._project_path

        if not self._project_path:
            return {"status": "ok", **info}

        # CST stores results in a directory alongside the .cst file
        # e.g. "Project.cst" -> "Project/Result/"
        project_base = self._project_path.replace(".cst", "")
        candidate_dirs = [
            os.path.join(project_base, "Result"),
            project_base,
        ]

        log_files: list[str] = []
        for d in candidate_dirs:
            if os.path.isdir(d):
                try:
                    for fname in os.listdir(d):
                        lower = fname.lower()
                        if "log" in lower or "solver" in lower or lower.endswith(".log"):
                            log_files.append(os.path.join(d, fname))
                except OSError:
                    continue

        if log_files:
            info["log_files"] = log_files
            try:
                newest = max(log_files, key=os.path.getmtime)
                with open(newest, "r", errors="replace") as f:
                    content = f.read()
                # Return last 5000 chars to keep response manageable
                info["latest_log"] = content[-5000:] if len(content) > 5000 else content
                info["latest_log_file"] = newest
            except OSError:
                pass

        return {"status": "ok", **info}

    # -- dialog management --

    _dialog_watcher: DialogWatcher | None = None

    def dismiss_dialogs(self) -> dict:
        """Find and dismiss any visible CST dialog windows.

        Returns details of each dialog that was dismissed (title, text,
        action taken).  Uses Win32 API on Windows; no-op on other platforms.
        """
        return {"status": "unsupported", "message": "Global dialog dismissal is disabled; inspect the owned instance error."}

    def read_dialogs(self) -> dict:
        """Read (but don't dismiss) any visible CST dialog windows."""
        dialogs = find_cst_dialogs()
        # Strip hwnd for serialisation
        for d in dialogs:
            d.pop("hwnd", None)
        if dialogs:
            return {"status": "found", "count": len(dialogs), "dialogs": dialogs}
        return {"status": "ok", "message": "No CST dialogs found."}

    def start_dialog_watcher(self) -> dict:
        """Start background thread that auto-dismisses CST dialogs."""
        return {"status": "unsupported", "message": "Automatic dialog acceptance is disabled."}

    def stop_dialog_watcher(self) -> dict:
        """Stop the background dialog watcher and return its log."""
        if CSTClient._dialog_watcher is None or not CSTClient._dialog_watcher.running:
            return {"status": "not_running"}
        log = CSTClient._dialog_watcher.get_log()
        CSTClient._dialog_watcher.stop()
        return {"status": "stopped", "dismissed_count": len(log), "log": log}

    def get_dialog_log(self) -> dict:
        """Get log of dialogs auto-dismissed by the watcher."""
        if CSTClient._dialog_watcher is None:
            return {"status": "not_running", "log": []}
        log = CSTClient._dialog_watcher.get_log()
        return {"status": "ok", "count": len(log), "log": log}

    def status(self) -> dict:
        """Get current client status."""
        return {
            "mode": self.mode,
            "owned_environment": self._owns_environment,
            "pid": self._de.pid() if self._de is not None else None,
            "cst_available": CST_AVAILABLE,
            "cst_path": self._config.cst_path,
            "cst_version": self._config.version,
            "work_dir": self._config.work_dir,
            "project_open": self.has_project,
            "project_path": self._project_path,
            "owned_environment": self._owns_environment,
            "pid": self._de.pid() if self._de is not None else None,
            "dialog_watcher": (
                CSTClient._dialog_watcher is not None
                and CSTClient._dialog_watcher.running
            ),
        }
