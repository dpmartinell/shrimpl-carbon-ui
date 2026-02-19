# ==========================
# Parameters.py
# ==========================

# ==========================
# General Constants
# ==========================
general_constants = {
    "water_density_kg_m3": 1025,         # Density of water (kg/m³) for seawater
    "g": 9.81,                           # Gravitational acceleration (m/s²)
    "friction_factor": 0.02,             # Friction factor for the pipe
    "diesel_energy_content_mj_l": 35.8,  # Energy content of diesel (MJ/L)
    "petrol_energy_content_mj_l": 34.2,  # Energy content of petrol (MJ/L)
    "mj_to_kwh": 3.6                     # Conversion factor from MJ to kWh
}

# ==========================
# CO2e Emissions Parameters
# ==========================
co2_emissions = {
    "per_kwh": {  # Emissions per kWh by country (gCO2e/kWh)
        "Mexico": 0.415,
        "Ecuador": 0.206,
        "Indonesia": 0.654,
        "Thailand": 0.491,
        "Vietnam": 0.504,
        "Bangladesh": 0.621,
        "Brazil": 0.1,
        "Guatemala": 0.209,
        "El Salvador": 0.196,
        "Honduras": 0.279,
        "Philippines": 0.546,
        "India": 0.621,
        "China": 0.636
    },
    "per_liter": {  # Emissions per liter of diesel or petrol (kgCO2e/L)
        "diesel": 2.640,
        "petrol": 2.392
    }
}

# ==========================
# Farm Parameters
# ==========================
farm_parameters = {
    "volume_m3": 2800000,                 # Total water volume in m³
    "pipe_length_m": 5000,                # Pipe length in meters
    "pipe_diameter_m": 2.5,              # Pipe diameter in meters
    "static_head_m": 15,                 # Static head in meters
    "energy_source": "Vietnam",          # Pumping energy source
    "aeration_energy_source": "Vietnam", # Aeration energy source
    "country": "Mexico",                 # Farm location
    "pump_efficiency": 0.7,              # Pump efficiency
    "soil_type": "tropical",             # Soil type for LULUC
    "farm_age": 3,                       # Farm age in years
    "temperature": 28,                   # Temperature in Celsius
    "salinity": 15,                      # Salinity in ppt
    "aerator_hp": 15,                    # Aerator horsepower
    "aeration_hours_per_day": 12,        # Hours of aeration per day
    "feed_input": 80,                    # Feed input in kg/day
    "waste_percentage": 0.25,            # Percentage of feed converted to waste
}

# ==========================
# Pond Parameters
# ==========================
pond_parameters = {
    "pond_area": 1.0,  # hectares
    "pond_depth": 2.5,  # meters
    "wind_speed": 2.5,  # m/s
    "chlorophyll_concentration": 7.0,  # µg/L
    "temp": 32,  # Celsius
    "salinity": 20,  # ppt
    "feed_input": 45,  # kg/day
    "waste_percentage": 0.15,  # 15%
    "aerator_hp": 26,  # horsepower
    "aeration_hours_per_day": 24,  # hours
    "aeration_active": True,  # Boolean toggle for aeration
    "OM_concentration_mg_L": 9,  # Organic matter concentration (mg/L)
    "total_aeration_hp": 150,
    "num_aerators": 10,  # Number of aerators
    "cycle_length_days": 90, # Cycle length in days
    "aeration_energy_source": "diesel", # Energy source for aeration
    "feed_input": 59.61,  # kg/day (Feed input)
    "fcr": 1.5, # Feed Conversion Ratio
    "shrimp_biomass": 1000,

    }



# ==========================
# Aeration Parameters
# ==========================
aeration_parameters = {
    "motor_efficiency": 0.8,  # Motor efficiency
    "blower_efficiency": 0.7,  # Blower efficiency
    "energy_content_diesel_mj_l": 35.8,  # Energy content of diesel (MJ/L)
    "energy_content_petrol_mj_l": 34.2,  # Energy content of petrol (MJ/L)
    "energy_source": "diesel",  # Energy source ('grid', 'diesel', 'petrol')
}

# ==========================
# Feed Emissions Parameters
# ==========================
feed_emissions_parameters = {
    "wild_fish_percentage": 7,  # Percentage of wild fish in feed
    "energy_source": "grid",  # Energy source ('grid', 'diesel', 'petrol')
    "emission_factor_per_kg_feed": 2.5,  # Example emission factor in kg CO2e per kg of feed
}


# ==========================
# Kcap Parameters
# ==========================
kcap_parameters = {
    "oxygen_saturation": {"salinity_factor": 0.03},
    "liquid_film_coefficient": {"base_coefficient": 1.1},
    "oxygen_production": {
        "light_factor": 1.3,
        "production_rate_constant": 5,
    },
    "organic_matter": {"oxygen_demand_per_kg": 1.3},
    "oxygen_consumption": {
        "base_consumption_rate": 3000,  # mg/day per kg shrimp
        "temp_threshold": 35,  # Celsius
        "salinity_threshold": 30,  # ppt
        "increase_factor": 1.5,
    },
    "aerator": {"oxygenation_per_hp": 300000},  # mg/hr per HP
}

