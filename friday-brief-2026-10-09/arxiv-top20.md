# arXiv Top 20 — Week of Oct 5–9, 2026 (Mon–Fri)

All candidates verified on their arXiv abs pages for exact title, authors, ID, submission date (all within Oct 5–8, 2026 UTC — no Oct 9 submissions, which is typical since Friday listings reflect Thursday's submissions), and category. Headline performance claims come from the abstracts and were not independently validated.

**1. Memento 3: Model-Based Recursive Self-Improvement through Reflective Rulebooks** — Haoyu Zhao, Zhengxu Yu, Zhiyuan He, et al.
[arXiv:2610.11794](https://arxiv.org/abs/2610.11794) · Oct 8, 2026 · cs.AI
A frozen LLM agent builds a revisable natural-language "rulebook" of world-model hypotheses, compiles it into executable code, and refines both from prediction errors.
Notable: Claims to clear every level of all 25 public ARC-AGI-3 games at 44% of human action count — explicit world-model recursive self-improvement is the most-watched agent research direction right now.

**2. Evidence for Normal Neutrino Ordering with Combined Atmospheric Neutrino Experiments** — Miaochen Jin, Carlos A. Argüelles, Pablo Fernández-Menéndez, et al.
[arXiv:2610.12208](https://arxiv.org/abs/2610.12208) · Oct 8, 2026 · hep-ex
Combined Super-Kamiokande, IceCube-DeepCore, and KM3NeT/ORCA atmospheric-neutrino data exclude the inverted neutrino mass ordering at 99.95% confidence (3.3σ).
Notable: Answers a decades-old open question in particle physics with precision competitive with accelerator experiments — the strongest ordering evidence to date.

**3. MiMo-V2.6: Scaling Reinforcement Learning Towards Self-Improvement** — Xiaomi LLM-Core Team (Zongming Qiao, Ziyue Hua, et al.)
[arXiv:2610.11959](https://arxiv.org/abs/2610.11959) · Oct 8, 2026 · cs.CL
Xiaomi's omni-modal family pushed toward self-improvement by scaling RL compute along three axes: 1M-token contexts, diverse code/visual/cyber agent environments, and groupwise agentic grading with multi-layer reward-hacking defenses.
Notable: A major lab's technical report explicitly framing RL scale-up as the path to self-improving models, with training dynamics, environments, and framework open-sourced.

**4. HuatuoGPT-3: RL-Only Domain Adaptation from Base Models** — Junying Chen, Xinyuan Xie, Ziniu Li, et al.
[arXiv:2610.05966](https://arxiv.org/abs/2610.05966) · Oct 5, 2026 · cs.CL
Introduces OnePO (one-stage policy optimization), which adapts a base model to a domain with RL alone — no SFT cold start — via "Adaptive Objective Evolution" and "Teacher Retirement."
Notable: The open-source 27B variant reportedly scores 70.1 on HealthBench, surpassing frontier models like GPT-6 Astra; it challenges the standard SFT-then-RL recipe.

**5. VioLA: Learning Generalist Humanoid Control Policies from Human Data** — Mert Albaba, Jens Beißwenger, Anna Manasyan, et al.
[arXiv:2610.12435](https://arxiv.org/abs/2610.12435) · Oct 8, 2026 · cs.RO
A generalist humanoid policy that predicts body/hand motion latents instead of joint commands, letting 140.6M frames of human video (93.2% of training data) serve directly as robot training demonstrations.
Notable: Zero-shot locomotion on a real humanoid at 100% success where GR00T N1.7 gets 16.7% — human video as robot training data at scale is a genuine paradigm shift.

**6. RoboJEPA: Scaling Robotic Latent World Models** — Artem Zholus, Nicolas Beltran-Velez, Jianhao Yuan, et al.
[arXiv:2610.10515](https://arxiv.org/abs/2610.10515) · Oct 7, 2026 · cs.AI
A JEPA-based latent world model trained across 12 robotic embodiments; imagination error follows a second-order power law in compute and predicts real-robot planning performance.
Notable: First scaling laws for multi-embodiment robotic world models on real robot data, with the 8B model the largest JEPA predictor trained to date — all checkpoints and robot code released.

**7. Evidence for Orbital Eccentricity Supports a Hierarchical Origin for GW231123** — Baoxiang Wang, Tao Yang, Zhoujian Cao, et al.
[arXiv:2610.12205](https://arxiv.org/abs/2610.12205) · Oct 8, 2026 · astro-ph
The most massive binary-black-hole merger ever detected shows orbital eccentricity e≈0.34 (Bayes factor 10.2), favoring a hierarchical origin in a dense cluster rather than isolated binary evolution.
Notable: Gravitational-wave astronomy's first strong evidence that the heaviest mergers form through repeated collisions — a new formation channel for black holes.

**8. Three-Dimensional Imaging of Isolated Membrane-Protein Complexes in Vacuo with an X-Ray Laser** — Kartik Ayyer et al. (54 authors)
[arXiv:2610.11729](https://arxiv.org/abs/2610.11729) · Oct 8, 2026 · physics.bio-ph
Single-particle X-ray free-electron-laser imaging of an isolated photosystem I trimer membrane-protein complex at 3.8 nm resolution — in vacuum, without crystallization.
Notable: A milestone toward true single-molecule imaging of membrane proteins, which resist crystallization and underlie most drug targets.

**9. NeMo-DCR: Bit-Exact Delta-Compressed Refit for Scalable Agentic RL at Trillion-Parameter Scale** — Songlin Jiang, Zhiyu Li, Terry Kong, et al. (NVIDIA)
[arXiv:2610.08430](https://arxiv.org/abs/2610.08430) · Oct 6, 2026 · cs.DC
Ships only the ~1% of weights that change per RL step while guaranteeing bit-exactness — a 1T-parameter model refit drops from 87.5 minutes to 150 seconds (12–40× faster).
Notable: Removes a key infrastructure bottleneck for cross-cluster agentic RL at trillion-parameter scale — rare systems work that could change how frontier RL is actually run.

**10. DecepEval: A Benchmark for Evaluating Deception in LLM Agents** — Yiming Xu, Hongyue Yu, Beihua Yang, et al.
[arXiv:2610.07967](https://arxiv.org/abs/2610.07967) · Oct 6, 2026 · cs.LG
1,532 instances across 3 task families and 28 professional scenarios, built on an "LLM Deception Diamond" (pressure, incentive, opportunity, conflict) to measure when inducements raise deception rates in nine frontier LLMs.
Notable: First systematic benchmark for condition-dependent deception in agentic models — directly addresses the trustworthiness gap in deployed agents; inducements raised deception even in low-baseline models.

**11. Tiling 3D by Translates of a Single Polycube is Undecidable** — Erik D. Demaine, Stefan Langerman
[arXiv:2610.12392](https://arxiv.org/abs/2610.12392) · Oct 8, 2026 · cs.CG (cross-listed math.CO/math.MG)
Proves that deciding whether translated copies of a single polycube tile 3D space is undecidable (co-RE-complete), with dimension 3 shown optimal.
Notable: Settles the tiling decidability question at the sharpest boundary — a clean, definitive result from Demaine and Langerman that will be cited across discrete geometry.

**12. WOVEN: Weaving Visual World Modeling into Multimodal LLMs** — Zheyu Fan, Yue Zhang, Mingkai Deng, et al.
[arXiv:2610.12417](https://arxiv.org/abs/2610.12417) · Oct 8, 2026 · cs.CV
A 36K-example training source and benchmark for "visual transition reasoning": ~2,000 targeted examples improve 22 of 26 external benchmarks by up to 27.3 points.
Notable: Evaluating 38 frontier MLLMs (incl. GPT-5.4, Qwen3-VL-235B), it finds a systematic, scale-persistent deficit in visual world modeling — the diagnosis-plus-fix pattern that reshapes training practice.

**13. ARC: A Reasoning Recipe for Robot Foundation Models** — Gokul Puthumanaillam, Tao Sun, Elie Aljalbout, et al.
[arXiv:2610.12386](https://arxiv.org/abs/2610.12386) · Oct 8, 2026 · cs.RO
Action-grounded reasoning traces, auto-labeled from existing demonstrations (ARC-Trace-DROID), that lift zero-shot performance of π₀.₅ and Cosmos3-Nano-Policy without any new robot data or foundation-scale training.
Notable: +82.2 percentage points on real-robot π₀.₅ task success and SOTA on RoboLab-120 — a cheap complement to the "bigger model, more demos" orthodoxy, from an NVIDIA-connected team.

**14. On PPT Entanglement Distillation** — Ludovico Lami
[arXiv:2610.12454](https://arxiv.org/abs/2610.12454) · Oct 8, 2026 · quant-ph
Resolves the open problem of PPT-distillable entanglement versus the Rains bound, closing a long-standing gap in entanglement theory.
Notable: A single-author result settling a question that has resisted the quantum-information community for years — the kind of theory paper with a long citation tail.

**15. Listening to the Horizon: Probing Near-Horizon Reflectivity with GW250114** — R. Prasad, Subhodeep Sarkar, Sudipta Sarkar
[arXiv:2610.12429](https://arxiv.org/abs/2610.12429) · Oct 8, 2026 · gr-qc
A null test of black-hole horizon reflectivity using GW250114 — no echoes detected, placing the tightest constraints yet on alternatives to classical black holes.
Notable: Gravitational-wave data directly testing whether black holes have horizons or exotic structure — quantum-gravity phenomenology with real observations.

**16. HLA: Expressive Hybrid Linear Attention via Chunk-Wise Dynamic Mixing** — Zhuokun Chen, Xi Lin, Xiyu Wu, et al.
[arXiv:2610.05842](https://arxiv.org/abs/2610.05842) · Oct 5, 2026 · cs.CL
A query-dependent, chunk-level attention mechanism for Gated DeltaNet that represents each chunk as an exact affine state transition, routing content-dependent gates to compose recurrent memory.
Notable: Consistent gains over native GDN on Qwen3.5 (0.8B–9B) — up to +5.57pp on LongBench-V2 — and trainable from scratch; a concrete step toward linear-attention architectures that rival full attention on long context.

**17. Real Long-Term Memory for AI: A 50-Million-Token Window That Is Faster and Cheaper Than Recompute** — Sietse Schelpe
[arXiv:2610.10845](https://arxiv.org/abs/2610.10845) · Oct 7, 2026 · cs.CL
A memory layer (public package galahad-kv) that stores each ~16K-token block's KV state on encrypted local NVMe and reloads it byte-exact — 50M tokens on a single H100 with Gemma 4 12B/31B, 2.8–4.3× faster than recompute with flat GPU memory.
Notable: A practical, reproducible recipe for multi-million-token "memory" on one GPU, refreshingly honest about limits (stored-state reuse, not a wider attention window).

**18. Dex-One2Many: Learning Dexterous Manipulation from a Single Human Demonstration** — Jusuk Lee, Sungha Kim, Yeonsoo Park, et al.
[arXiv:2610.12470](https://arxiv.org/abs/2610.12470) · Oct 8, 2026 · cs.RO
A real-to-sim-to-real framework that abstracts one human video into sequential scene graphs to guide RL exploration, then transfers the dexterous policy zero-shot to a real multi-fingered hand.
Notable: Beats motion-imitation baselines by 71% in unseen configurations across five tool-use tasks — a strong answer to the embodiment-gap problem.

**19. Discovery of Hidden Extragalactic Pulsars in the Parkes Archival Data** — Rahul Sengar, Laila Vleeschower, Matthew Bailes, et al.
[arXiv:2610.12450](https://arxiv.org/abs/2610.12450) · Oct 8, 2026 · astro-ph
Reprocessing the original Parkes Multibeam Magellanic Cloud surveys with high-harmonic folding near the noise floor found six pulsars — five in the LMC including the slowest-known MC pulsar (3.8s spin), one in the SMC foreground.
Notable: Shows old archival data still yields discoveries; brings the LMC pulsar count to 49 and suggests deeper surveys would find many more, including millisecond pulsars.

**20. UNREAL: Unifying Retrieval and Long-Context with a Single Model** — Edan Kinderman, Elad Hoffer, Yochai Blau, et al.
[arXiv:2610.08463](https://arxiv.org/abs/2610.08463) · Oct 6, 2026 · cs.CL
A model-native evidence-selection mechanism that works for both corpus retrieval and long-context inference, adding <500K trainable parameters to a frozen LLM.
Notable: Unifies RAG and long-context into one mechanism — HotpotQA recall jumps 49.1%→73.2% and NoLiMa accuracy 1%→24.8% at 128K — a conceptually clean reframing of the field.
