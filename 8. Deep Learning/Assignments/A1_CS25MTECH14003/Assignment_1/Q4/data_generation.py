#!/usr/bin/env python3
import argparse
import csv
import os
import numpy as np


# Constants 

MEAL_TIMES    = {0: "breakfast", 1: "lunch", 2: "dinner"}
BASE_DURATION = {0: 18.0, 1: 34.0, 2: 44.0}   # base mess duration (min) per meal type

COLUMNS = [
    "student_id", "day_of_week", "meal_time", "meal_type",
    "is_weekend", "class_day", "assignment_deadline",
    "temperature_c", "humidity", "wind_speed", "rain_mm",
    "air_quality_index", "rising_time_min", "sleeping_time_min",
    "mess_duration_min",
]

AUG_NOISE = {
    "temperature_c":     0.7,
    "humidity":          2.5,
    "wind_speed":        0.5,
    "rain_mm":           1.2,
    "air_quality_index": 7.0,
    "rising_time_min":   9.0,
    "sleeping_time_min": 9.0,
}

BOUNDS = {
    "temperature_c":     (15.0,  42.0),
    "humidity":          ( 0.0, 100.0),
    "wind_speed":        ( 0.0,  25.0),
    "rain_mm":           ( 0.0,  60.0),
    "air_quality_index": (20.0, 350.0),
    "rising_time_min":   (4*60,  11*60),    # 04:00 – 11:00
    "sleeping_time_min": (19*60, 23*60+59), # 19:00 – 23:59
}


# Helpers

def bounded(arr, key):
    """Clip array to the allowed range for a given feature."""
    lo, hi = BOUNDS[key]
    return np.minimum(np.maximum(arr, lo), hi)

def hm(h, m=0):
    """Convert hours + minutes to total minutes from 00:00."""
    return h * 60 + m

