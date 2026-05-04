# Task 1 — ANN with Backpropagation

## Structure

```
Q1/
├── ann.py        ← entire implementation
├── README.md     ← this file
└── outputs/      ← auto-created; plots saved here
```

## Run Commands

# Install dependency
pip install numpy matplotlib

# Basic runs
python ann.py --task xor
python ann.py --task cosine

# Experiments
python ann.py --task xor --experiment gd_sweep
python ann.py --task xor --experiment sgd_sweep
python ann.py --task cosine --experiment gd_sweep
python ann.py --task cosine --experiment sgd_sweep
