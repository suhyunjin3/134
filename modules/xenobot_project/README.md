# Xenobot Kinematics Simulator
### BioE 234 — Final Project | Individual Module

---

## Overview

Xenobots are the first known class of living machines: millimeter-scale organisms
assembled from dissociated embryonic cells of *Xenopus laevis* (the African clawed
frog) and redesigned computationally to perform user-specified locomotive tasks.
Described by Kriegman et al. in their 2020 *PNAS* paper, ["A scalable pipeline for
designing reconfigurable organisms"](https://www.pnas.org/doi/10.1073/pnas.1910837117),
xenobots are composed of two functional cell types: **cardiac cells**, which contract
rhythmically and act as biological motors, and **passive skin cells**, which provide
structural scaffolding. The key insight from Kriegman et al. is that the *spatial
arrangement* of these two cell types — not genetic modification — determines emergent
locomotive behavior. An evolutionary algorithm explores billions of possible
configurations in silico, selecting designs that maximize displacement; the winning
designs are then physically assembled from frog cells using microsurgery.

This module simulates that locomotive behavior computationally. Rather than modeling
the full morphogenetic complexity of a real xenobot, it focuses on the **kinematic**
question: given a set of cells, each contributing a directional force, what collective
trajectory does the organism follow? Each motor cell contributes a force vector
`(motor_x, motor_y)` in micrometers per step, the net force is computed via vector
addition across the cell population, Gaussian noise models biological stochasticity,
and a discrete Euler integration scheme propagates individual and centroid trajectories
across a configurable number of time steps. The result is a dual-panel trajectory plot
returned as a base64-encoded PNG alongside a plain-text summary — both delivered inside
a single MCP tool response.

---

## Individual Contribution

This module was authored individually as part of the BioE 234 final project. All design
decisions, implementation, and documentation are original work.

**What I built:**

- `xenobot_sim.py` — the core `XenobotSim` class implementing `initiate()` and `run()`,
  including the NumPy-based force model, Euler integrator, noise injection, centroid
  computation, and dual-panel Matplotlib visualization pipeline.
- `xenobot_sim.json` — the C9 function wrapper declaring the full schema, typed inputs
  and outputs, worked examples, and execution entry points in compliance with
  `Function_Development_Specification.md`.
- `SKILL.md` — natural-language guidance injected into Gemini's system prompt, covering
  xenobot design patterns, parameter interpretation, and result explanation.
- `prompts.json` — three evaluation prompts covering cooperative, antagonist, and
  single-cell configurations, each with `expected_tool` and `expected_args`.
- `test_xenobot.py` — a pytest suite of 25 tests across five classes covering output
  structure, PNG validity, summary text content, kinematic correctness (including the
  zero-displacement antagonist case), and edge-case robustness.

**Key implementation choices I made and why** are detailed in the
[Design Decisions](#design-decisions) section below.

---

## C9 / MCP Architecture: The Verb–Noun Pattern

This module is built on the **Function Object Pattern** defined by the BioE 234 C9
framework. Every tool in the framework is a self-contained object that separates
*what it does* (a **verb**: `run`, `initiate`) from *what it operates on* (a **noun**:
`cells`, `steps`, `noise`). This mirrors the broader Verb–Noun design philosophy of
the C9 API, where operations like `Run`, `Show`, and `Query` are applied uniformly to
typed objects — functions, datasets, sequences — rather than being hard-coded into
monolithic scripts.

Concretely, `XenobotSim` is decoupled from the MCP server in three ways:

**1. No server imports.** `xenobot_sim.py` depends only on NumPy and Matplotlib. It has
no knowledge of `fastmcp`, `server.py`, or the Gemini client. It can be imported and
tested in any Python environment without standing up any server process.

**2. Registration is external.** The MCP server discovers this tool by reading
`xenobot_sim.json`, which declares the tool's schema, input types, and execution entry
points (`initiate` / `run`). The framework wraps the class automatically — the module
author never writes any MCP-specific plumbing.

**3. The output contract is transport-agnostic.** `run()` returns a plain Python
dictionary with a `"content"` list. The Gemini client knows how to render
`{"type": "text"}` and `{"type": "image"}` blocks; a different client (e.g., a CLI
renderer or a Jupyter notebook) could consume the same dict without any changes to the
simulator itself.

This separation means the simulator can be developed, validated, and extended entirely
independently of the communication layer it eventually runs inside.

---

## The Kinematics Model

Xenobots operate at **low Reynolds number** — the physical regime where viscous drag
dominates over inertia. At the micrometer scale, a cell that stops actively contracting
stops moving almost instantaneously; there is no coasting. This makes Newtonian force
balance, rather than momentum integration, the appropriate physical framework: at every
instant, the net propulsive force produced by the motor cells is exactly balanced by
the drag force resisting motion through the surrounding fluid.

### Cell Force Vectors

Each cell is represented by a two-dimensional propulsive force vector:

```
f_i = (motor_x_i, motor_y_i)   [µm / step]
```

`motor_x` is the cell's contribution to rightward displacement per time step; `motor_y`
is its contribution to upward displacement. Negative values model cells that pull in
the opposing direction — analogous to placing cardiac cells on the posterior face of a
xenobot body to generate backward thrust. **Passive cells** (skin cells providing
structural scaffolding) are represented by `motor_x = 0, motor_y = 0`: they contribute
no propulsive force and act as drag-only elements in the body.

### Vector Addition and Net Propulsive Force

The net propulsive force at each time step is the **vector sum** across all `n` cells:

```
F_net = Σ f_i  =  (Σ motor_x_i,  Σ motor_y_i)
```

This is computed in a single NumPy operation:

```python
motors = np.array([[c["motor_x"], c["motor_y"]] for c in cells])  # shape (n, 2)
net_motor = motors.sum(axis=0)                                      # shape (2,)
```

Vector addition is appropriate here because, at low Reynolds number, forces superpose
linearly and the body velocity at each step is proportional to the net force. Two motor
cells pulling with equal force in opposite directions cancel exactly — validated by the
antagonist test case (`motor_x = +1` and `motor_x = −1` → net displacement = 0 with
`noise = 0`).

### Drag and Passive Cells

In the low-Reynolds-number regime, drag is **linear in velocity** (Stokes drag):

```
F_drag = −γ · v
```

where `γ` is the drag coefficient. At mechanical equilibrium per step,
`F_net = F_drag`, so:

```
v = F_net / γ
```

In this model, `γ` is absorbed into the units of `motor_x` and `motor_y` — each value
already represents the net displacement per step *after* drag has been balanced, so no
explicit drag coefficient parameter is exposed. **Passive cells** contribute
`f_i = (0, 0)` to the propulsive numerator while implicitly increasing the effective
drag denominator by adding to the body's surface area. In practice, adding passive
cells to a design dilutes the average displacement per step because the motor cells
must drag more body mass and surface area through the fluid — a configurable tradeoff
that users can explore by adjusting the ratio of motor to passive cells.

### Biological Noise

Real xenobots exhibit stochastic behavior: cilia beat with slight phase offsets, thermal
fluctuations perturb trajectories, and cell-to-cell variability exists even within a
clonal population. The simulator models this with additive Gaussian noise drawn fresh at
every step for every cell:

```python
noise_arr = self._rng.normal(0.0, noise, size=(n, 2))   # σ = noise [µm/step]
```

The default noise level of `σ = 0.05 µm/step` is small relative to a typical motor
magnitude of 0.5–2.0 µm/step, so it perturbs individual trajectories visibly while
preserving the dominant directed motion. Setting `noise = 0.0` recovers fully
deterministic trajectories, which is useful for unit testing and for isolating the
effect of cell arrangement.

### Euler Integration

Individual cell positions are propagated using first-order **Euler integration** — the
simplest explicit scheme for an ODE of the form `dx/dt = v(t)`. In the low-Re limit
where velocity is proportional to net force, this becomes:

```
x_i(t+1) = x_i(t) + f_i + ε_i(t)
```

where `ε_i(t) ~ N(0, σ²)` is the per-step noise term. All cells start at the origin
`(0, 0)`. The full trajectory tensor has shape `(n_cells, steps+1, 2)`, storing every
position for every cell at every step.

The **centroid trajectory** — the mean position across all cells at each step —
summarizes the collective motion of the body:

```python
centroid = positions.mean(axis=0)   # shape (steps+1, 2)
```

Net displacement is the Euclidean distance between the centroid's initial and final
positions:

```python
total_disp = np.linalg.norm(centroid[-1] - centroid[0])
```

The default simulation runs for **50 steps**. At a motor magnitude of 1.0 µm/step with
`σ = 0.05`, this corresponds to approximately 50 µm of directed travel — on the order
of a real xenobot's body length, making the simulation physically grounded even in its
simplified form.

---

## Project Structure

```
modules/
└── xenobot_project/
    ├── SKILL.md                   # Natural-language capability description for Gemini
    ├── README.md                  # This file
    └── tools/
        ├── xenobot_sim.py         # XenobotSim class — initiate() + run()
        ├── xenobot_sim.json       # C9 function wrapper (schema, I/O, execution details)
        ├── prompts.json           # Evaluation prompts with expected_tool + expected_args
        └── test_xenobot.py        # pytest suite (25 tests across 5 test classes)
```

The naming of `xenobot_sim.py` and `xenobot_sim.json` is intentional: the BioE 234
framework discovers and registers tools by matching `.py` and `.json` files of the same
stem within a `tools/` directory. Renaming either file without updating the other will
break auto-registration.

---

## Design Decisions

### Why NumPy for the force calculation?

The alternative — a Python loop over cell dicts summing `motor_x` and `motor_y`
manually — would be functionally identical for small cell counts but would not scale.
NumPy's `array.sum(axis=0)` batches the entire cell population into a single vectorized
C-level operation, and the trajectory tensor `positions` of shape `(n, steps+1, 2)`
enables slicing across the full simulation history without any Python-level loops over
time steps. This matters when the simulator is called many times in sequence (e.g.,
during a parameter sweep comparing many cell arrangements), and it keeps the core math
readable as a direct transcription of the linear algebra.

### Why a class (`XenobotSim`) rather than a module-level function?

A standalone function `run(cells, ...)` would work for a single call, but it cannot
cheaply maintain state across calls. The `XenobotSim` class holds a seeded
`np.random.default_rng` instance initialized once in `initiate()`, which guarantees
**reproducible** trajectories across repeated `run()` calls within the same session
(seed=42). If the simulator were a bare function, every call would either re-seed
(losing cross-call reproducibility) or rely on global state (not thread-safe). The
class pattern also matches the C9 Function Object Pattern directly — the framework
expects an `initiate` method for setup and a `run` method for execution — so using a
class is both architecturally correct and practically required for framework
compatibility.

### Why is the drag coefficient implicit rather than an explicit parameter?

Exposing a raw `gamma` drag coefficient would make the interface more physically
precise but would require users to understand the relationship between force, drag, and
resulting velocity at the microscale — a significant friction cost for a tool intended
to be invoked through natural language. Instead, `motor_x` and `motor_y` are defined
directly in units of µm/step: they already encode the net displacement per step *after*
drag has been balanced. The effect of adding passive (high-drag) cells is still visible
and explorable — more passive cells dilute the net motor force per unit surface area —
without requiring the user to reason in terms of Stokes coefficients. A future version
could expose a `drag_per_passive_cell` parameter for users who want explicit control.

---

## Usage

### Calling the tool via the Gemini client

Start the MCP server and Gemini client from the project root:

```bash
python client_gemini.py
```

Once connected, invoke the simulator in natural language:

```
You: Simulate a xenobot with two motor cells pushing diagonally —
     motor_x=1.0, motor_y=0.5 and motor_x=0.5, motor_y=1.0 —
     over 30 steps with noise 0.05.
```

Gemini will call `simulate_xenobot_kinematics` with the following arguments and return
the trajectory plot inline:

```json
{
  "cells": [
    {"motor_x": 1.0, "motor_y": 0.5, "label": "cilia_cell_1"},
    {"motor_x": 0.5, "motor_y": 1.0, "label": "cilia_cell_2"}
  ],
  "steps": 30,
  "noise": 0.05
}
```

To run a saved evaluation prompt directly, use the `/prompt` slash command:

```
You: /prompt simulate_xenobot {"cells": [{"motor_x": 2.0, "motor_y": 0.0}]}
```

### Calling the class directly (Python)

```python
from modules.xenobot_project.tools.xenobot_sim import XenobotSim

sim = XenobotSim()
sim.initiate()

result = sim.run(
    cells=[
        {"motor_x": 1.0, "motor_y": 0.5, "label": "anterior_motor"},
        {"motor_x": 0.0, "motor_y": 0.0, "label": "passive_skin"},
    ],
    steps=50,
    noise=0.05,
)

print(result["content"][0]["text"])    # plain-text summary
# result["content"][1]["data"]  →  base64-encoded PNG
```

To decode and display the plot in a Jupyter notebook:

```python
import base64
from IPython.display import Image, display

img_data = base64.b64decode(result["content"][1]["data"])
display(Image(data=img_data))
```

### Running the test suite

```bash
# From the project root
pytest modules/xenobot_project/tools/test_xenobot.py -v
```

Expected output (25 tests):

```
TestOutputStructure::test_returns_dict_with_content        PASSED
TestOutputStructure::test_content_has_two_blocks           PASSED
TestOutputStructure::test_first_block_is_text              PASSED
TestOutputStructure::test_second_block_is_image            PASSED
TestOutputStructure::test_image_is_valid_base64_png        PASSED
TestSummaryText::test_summary_mentions_net_displacement    PASSED
TestSummaryText::test_summary_mentions_cell_count          PASSED
TestSummaryText::test_summary_mentions_steps               PASSED
TestSummaryText::test_summary_mentions_noise               PASSED
TestKinematics::test_zero_net_displacement_antagonists     PASSED
TestKinematics::test_positive_x_motor_moves_right          PASSED
TestKinematics::test_multiple_steps_increases_displacement PASSED
TestEdgeCases::test_empty_cells_returns_error              PASSED
TestEdgeCases::test_single_cell_no_label                   PASSED
TestEdgeCases::test_many_cells                             PASSED
TestEdgeCases::test_initiate_is_idempotent                 PASSED
TestEdgeCases::test_run_without_explicit_initiate          PASSED
...
25 passed
```

To run only the kinematics physics tests:

```bash
pytest modules/xenobot_project/tools/test_xenobot.py::TestKinematics -v
```

---

## Dependencies

| Package      | Role                                                                         | Min version |
|--------------|------------------------------------------------------------------------------|-------------|
| `numpy`      | Motor matrix construction, trajectory integration, displacement calculation  | 1.24        |
| `matplotlib` | Dual-panel trajectory plot (Agg non-interactive backend)                     | 3.7         |
| `pytest`     | Test suite execution                                                         | 7.0         |
| `fastmcp`    | MCP server / client transport (framework-level; not imported by this module) | —           |

---

## References

Kriegman, S., Blackiston, D., Levin, M., & Bongard, J. (2020). A scalable pipeline for
designing reconfigurable organisms. *Proceedings of the National Academy of Sciences*,
117(4), 1853–1859. https://doi.org/10.1073/pnas.1910837117
