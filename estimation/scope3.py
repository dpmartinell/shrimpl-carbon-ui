# Scope 3 Categories for Shrimp Aquaculture and Feed Mills

scope_3_categories = {
    "Upstream": {
        "Purchased Goods and Services": {
            "Shrimp Aquaculture": [
                "Procurement of post-larvae (PL) shrimp",
                "Chemicals and medicines (e.g., antibiotics, lime, probiotics)",
                "Energy inputs (e.g., diesel, petrol, electricity)"
            ],
            "Feed Mills": [
                "Raw materials for feed production (e.g., fishmeal, soy, corn)",
                "Packaging materials for feed distribution"
            ]
        },
        "Fuel- and Energy-Related Activities": [
            "Extraction and refining of diesel/petrol used in farm machinery or feed production",
            "Generation and transmission of electricity for aerators, pumps, and mills"
        ],
        "Upstream Transportation and Distribution": [
            "Transporting feed to aquaculture farms",
            "Transporting raw materials to feed mills or aquaculture facilities"
        ],
        "Waste Generated in Operations": {
            "Shrimp Aquaculture": [
                "Disposal of pond sludge",
                "Waste feed and mortalities"
            ],
            "Feed Mills": [
                "Packaging waste",
                "Process residues",
                "Rejected feed batches"
            ]
        },
        "Business Travel": [
            "Travel by employees for operational oversight, farm visits, or supplier audits"
        ],
        "Employee Commuting": [
            "Worker commuting to feed mills or aquaculture farms"
        ],
        "Upstream Leased Assets": [
            "Leased facilities or equipment (e.g., feed storage warehouses, processing plants)"
        ]
    },
    "Downstream": {
        "Downstream Transportation and Distribution": [
            "Distributing shrimp to processing facilities or export markets",
            "Transporting feed to aquaculture farms from feed mills"
        ],
        "Processing of Sold Products": [
            "Processing shrimp into final products (e.g., freezing, cooking, packaging)"
        ],
        "End-of-Life Treatment of Sold Products": [
            "Waste treatment of shrimp packaging materials",
            "Waste treatment of feed packaging materials"
        ],
        "Use of Sold Products": [
            "Feed utilization by shrimp farmers affecting pond management and GHG emissions"
        ]
    }
}

# Function to display Scope 3 categories in a readable format
def display_scope_3_categories(categories):
    for category, subcategories in categories.items():
        print(f"{category}:")
        if isinstance(subcategories, dict):
            for subcategory, items in subcategories.items():
                print(f"  {subcategory}:")
                if isinstance(items, list):
                    for item in items:
                        print(f"    - {item}")
                elif isinstance(items, dict):
                    for key, value in items.items():
                        print(f"    {key}:")
                        for sub_item in value:
                            print(f"      - {sub_item}")
        elif isinstance(subcategories, list):
            for item in subcategories:
                print(f"  - {item}")
        print()

# Display the categories
if __name__ == "__main__":
    display_scope_3_categories(scope_3_categories)
