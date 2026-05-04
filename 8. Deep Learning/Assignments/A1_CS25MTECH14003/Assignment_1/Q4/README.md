# IIT-H Campus Life — Dataset Generation

Generates a synthetic dataset predicting how long a student spends in the mess at IIT Hyderabad.

## Requirements

```bash
pip install numpy
```

## Run

```bash
python data_generation.py
python data_generation.py --seed 7 --out_dir outputs --n_base 500 --n_aug 5000 --days 15
```

## Outputs

| File | Rows | Description |
|---|---|---|
| `iith_campus_life_500.csv` | 500 | Base dataset |
| `iith_campus_life_5000.csv` | 5000 | Augmented dataset |

## Arguments

| Argument | Default | Description |
|---|---|---|
| `--seed` | `7` | Random seed for reproducibility |
| `--out_dir` | `outputs` | Output directory |
| `--n_base` | `500` | Number of base samples |
| `--n_aug` | `5000` | Number of augmented samples |
| `--days` | `15` | Simulation window in days |

## Dataset

**Target:** `mess_duration_min` — time a student spends in the mess (10–120 min)

**15 features** covering student schedule (meal time, weekend, class day, deadline), weather (temperature, humidity, wind, rain, AQI), and student habits (wake-up time, sleep time).

For full feature descriptions and generation methodology see `dataset_description.pdf`.