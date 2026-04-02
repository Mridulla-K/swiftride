from app.surge import compute_multiplier, calculate_fare

def test_surge_at_zero_drivers():
    # Demand 5, Supply 0
    multiplier = compute_multiplier(5, 0)
    assert multiplier == 3.0  # Cap (5/1 = 5.0, capped at 3.0)

def test_surge_equal_supply_demand():
    # Demand 5, Supply 5
    multiplier = compute_multiplier(5, 5)
    assert multiplier == 1.0  # round(5/5, 1) = 1.0

def test_surge_3x_cap():
    # Demand 100, Supply 1
    multiplier = compute_multiplier(100, 1)
    assert multiplier == 3.0  # round(100/1, 1) = 100.0, capped at 3.0

def test_fare_calculation():
    distance_km = 10.0
    surge_multiplier = 2.0
    
    base, surge, total = calculate_fare(distance_km, surge_multiplier)
    
    expected_base = 2.50 + (10.0 * 1.20)  # 14.50
    expected_total = round(expected_base * 2.0, 2)  # 29.0
    
    assert base == expected_base
    assert surge == surge_multiplier
    assert total == expected_total

def test_min_fare_floor():
    distance_km = 0.5
    surge_multiplier = 1.0
    
    base, surge, total = calculate_fare(distance_km, surge_multiplier)
    
    # base = 2.50 + 0.6 = 3.10
    # total = 3.10 * 1.0 = 3.10
    # min_fare = 5.00
    
    assert total == 5.00
