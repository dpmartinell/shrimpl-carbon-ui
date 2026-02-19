
from estimation.estimator import EstimatorInputs, estimate
from estimation.Water_exchange_estimation import PumpingModelInputs
from estimation.Aeration_energy import AerationInputs
from estimation.LULUC import LulucInputs
from estimation.Carbon_Sequestration import SequestrationInputs
from estimation.otherghg import PondGHGInputs

inputs = EstimatorInputs(
    harvested_shrimp_kg=10000,
    period="cycle",
    cycle_days=90,
    boundary="A",
    pumping=PumpingModelInputs(volume_m3=50000, pipe_length_m=200, static_head_m=2, energy_source="grid", grid_country="Ecuador"),
    aeration=AerationInputs(total_aeration_hp=50, operating_hours=90*12, energy_source="grid", grid_country="Ecuador"),
    total_feed_kg=15000,
    seed_thousand_pl=2000,
    luluc=LulucInputs(soil_type="mangrove", area_ha=5, farm_age_years=2, amortization_years=20),
    sequestration=SequestrationInputs(vegetation_type="Mangroves", area_ha=1),
    pond_ghg=PondGHGInputs(pond_area_m2=50000, system_type="semi_intensive"),
)

print(estimate(inputs))