def logistic(x):
    """Numerically stable sigmoid."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))


# Weather Simulation

def simulate_weather(num_days, rng):
    """Generate daily weather arrays using sinusoidal trends + Gaussian noise,
    calibrated to the Hyderabad climate profile."""
    t     = np.arange(num_days, dtype=float)
    cycle = 2.0 * np.pi * t / num_days

    temp = bounded(30.0 + 3.0 * np.sin(cycle + 0.3) + rng.normal(0, 0.9, num_days), "temperature_c")
    hum  = bounded(60.0 + 16.0 * np.cos(cycle - 0.5) + rng.normal(0, 5.0, num_days), "humidity")
    wind = bounded(2.0 + 1.2 * np.abs(np.sin(cycle)) + rng.normal(0, 0.5, num_days), "wind_speed")

    # Rain probability driven by humidity; flag × random amount
    rain_prob = logistic((hum - 72.0) / 7.0) * 0.55
    rain_flag = (rng.random(num_days) < rain_prob).astype(float)
    rain_amt  = bounded(rain_flag * (np.abs(rng.normal(0, 5.0, num_days)) + rng.random(num_days) * 3.0), "rain_mm")

    aqi = bounded(105.0 + 20.0 * np.sin(cycle + 1.0) + rng.normal(0, 10.0, num_days), "air_quality_index")

    return {"temperature_c": temp, "humidity": hum,
            "wind_speed": wind, "rain_mm": rain_amt,
            "air_quality_index": aqi}


# Student Profiles 

def build_student_profiles(unique_ids, rng):
    """Assign each student a habitual rise time, sleep time, and eating pace."""
    n = len(unique_ids)
    rise  = rng.normal(hm(7, 30), 40.0, n)
    sleep = rng.normal(hm(23, 0), 50.0, n)
    pace  = rng.normal(0.0, 3.5, n)

    profiles = {}
    for i, sid in enumerate(unique_ids):
        profiles[int(sid)] = {
            "rise":  float(np.clip(rise[i],  *BOUNDS["rising_time_min"])),
            "sleep": float(np.clip(sleep[i], *BOUNDS["sleeping_time_min"])),
            "pace":  float(pace[i]),
        }
    return profiles


# Base Dataset (500 samples)

def generate_base(n_samples, num_days, rng, start_dow=0):
    """Simulate n_samples records across num_days. start_dow=0 means day 0 is Monday."""
    day_idx    = rng.integers(0, num_days, size=n_samples)
    dow        = (start_dow + day_idx) % 7
    is_weekend = (dow >= 5).astype(int)

    meal_time = rng.integers(0, 3, size=n_samples)
    meal_type = (rng.random(n_samples) < 0.28).astype(int)   # ~28% non-veg

    # weekdays: 85% chance of class; weekends: 10% chance
    free_prob  = np.where(is_weekend == 1, 0.90, 0.15)
    class_day  = (rng.random(n_samples) < free_prob).astype(int)

    # 3 random days designated as deadline days; encoded as 0 = deadline, 1 = no deadline
    deadline_days       = rng.choice(num_days, size=3, replace=False)
    assignment_deadline = 1 - np.isin(day_idx, deadline_days).astype(int)

    student_id = rng.integers(2101001, 2101200, size=n_samples)
    profiles   = build_student_profiles(np.unique(student_id), rng)

    # map daily weather to each record, then add small per-record micro-noise
    daily_wx = simulate_weather(num_days, rng)

    def wx_col(key, micro_std):
        return bounded(daily_wx[key][day_idx] + rng.normal(0, micro_std, n_samples), key)

    temperature_c     = np.round(wx_col("temperature_c",     0.4), 2)
    humidity          = np.round(wx_col("humidity",          1.8), 2)
    wind_speed        = np.round(wx_col("wind_speed",        0.3), 2)
    rain_mm           = np.round(wx_col("rain_mm",           0.6), 2)
    air_quality_index = np.round(wx_col("air_quality_index", 5.0), 1)

    rising_time   = np.zeros(n_samples, dtype=float)
    sleeping_time = np.zeros(n_samples, dtype=float)
    pace_effect   = np.zeros(n_samples, dtype=float)

    # per-student rising/sleeping times adjusted for context, then add daily noise
    for i in range(n_samples):
        p = profiles[int(student_id[i])]
        pace_effect[i] = p["pace"]

        r  = p["rise"]
        r += 28.0 * is_weekend[i]                    # wake later on weekends
        r -= 12.0 * (1 - class_day[i])               # wake earlier when class exists
        r -= 8.0  * (1 - assignment_deadline[i])      # wake earlier on deadline day
        r += rng.normal(0, 12.0)
        rising_time[i] = np.clip(r, *BOUNDS["rising_time_min"])

        s  = p["sleep"]
        s += 18.0 * is_weekend[i]                    # stay up later on weekends
        s += 25.0 * (1 - assignment_deadline[i])      # stay up late on deadline day
        s += rng.normal(0, 15.0)
        sleeping_time[i] = np.clip(s, *BOUNDS["sleeping_time_min"])

    rising_time   = np.round(rising_time).astype(int)
    sleeping_time = np.round(sleeping_time).astype(int)

    # additive model for target: base + behavioural + weather + noise
    duration  = np.array([BASE_DURATION[m] for m in meal_time], dtype=float)
    duration += pace_effect                                      # slow/fast eater offset
    duration += 4.5 * is_weekend                                 # linger longer on weekends
    duration += 2.5 * meal_type                                  # non-veg takes more time
    duration += 3.5 * class_day                                  # no rush on free days
    duration -= 3.0 * (1 - assignment_deadline)                  # eat quickly on deadline day
    duration += 0.06 * (humidity - 55.0)                         # high humidity → slower
    duration += 0.20 * rain_mm                                   # rain → crowd lingers
    duration += 0.12 * np.abs(temperature_c - 29)                # extreme temp → discomfort
    duration -= 0.012 * (air_quality_index - 100)                # bad AQI → leave sooner
    duration += (meal_time == 0).astype(float) * (-0.035 * (rising_time.astype(float) - hm(8, 0)))  # late riser eats faster at breakfast
    duration += rng.normal(0, 3.8, n_samples)                    # residual noise
    duration  = np.round(np.clip(duration, 10.0, 120.0), 2)

    return {
        "student_id":           student_id.astype(int),
        "day_of_week":          dow.astype(int),
        "meal_time":            meal_time.astype(int),
        "meal_type":            meal_type.astype(int),
        "is_weekend":           is_weekend.astype(int),
        "class_day":            class_day.astype(int),
        "assignment_deadline":  assignment_deadline.astype(int),
        "temperature_c":        temperature_c,
        "humidity":             humidity,
        "wind_speed":           wind_speed,
        "rain_mm":              rain_mm,
        "air_quality_index":    air_quality_index,
        "rising_time_min":      rising_time,
        "sleeping_time_min":    sleeping_time,
        "mess_duration_min":    duration,
    }


# Augmentation (500 → 5000)

def augment(base, n_aug, rng):
    """Tile the base dataset and add Gaussian noise only to continuous input features.
    Discrete columns and the target are left unchanged."""
    n_base = base["student_id"].shape[0]
    reps   = int(np.ceil(n_aug / n_base))
    tiled  = {col: np.tile(base[col], reps)[:n_aug] for col in COLUMNS}

    for col, std in AUG_NOISE.items():
        lo, hi = BOUNDS[col]
        noisy = np.clip(tiled[col].astype(float) + rng.normal(0, std, n_aug), lo, hi)
        # preserve integer dtype for time columns
        if col in ("rising_time_min", "sleeping_time_min"):
            tiled[col] = np.round(noisy).astype(int)
        elif col == "air_quality_index":
            tiled[col] = np.round(noisy, 1)
        else:
            tiled[col] = np.round(noisy, 2)

    return tiled


# CSV Writer

def save_csv(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    n = len(data[COLUMNS[0]])
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for i in range(n):
            writer.writerow([data[c][i] for c in COLUMNS])
    print(f"saved {path}  ({n} rows)")


# Entry Point 

def compute_stats(data):
    d = data["mess_duration_min"].astype(float)
    return {"n": len(d), "mean": float(np.mean(d)), "std": float(np.std(d)),
            "min": float(np.min(d)), "max": float(np.max(d))}


def main():
    ap = argparse.ArgumentParser(description="IIT-H Campus Life Dataset Generator")
    ap.add_argument("--seed",    type=int, default=7)
    ap.add_argument("--out_dir", type=str, default="outputs")
    ap.add_argument("--n_base",  type=int, default=500)
    ap.add_argument("--n_aug",   type=int, default=5000)
    ap.add_argument("--days",    type=int, default=15)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    os.makedirs(args.out_dir, exist_ok=True)

    print("generating base dataset (500 samples) ...")
    base = generate_base(args.n_base, args.days, rng)

    print("augmenting to 5000 samples ...")
    aug = augment(base, args.n_aug, rng)

    print("saving csv files ...")
    save_csv(os.path.join(args.out_dir, "iith_campus_life_500.csv"),  base)
    save_csv(os.path.join(args.out_dir, "iith_campus_life_5000.csv"), aug)

    print("\nsummary")
    for label, s in [("base (500)", compute_stats(base)), ("augmented (5000)", compute_stats(aug))]:
        print(f"  {label:18s}  n={s['n']}  mean={s['mean']:.2f}  "
              f"std={s['std']:.2f}  min={s['min']:.2f}  max={s['max']:.2f}")


if __name__ == "__main__":
    main()