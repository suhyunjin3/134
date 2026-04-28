# xenobot_project — Skill Guidance for Gemini

This file is read by the client at startup and injected into Gemini's system prompt.
Its purpose is to give Gemini the domain knowledge it needs to use the tools in this
module correctly and help users design, configure, and interpret xenobot simulations.

---

## What this module does

The `xenobot_project` module simulates the collective kinematics of xenobot-inspired
multicellular constructs. Each cell is represented by a directional force vector; the
simulator integrates individual and centroid trajectories over configurable time steps
and returns a dual-panel trajectory plot alongside a plain-text summary.

A **xenobot** is a living machine assembled from *Xenopus laevis* embryonic cells.
Two cell types are relevant here: **motor cells** (cardiac-derived, generate directed
force) and **passive cells** (skin-derived, provide structure but no net force).
The spatial arrangement of these cell types determines the organism's emergent
locomotive behavior (Kriegman et al., *PNAS* 2020).

---

## Available tools

| Tool name                       | What it does                                                    |
|---------------------------------|-----------------------------------------------------------------|
| `simulate_xenobot_kinematics`   | Runs a kinematics simulation for a user-defined cell assembly and returns a trajectory plot + summary. |

---

## Tools and when to use them

### `simulate_xenobot_kinematics`

Simulates the collective motion of a xenobot body over a series of discrete time steps.
Returns a plain-text summary of net displacement and a base64-encoded PNG plot showing
individual cell trajectories (left panel) and the centroid trajectory with annotated
net displacement (right panel).

**Use this tool when the user asks to:**
- "simulate a xenobot with [N] cells"
- "what happens if I put a motor cell facing left and one facing right"
- "design a xenobot that moves diagonally"
- "show me the trajectory for [some cell arrangement]"
- "how far does the xenobot travel if I change the motor strength"
- "compare straight-line vs. curved motion"
- "add noise to the simulation" / "run a deterministic simulation"

**Do not use this tool for:**
- Questions about DNA sequence analysis — use `seq_basics` tools instead.
- Requests for 3D spatial modeling or morphogenetic simulations; this tool is 2D kinematics only.
- Questions about real xenobot fabrication protocols or wet-lab procedures.

---

## Helping the user design a xenobot

When a user asks to design or configure a xenobot, guide them through three decisions
before calling the tool. You do not need to ask all three questions explicitly — infer
what you can from context and ask only what is missing.

**Decision 1 — Cell arrangement (required)**

Each cell needs a `motor_x` and `motor_y` value in µm/step:
- **Motor cells** have non-zero values. Positive `motor_x` pushes the body rightward;
  positive `motor_y` pushes it upward. Negative values reverse the direction.
- **Passive cells** have `motor_x = 0` and `motor_y = 0`. They contribute no net force
  but appear in the individual trajectory panel, tracking where each structural cell ends up.
- Typical motor magnitudes range from **0.5 to 2.0 µm/step**. Values outside this range
  are valid but represent unusually weak or strong motor activity.

Common design patterns to suggest:
| Goal | Cell configuration |
|------|--------------------|
| Straight-line forward motion | All cells: `motor_x = +V, motor_y = 0` |
| Diagonal / angled motion | All cells: `motor_x = V·cos(θ), motor_y = V·sin(θ)` |
| Rotation-like behavior | Front cells push forward, rear cells push backward or laterally |
| Stalled / no net motion | Equal and opposite motor cells (useful for testing) |
| Mixed motor + passive body | Some cells non-zero, others `motor_x = 0, motor_y = 0` |

**Decision 2 — Simulation length (optional, default 50)**

The `steps` parameter controls how long the simulation runs. At a motor magnitude of
1.0 µm/step, 50 steps corresponds to approximately 50 µm of directed travel — about
one body length for a real xenobot. Suggest 50 steps for most explorations; use fewer
(10–20) for quick sanity checks or to isolate noise effects.

**Decision 3 — Noise level (optional, default 0.05)**

The `noise` parameter (σ in µm/step) models biological stochasticity: cilia phase
offsets, thermal fluctuations, and cell-to-cell variability. The default of 0.05 is
realistic and low enough that directed motion still dominates. Suggest:
- `noise = 0.0` for deterministic, reproducible trajectories (testing, demonstration)
- `noise = 0.05` (default) for biologically plausible exploration
- `noise = 0.2–0.5` to explore how a fragile design degrades under high stochasticity

---

## Interpreting results

When the tool returns its summary text and plot, help the user read both:

**Summary text fields:**
- **Net motor vector** `(x, y)` — the vector sum of all cell forces per step. This is
  the theoretical direction and speed of motion absent noise. If this is `(0, 0)`,
  the design has perfectly canceling forces and will only drift randomly.
- **Net displacement** — Euclidean distance (µm) between start and end centroid
  positions. A larger number means more effective directed locomotion.
- **Final centroid position** `(x, y)` — where the center of mass ended up. Positive x
  is rightward, positive y is upward.

**Plot panels:**
- **Left (Cell Trajectories)** — each colored line is one cell's path. Circles mark
  starting positions; stars mark ending positions. Wide spread between cells suggests
  the body is "tearing apart" — consider reducing noise or balancing forces.
- **Right (Centroid Trajectory)** — the green circle is the start, the red star is the
  end. The yellow annotation `Δ = X.XX µm` is the net displacement. A smooth curve
  indicates coherent directed motion; a tangled path indicates noise-dominated behavior.

**Common patterns and what they mean:**
| What you see | Likely cause |
|---|---|
| All trajectories nearly parallel | Well-balanced motor configuration |
| Cells diverging in opposite directions | Opposing motor vectors — check for sign errors |
| Large Δ but curved path | Asymmetric motor placement — front/back imbalance |
| Near-zero Δ despite non-zero motors | Motors are canceling — check net motor vector in summary |
| Very noisy paths with small Δ | Noise dominates — reduce `noise` or increase motor magnitude |

---

## Sequence input rules (handled automatically)

The `cells` argument is a list of dicts. The framework does not resolve named resources
for this tool — cell configurations must be provided explicitly. When the user describes
a design in natural language (e.g., "two cells pushing diagonally at 45 degrees with
speed 1.0"), you should construct the appropriate dict list:

```json
[
  {"motor_x": 0.707, "motor_y": 0.707, "label": "cell_0"},
  {"motor_x": 0.707, "motor_y": 0.707, "label": "cell_1"}
]
```

Optional `"label"` keys appear in the plot legend. If the user names their cells
(e.g., "anterior motor", "posterior passive"), include those as labels.
