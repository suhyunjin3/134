"""
pytest test suite for XenobotSim
=================================
Run from the project root:
    pytest modules/xenobot_project/tools/test_xenobot.py -v
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure the module is importable whether tests are run from the project root
# or from within the tools directory.
sys.path.insert(0, str(Path(__file__).parent))

from xenobot_sim import XenobotSim


# ── Fixtures ──────────────────────────────────────────────────────────────── #

@pytest.fixture
def sim() -> XenobotSim:
    """Return an initialised XenobotSim instance."""
    s = XenobotSim()
    s.initiate()
    return s


@pytest.fixture
def single_cell() -> list[dict]:
    return [{"motor_x": 1.0, "motor_y": 0.5, "label": "test_cell"}]


@pytest.fixture
def two_cells() -> list[dict]:
    return [
        {"motor_x": 1.0, "motor_y": 0.0, "label": "forward"},
        {"motor_x": 0.0, "motor_y": 1.0, "label": "upward"},
    ]


@pytest.fixture
def antagonist_cells() -> list[dict]:
    """Two cells with exactly opposing motors → zero net displacement (no noise)."""
    return [
        {"motor_x": 1.0, "motor_y": 0.0},
        {"motor_x": -1.0, "motor_y": 0.0},
    ]


# ── Output structure tests ─────────────────────────────────────────────────── #

class TestOutputStructure:

    def test_returns_dict_with_content(self, sim, single_cell):
        result = sim.run(single_cell)
        assert isinstance(result, dict), "run() must return a dict"
        assert "content" in result, "result must have 'content' key"

    def test_content_has_two_blocks(self, sim, single_cell):
        content = sim.run(single_cell)["content"]
        assert len(content) == 2, "content must have exactly 2 blocks"

    def test_first_block_is_text(self, sim, single_cell):
        block = sim.run(single_cell)["content"][0]
        assert block["type"] == "text"
        assert isinstance(block["text"], str)
        assert len(block["text"]) > 0

    def test_second_block_is_image(self, sim, single_cell):
        block = sim.run(single_cell)["content"][1]
        assert block["type"] == "image"
        assert block["media_type"] == "image/png"
        assert "data" in block

    def test_image_is_valid_base64_png(self, sim, single_cell):
        data = sim.run(single_cell)["content"][1]["data"]
        raw = base64.b64decode(data)
        # PNG magic bytes: 0x89 PNG \r\n \x1a \n
        assert raw[:8] == b"\x89PNG\r\n\x1a\n", "image data must be a valid PNG"


# ── Text summary content tests ─────────────────────────────────────────────── #

class TestSummaryText:

    def test_summary_mentions_net_displacement(self, sim, single_cell):
        text = sim.run(single_cell)["content"][0]["text"]
        assert "net displacement" in text.lower()

    def test_summary_mentions_cell_count(self, sim, two_cells):
        text = sim.run(two_cells)["content"][0]["text"]
        assert "cells: 2" in text.lower() or "2" in text

    def test_summary_mentions_steps(self, sim, single_cell):
        text = sim.run(single_cell, steps=15)["content"][0]["text"]
        assert "15" in text

    def test_summary_mentions_noise(self, sim, single_cell):
        text = sim.run(single_cell, noise=0.1)["content"][0]["text"]
        assert "0.1" in text


# ── Physics / kinematics tests ─────────────────────────────────────────────── #

class TestKinematics:

    def test_zero_net_displacement_antagonists(self, sim, antagonist_cells):
        """Two equal-and-opposite cells with no noise → centroid stays at origin."""
        result = sim.run(antagonist_cells, steps=20, noise=0.0)
        text = result["content"][0]["text"]
        # Extract the displacement value from the text
        for line in text.splitlines():
            if "net displacement" in line.lower():
                disp = float(line.split(":")[-1].strip().split()[0])
                assert disp < 1e-6, f"Expected ~0 displacement, got {disp}"
                break
        else:
            pytest.fail("Summary text did not contain 'net displacement'")

    def test_positive_x_motor_moves_right(self, sim):
        """Single cell with positive motor_x should end up to the right of origin."""
        result = sim.run([{"motor_x": 2.0, "motor_y": 0.0}], steps=10, noise=0.0)
        text = result["content"][0]["text"]
        for line in text.splitlines():
            if "final centroid position" in line.lower():
                coords = line.split(":")[-1].strip().strip("()µm").split(",")
                x_final = float(coords[0])
                assert x_final > 0, f"Expected x > 0, got {x_final}"
                break
        else:
            pytest.fail("Summary text did not contain 'Final centroid position'")

    def test_multiple_steps_increases_displacement(self, sim, single_cell):
        """More steps → larger (or equal) net displacement."""
        d10 = _extract_displacement(sim.run(single_cell, steps=10, noise=0.0))
        d50 = _extract_displacement(sim.run(single_cell, steps=50, noise=0.0))
        assert d50 >= d10, "Longer simulation should produce greater displacement"


# ── Edge-case / robustness tests ───────────────────────────────────────────── #

class TestEdgeCases:

    def test_empty_cells_returns_error(self, sim):
        result = sim.run([])
        text = result["content"][0]["text"].lower()
        assert "error" in text

    def test_single_cell_no_label(self, sim):
        """Cell without 'label' key should not raise."""
        result = sim.run([{"motor_x": 0.5, "motor_y": -0.3}])
        assert result["content"][1]["type"] == "image"

    def test_many_cells(self, sim):
        """Ten cells — should complete without error."""
        cells = [{"motor_x": float(i % 3 - 1), "motor_y": float(i % 2)} for i in range(10)]
        result = sim.run(cells, steps=20)
        assert result["content"][1]["type"] == "image"

    def test_initiate_is_idempotent(self):
        """Calling initiate() twice should not raise."""
        s = XenobotSim()
        s.initiate()
        s.initiate()
        result = s.run([{"motor_x": 1.0, "motor_y": 0.0}], steps=5)
        assert result["content"][0]["type"] == "text"

    def test_run_without_explicit_initiate(self):
        """run() should call initiate() automatically if not yet called."""
        s = XenobotSim()
        result = s.run([{"motor_x": 0.0, "motor_y": 1.0}], steps=5)
        assert result["content"][0]["type"] == "text"


# ── Helpers ───────────────────────────────────────────────────────────────── #

def _extract_displacement(result: dict) -> float:
    """Parse net displacement value from a run() result summary."""
    text = result["content"][0]["text"]
    for line in text.splitlines():
        if "net displacement" in line.lower():
            return float(line.split(":")[-1].strip().split()[0])
    raise ValueError("Could not find 'net displacement' in summary")
