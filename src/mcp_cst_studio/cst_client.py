"""CST Studio connection manager with connected/offline modes."""

from __future__ import annotations

import logging
import os
import re
import time
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
        return "connected" if self.connected else "offline"

    def connect(self) -> dict:
        """Connect to CST Design Environment.

        First tries to connect to an already-running instance. If none
        is running, launches a new one.
        """
        if not CST_AVAILABLE:
            return {
                "status": "offline",
                "message": "CST Python library not available. Running in offline mode — "
                "VBA scripts will be generated but not executed.",
            }

        try:
            # Try connecting to an already-running CST instance first
            running = cst.interface.running_design_environments()
            if running:
                self._de = cst.interface.DesignEnvironment.connect(running[0])
                self._config.connected = True
                # Pick up any already-open project
                open_projects = self._de.get_open_projects()
                if open_projects:
                    self._project = open_projects[0]
                    fname = self._project.filename
                    self._project_path = str(fname() if callable(fname) else fname)
                return {
                    "status": "connected",
                    "message": f"Connected to running CST instance (PID {running[0]})",
                    "open_projects": len(open_projects) if open_projects else 0,
                }

            # No running instance — launch a new one
            self._de = cst.interface.DesignEnvironment()
            self._config.connected = True
            return {"status": "connected", "message": "Launched new CST Design Environment"}
        except Exception as e:
            self._config.connected = False
            return {
                "status": "offline",
                "message": f"Failed to connect to CST: {e}. Running in offline mode.",
            }

    def disconnect(self) -> dict:
        """Disconnect from CST."""
        if self._de is not None:
            try:
                self._de.close()
            except Exception:
                pass
            self._de = None
            self._project = None
            self._project_path = None
            self._config.connected = False
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

    def new_project(self, path: str, project_type: str = "MWS") -> dict:
        """Create a new CST project.

        Starts a background dialog watcher before saving because
        ``project.save(path)`` can trigger a blocking modal dialog
        (e.g. overwrite confirmation).  The watcher auto-dismisses it.
        """
        if self.connected and self._de is not None:
            try:
                factory_name = self._PROJECT_FACTORIES.get(
                    project_type.upper(), "new_mws"
                )
                factory = getattr(self._de, factory_name, self._de.new_mws)
                self._project = factory()
                # Start watcher to handle potential save dialog
                self.start_dialog_watcher()
                try:
                    self._project.save(path)
                finally:
                    self.stop_dialog_watcher()
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
        if self.connected and self._de is not None:
            try:
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
                # Start watcher to handle potential save dialog
                self.start_dialog_watcher()
                try:
                    if save_path:
                        self._project.save(save_path)
                    else:
                        self._project.save()
                finally:
                    self.stop_dialog_watcher()
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
        """Execute VBA code in CST.

        In connected mode: executes via ``model3d.add_to_history()`` which
        adds the VBA macro to the project history and runs it immediately.
        A background :class:`DialogWatcher` runs during execution to
        auto-dismiss any CST modal dialogs (error, property, frequency-range)
        that would otherwise block the COM call indefinitely.
        Falls back to the schematic interface for Design Studio projects.

        In offline mode: returns the VBA script for manual execution.
        """
        if self.connected and self._project is not None:
            try:
                CSTClient._history_counter += 1
                label = history_label or f"mcp_action_{CSTClient._history_counter}"
                watcher = DialogWatcher(poll_interval=0.5)
                watcher.start()
                try:
                    result = self._project.model3d.add_to_history(label, vba_code)
                finally:
                    watcher.stop()
                response: dict = {
                    "status": "executed",
                    "result": str(result) if result else "ok",
                }
                log = watcher.get_log()
                if log:
                    response["dialogs_dismissed"] = len(log)
                    response["dialog_log"] = log
                return response
            except AttributeError:
                # DS/CS projects may only have the model3d interface;
                # fall back to the schematic interface
                try:
                    result = self._project.schematic.execute_vba_code(vba_code)
                    return {
                        "status": "executed",
                        "result": str(result) if result else "ok",
                    }
                except Exception as e:
                    return {"status": "error", "message": str(e), "vba": vba_code}
            except Exception as e:
                return {"status": "error", "message": str(e), "vba": vba_code}

        return {
            "status": "offline",
            "vba": vba_code,
            "message": "VBA script generated. Execute in CST Studio Suite on Windows.",
        }

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
            method = getattr(obj, method_name)
            if not callable(method):
                raise RuntimeError(f"{object_name}.{method_name} is not callable")
            result = method(*args, **kwargs)
            return {
                "status": "executed",
                "interface": "schematic",
                "object_name": object_name,
                "method_name": method_name,
                "result": self._jsonable(result),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def execute_vba_silent(self, vba_code: str) -> dict:
        """Execute VBA without adding to project history.

        Uses ``schematic.execute_vba_code()`` which runs the macro silently.
        The code must be wrapped in ``Sub Main() ... End Sub``.
        Ideal for optimization loops where dozens of iterations would
        otherwise bloat the history list.

        A background :class:`DialogWatcher` runs during execution to
        auto-dismiss any CST modal dialogs that would block the COM call.

        In offline mode: returns the VBA script for manual execution.
        """
        if self.connected and self._project is not None:
            try:
                watcher = DialogWatcher(poll_interval=0.5)
                watcher.start()
                try:
                    self._project.schematic.execute_vba_code(vba_code)
                finally:
                    watcher.stop()
                response: dict = {"status": "executed"}
                log = watcher.get_log()
                if log:
                    response["dialogs_dismissed"] = len(log)
                    response["dialog_log"] = log
                return response
            except Exception as e:
                return {"status": "error", "message": str(e), "vba": vba_code}

        return {
            "status": "offline",
            "vba": vba_code,
            "message": "VBA script generated (silent). Execute in CST Studio Suite.",
        }

    def is_solver_running(self) -> bool:
        """Check if a solver is currently running."""
        if self.connected and self._project is not None:
            try:
                return bool(self._project.model3d.is_solver_running())
            except Exception:
                return False
        return False

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

    def get_result(self, tree_path: str) -> dict:
        """Get a result from the CST result tree."""
        if self.connected and self._project is not None:
            try:
                result = cst.results.ProjectFile(self._project_path)
                data = result.get_3d().get_tree_item(tree_path)
                return {"status": "ok", "data": str(data)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {
            "status": "offline",
            "tree_path": tree_path,
            "message": "Result retrieval requires connected mode with a completed simulation.",
        }

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
        dismissed = dismiss_cst_dialogs()
        if dismissed:
            return {"status": "dismissed", "count": len(dismissed), "dialogs": dismissed}
        return {"status": "ok", "message": "No CST dialogs found."}

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
        if CSTClient._dialog_watcher is not None and CSTClient._dialog_watcher.running:
            return {"status": "already_running"}
        CSTClient._dialog_watcher = DialogWatcher(poll_interval=0.5)
        CSTClient._dialog_watcher.start()
        return {"status": "started"}

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
            "cst_available": CST_AVAILABLE,
            "cst_path": self._config.cst_path,
            "cst_version": self._config.version,
            "work_dir": self._config.work_dir,
            "project_open": self.has_project,
            "project_path": self._project_path,
            "dialog_watcher": (
                CSTClient._dialog_watcher is not None
                and CSTClient._dialog_watcher.running
            ),
        }
