# Shrimpl Carbon Footprint Estimation (Methodology-aligned)

This folder contains the ISO 14064–aligned, **cycle-based** carbon footprint estimator.

## Key rule
- The estimator is **cycle-based**. A cycle is defined by `cycle_days` (number of days).

## Install (from repo root)
```bash
pip install -r requirements.txt  # if you have one
```

## Run the included example
```bash
python example_run.py
```

## Programmatic use
```python
from estimation.estimator import EstimatorInputs, estimate
from estimation.Water_exchange_estimation import PumpingModelInputs
from estimation.Aeration_energy import AerationInputs

inputs = EstimatorInputs(
    harvested_shrimp_kg=10000,
    period="cycle",
    cycle_days=90,
    total_feed_kg=15000,
    pumping=PumpingModelInputs(
        area_m2=10000,
        depth_m=1.2,
        exchange_rate_fraction_per_day=0.1,
        pipe_diameter_m=0.3,
        pipe_length_m=50,
        pump_efficiency=0.7,
        motor_efficiency=0.9,
        total_dynamic_head_m=3.0,
        energy_source="grid",
        grid_country="Mexico",
    ),
    aeration=AerationInputs(
        total_aeration_hp=20,
        hours_per_day=18,
        motor_efficiency=0.9,
        blower_efficiency=0.8,
        energy_source="grid",
        grid_country="Mexico",
        period="cycle",
        cycle_days=90,
    ),
)

result = estimate(inputs)
print(result.intensity_kgco2e_per_kg_shrimp)
```

## Output
The estimator returns:
- total emissions (kgCO2e) for the period
- intensity (kgCO2e/kg shrimp)
- a breakdown by component