# ==========================
# Other GHGs Parameters
# ==========================
other_ghgs_parameters = {
    "GWP_CH4": 28,                            # GWP of Methane
    "GWP_N2O": 298,                           # GWP of Nitrous Oxide
    "EF_CH4": 0.25,                           # CH4 emission factor (g CH4/g OC)
    "EF_N2O": 0.01,                           # N2O emission factor (g N2O/g N)
    "OM_concentration_mg_L": 20,              # Organic matter concentration (mg/L)
}

# ==========================
# LULUC Parameters
# ==========================
luluc_parameters = {
    "carbon_to_co2_factor": 3.67,             # Conversion factor from carbon to CO2
    "soc_values_by_soil_type": {
        "desert": [10, 8, 6],
        "tropical": [70, 55, 40],
        "temperate": [85, 70, 50],
        "boreal": [200, 150, 100],
        "peatland": [500, 400, 300],
        "mangrove": [300, 250, 200],
    },
    "immediate_release_fraction": 0.7,        # Fraction of carbon released immediately (if farm age <= 5)
    "years": 20                               # Period for emissions calculation
}

# ==========================
# Carbon Sequestration Parameters
# ==========================
carbon_sequestration_parameters = {
    "CARBON_TO_CO2_FACTOR": 3.67,
    "AGB_FACTORS": {
        "Mangroves": 150,
        "Tropical Forests": 120,
        "Grasslands": 40,
        "Wetlands": 60,
        "Temperate Forests": 100,
        "Peatlands": 70,
    },
    "ROOT_TO_SHOOT_RATIOS": {
        "Mangroves": 0.45,
        "Tropical Forests": 0.24,
        "Grasslands": 0.2,
        "Wetlands": 0.5,
        "Temperate Forests": 0.25,
        "Peatlands": 0.3,
    },
    "GROWTH_RATES": {
        "Mangroves": 0.015,
        "Tropical Forests": 0.015,
        "Grasslands": 0.03,
        "Wetlands": 0.02,
        "Temperate Forests": 0.02,
        "Peatlands": 0.01,
    },
    "AREA": 0,                              # Area in hectares
    "VEGETATION_TYPE": "Mangroves"
}


"""
References

1. Desert Soils:

Main Reference: Lal, R. (2004). Soil carbon sequestration impacts on global climate change and food security. Science, 304(5677), 1623-1627.
Additional References:
Batjes, N. H. (1996). Total carbon and nitrogen in the soils of the world. European Journal of Soil Science, 47(2), 151-163.
Eswaran, H., Van Den Berg, E., & Reich, P. (1993). Organic carbon in soils of the world. Soil Science Society of America Journal, 57(1), 192-194.

2. Tropical Soils:

Main Reference: Don, A., Schumacher, J., & Freibauer, A. (2011). Impact of tropical land-use change on soil organic carbon stocks–a meta-analysis. Global Change Biology, 17(4), 1658-1670.
Additional References:
IPCC. (2006). Guidelines for National Greenhouse Gas Inventories, Volume 4: Agriculture, Forestry and Other Land Use.
Batjes, N. H. (1996). Total carbon and nitrogen in the soils of the world. European Journal of Soil Science, 47(2), 151-163.

3. Temperate Soils:

Main Reference: Smith, P., et al. (2008). Greenhouse gas mitigation in agriculture. Philosophical Transactions of the Royal Society B: Biological Sciences, 363(1492), 789-813.
Additional References:
Poeplau, C., & Don, A. (2015). Carbon sequestration in agricultural soils via cultivation of cover crops–A meta-analysis. Agriculture, Ecosystems & Environment, 200, 33-41.

4. Boreal Soils:

Main Reference: Tarnocai, C., et al. (2009). Soil organic carbon pools in the northern circumpolar permafrost region. Global Biogeochemical Cycles, 23(2).
Additional References:
Hugelius, G., et al. (2014). Estimated stocks of circumpolar permafrost carbon with quantified uncertainty ranges and identified data gaps. Biogeosciences, 11(23), 6573-6593.

5. Peatlands:

Main Reference: Joosten, H. (2010). The global peatland CO2 picture: Peatland status and drainage-related emissions in all countries of the world. Wetlands International.
Additional References:
Gorham, E. (1991). Northern peatlands: role in the carbon cycle and probable responses to climatic warming. Ecological Applications, 1(2), 182-195.

6. Mangrove Soils:

Main Reference: Donato, D. C., Kauffman, J. B., Murdiyarso, D., Kurnianto, S., Stidham, M., & Kanninen, M. (2011). Mangroves among the most carbon-rich forests in the tropics. Nature Geoscience, 4(5), 293-297.
Additional References:
Alongi, D. M. (2014). Carbon cycling and storage in mangrove forests. Annual Review of Marine Science, 6, 195-219.
Kauffman, J. B., & Donato, D. C. (2012). Protocols for the measurement, monitoring, and reporting of structure, biomass, and carbon stocks in mangrove forests. Center for International Forestry Research.


Grid emission factors

International Energy Agency (IEA) - Country-specific electricity grid emissions data (2022).

European Environment Agency (EEA) - CO2 emissions from electricity generation.

Global Carbon Atlas - Emissions data by country and sector.

CFE (Comisión Federal de Electricidad, Mexico) - Electricity generation emissions reports.

National energy agency reports (Brazil, Guatemala, El Salvador).



"""


