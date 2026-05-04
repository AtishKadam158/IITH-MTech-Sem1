# Task 5 — ADALINE (Adaptive Linear Neuron)

## Directory Structure

A1_task5/
├── adaline.py              <- ADALINE class (Task 5.2)
├── task5_experiments.py    <- all experiments (Task 5.3 a/b/c/d)
├── README.md               <- this file
└── outputs/
    ├── iith_campus_life_5000.csv   <- dataset from Task 4
    ├── dataset_pca.png             
    ├── training_curves.png         
    ├── lr_sweep.png              
    └── size_vs_accuracy.png        

## How to Run
python task5_experiments.py


## Plots Produced (4 images)

| Image | Experiment |
|---|---|
| dataset_pca.png | (a) Dataset visualised in 2D PCA space |
| training_curves.png | (b) MSE curve + train/val MSE + decision boundary |
| lr_sweep.png | (c) Train & val MSE for eta in {0.01, 0.1, 1.0, 10.0} |
| size_vs_accuracy.png | (d) Test accuracy vs training set size 10%-100% |

## Dependencies
pip install numpy matplotlib

## Important Comment
It was instructed that Q 5.3.b (decision boundary plot) should be ignore as correction.
Still, I have included it as additional work since i already worked upon it.
It does not affect any other results.