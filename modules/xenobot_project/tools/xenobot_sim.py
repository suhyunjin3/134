"""
Xenobot Kinematics Simulator
============================

Description:
    Simulates the kinematic behavior of xenobot-inspired multicellular constructs.
    Each cell is modeled as a force-generating unit with motor_x and motor_y
    components (in micrometers/step). The simulator computes net displacement via
    NumPy vector addition across all cells, integrates trajectories over a
    configurable number of steps, and produces a trajectory plot encoded as base64
    PNG — ready for display in a Gemini/MCP tool response.

Input:
    cells (list[dict]): Each dict must contain:
        - "motor_x" (float): Force contribution along the x-axis (µm/step).
        - "motor_y" (float): Force contribution along the y-axis (µm/step).
        Optional per-cell fields:
        - "label" (str): Display name for legend (default: "cell_N").
    steps (int, optional): Number of simulation steps (default 50).
    noise (float, optional): Gaussian noise std-dev added per step (default 0.05).

Output:
    dict with a "content" list containing:
        [0] {"type": "text",  "text": "<summary string>"}
        [1] {"type": "image", "data": "<base64-encoded PNG>",
             "media_type": "image/png"}

Tests:
    >>> sim = XenobotSim()
    >>> sim.initiate()
    >>> result = sim.run([{"motor_x": 1.0, "motor_y": 0.0}])
    >>> assert result["content"][0]["type"] == "text"
    >>> assert result["content"][1]["type"] == "image"

    >>> # Two antagonistic cells → near-zero net displacement
    >>> result2 = sim.run([{"motor_x": 1.0, "motor_y": 0.0},
    ...                    {"motor_x": -1.0, "motor_y": 0.0}], steps=10, noise=0.0)
    >>> import json; summary = result2["content"][0]["text"]
    >>> assert "net displacement" in summary.lower()
"""

from __future__ import annotations

import base64
import io
from typing import Any

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — safe for server use
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np


class XenobotSim:
    """Xenobot kinematics simulator compatible with the BioE234 MCP Function Object Pattern."""

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def initiate(self) -> None:
        """Set up simulator state and validate NumPy / Matplotlib availability."""
        self._rng = np.random.default_rng(seed=42)
        self._ready = True

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def run(
        self,
        cells: list[dict[str, Any]],
        steps: int = 50,
        noise: float = 0.05,
    ) -> dict[str, Any]:
        """
        Simulate xenobot kinematics for the supplied cell configurations.

        Parameters
        ----------
        cells : list[dict]
            Each dict must have ``motor_x`` (float) and ``motor_y`` (float).
            Optional ``label`` (str) sets a per-cell legend entry.
        steps : int
            Number of simulation steps (default 50).
        noise : float
            Gaussian noise standard deviation added to each cell at every step
            (default 0.05 µm/step).

        Returns
        -------
        dict
            ``{"content": [text_block, image_block]}``
        """
        if not getattr(self, "_ready", False):
            self.initiate()

        if not cells:
            return {
                "content": [
                    {"type": "text", "text": "Error: 'cells' list must not be empty."}
                ]
            }

        n = len(cells)
        # ── motor vectors ──────────────────────────────────────────────
        motors = np.array(
            [[c.get("motor_x", 0.0), c.get("motor_y", 0.0)] for c in cells],
            dtype=float,
        )  # shape (n, 2)

        # Net per-step displacement (vector sum across all cells)
        net_motor: np.ndarray = motors.sum(axis=0)  # shape (2,)

        # ── trajectory integration ─────────────────────────────────────
        # Per-cell trajectories: shape (n, steps+1, 2)
        positions = np.zeros((n, steps + 1, 2))
        for t in range(steps):
            noise_arr = self._rng.normal(0.0, noise, size=(n, 2))
            for i, motor in enumerate(motors):
                positions[i, t + 1] = positions[i, t] + motor + noise_arr[i]

        # Aggregate (centroid) trajectory
        centroid = positions.mean(axis=0)  # shape (steps+1, 2)
        total_disp = np.linalg.norm(centroid[-1] - centroid[0])

        # ── plot ───────────────────────────────────────────────────────
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        fig.patch.set_facecolor("#0d1117")

        colors = cm.plasma(np.linspace(0.2, 0.9, n))

        # Left panel: individual cell trajectories
        ax1 = axes[0]
        ax1.set_facecolor("#161b22")
        for i, c in enumerate(cells):
            label = c.get("label", f"cell_{i}")
            traj = positions[i]
            ax1.plot(traj[:, 0], traj[:, 1], color=colors[i], lw=1.2,
                     alpha=0.8, label=label)
            ax1.scatter(*traj[0], color=colors[i], s=30, zorder=5, marker="o")
            ax1.scatter(*traj[-1], color=colors[i], s=60, zorder=5, marker="*")

        ax1.set_title("Cell Trajectories", color="white", fontsize=11, pad=8)
        ax1.set_xlabel("x (µm)", color="#8b949e")
        ax1.set_ylabel("y (µm)", color="#8b949e")
        ax1.tick_params(colors="#8b949e")
        for spine in ax1.spines.values():
            spine.set_edgecolor("#30363d")
        ax1.legend(fontsize=7, labelcolor="white",
                   facecolor="#21262d", edgecolor="#30363d")

        # Right panel: centroid trajectory + displacement
        ax2 = axes[1]
        ax2.set_facecolor("#161b22")
        ax2.plot(centroid[:, 0], centroid[:, 1],
                 color="#58a6ff", lw=2, label="centroid")
        ax2.scatter(*centroid[0], color="#3fb950", s=60, zorder=5,
                    marker="o", label="start")
        ax2.scatter(*centroid[-1], color="#f85149", s=80, zorder=5,
                    marker="*", label="end")

        # Annotate net displacement
        ax2.annotate(
            f"Δ = {total_disp:.2f} µm",
            xy=centroid[-1],
            xytext=(0.05, 0.93),
            textcoords="axes fraction",
            color="#e3b341",
            fontsize=9,
            arrowprops=dict(arrowstyle="->", color="#e3b341", lw=0.8),
        )

        ax2.set_title("Centroid Trajectory", color="white", fontsize=11, pad=8)
        ax2.set_xlabel("x (µm)", color="#8b949e")
        ax2.set_ylabel("y (µm)", color="#8b949e")
        ax2.tick_params(colors="#8b949e")
        for spine in ax2.spines.values():
            spine.set_edgecolor("#30363d")
        ax2.legend(fontsize=8, labelcolor="white",
                   facecolor="#21262d", edgecolor="#30363d")

        fig.suptitle(
            f"Xenobot Simulation  |  {n} cell(s)  |  {steps} steps",
            color="white", fontsize=13, y=1.01,
        )
        fig.tight_layout()

        # Encode to base64 PNG
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120,
                    bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode("utf-8")

        # ── summary text ───────────────────────────────────────────────
        summary = (
            f"Xenobot simulation complete.\n"
            f"  Cells: {n}  |  Steps: {steps}  |  Noise σ: {noise} µm\n"
            f"  Net motor vector: ({net_motor[0]:.3f}, {net_motor[1]:.3f}) µm/step\n"
            f"  Net displacement (centroid): {total_disp:.4f} µm\n"
            f"  Final centroid position: ({centroid[-1, 0]:.3f}, {centroid[-1, 1]:.3f}) µm"
        )

        return {
            "content": [
                {"type": "text",  "text": summary},
                {"type": "image", "data": img_b64, "media_type": "image/png"},
            ]
        }
