def act(self, observation):
    import math # YOU MUST IMPORT THIS MODULE EVERY SINGLE TIME. DO NOT IMPORT ANY OTHER MODULES
    
    print("OBSERVATION:", observation)
    # Get our champion and enemy champion info
    my_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 1)
    enemy_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 0)
    nearby_projectiles = [p for p in observation["projectiles"] 
                         if p["my_team"] == 0 and p["distance_to_me"] < 800]

    # High priority: Dodge enemy skillshots (prevents HP loss which has high negative reward)
    if nearby_projectiles:
        proj = nearby_projectiles[0]
        # Calculate perpendicular dodge direction
        dodge_x = proj["dy_to_me"]
        dodge_y = -proj["dx_to_me"]
        magnitude = (dodge_x**2 + dodge_y**2)**0.5
        if magnitude > 0:
            dodge_x = (dodge_x/magnitude * 200) + my_champ["position"]["X"]
            dodge_y = (dodge_y/magnitude * 200) + my_champ["position"]["Y"]
            return (1, [dodge_y, dodge_x])

    # Offensive opportunities (for kill rewards and HP damage)
    if enemy_champ["distance_to_me"] < 600:
        # Check if we have HP advantage
        my_hp_percent = my_champ["current_hp"] / my_champ["max_hp"]
        enemy_hp_percent = enemy_champ["current_hp"] / enemy_champ["max_hp"]
        
        if my_hp_percent > enemy_hp_percent + 0.2:  # We have significant HP advantage
            # Cast Q if available and in range
            if my_champ["q_cooldown"] == 0:
                return (2, [[0], [enemy_champ["position"]["Y"], enemy_champ["position"]["X"]]])
        else:
            # Maintain safe distance if we don't have HP advantage
            retreat_x = my_champ["position"]["X"] - enemy_champ["dx_to_me"]
            retreat_y = my_champ["position"]["Y"] - enemy_champ["dy_to_me"]
            return (1, [retreat_y, retreat_x])

    # Resource management (MP has moderate reward weight)
    if my_champ["current_mp"] / my_champ["max_mp"] < 0.3:
        # Play conservatively when low on mana
        safe_x = my_champ["position"]["X"] + (enemy_champ["dx_to_me"] * -1.5)
        safe_y = my_champ["position"]["Y"] + (enemy_champ["dy_to_me"] * -1.5)
        return (1, [safe_y, safe_x])

    # Default behavior: Maintain optimal trading range
    optimal_range = 500  # Adjust based on champion
    if enemy_champ["distance_to_me"] > optimal_range:
        # Move closer
        approach_x = my_champ["position"]["X"] + enemy_champ["dx_to_me"] * 0.5
        approach_y = my_champ["position"]["Y"] + enemy_champ["dy_to_me"] * 0.5
        return (1, [approach_y, approach_x])
    else:
        # Orbit around enemy while in range
        orbit_angle = math.atan2(enemy_champ["dy_to_me"], enemy_champ["dx_to_me"])
        orbit_x = enemy_champ["position"]["X"] + math.cos(orbit_angle + math.pi/4) * optimal_range
        orbit_y = enemy_champ["position"]["Y"] + math.sin(orbit_angle + math.pi/4) * optimal_range
        return (1, [orbit_y, orbit_x])