def act(self, observation):
    import math

    my_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 1)
    enemy_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 0)

    my_hp_pct = my_champ["current_hp"] / max(my_champ["max_hp"], 1)
    enemy_hp_pct = enemy_champ["current_hp"] / max(enemy_champ["max_hp"], 1)
    my_mp_pct = my_champ["current_mp"] / max(my_champ["max_mp"], 1)
    my_x = my_champ["position"]["X"]
    my_y = my_champ["position"]["Y"]
    enemy_dx = enemy_champ["dx_to_me"]
    enemy_dy = enemy_champ["dy_to_me"]
    enemy_dist = enemy_champ["distance_to_me"]
    enemy_x = enemy_champ["position"]["X"]
    enemy_y = enemy_champ["position"]["Y"]

    q_ready = my_champ["q_cooldown"] == 0
    w_ready = my_champ["w_cooldown"] == 0
    e_ready = my_champ["e_cooldown"] == 0
    r_ready = my_champ["r_cooldown"] == 0

    # Priority 1: Dodge incoming enemy projectiles
    nearby_projectiles = [p for p in observation["projectiles"]
                         if p["my_team"] == 0 and p["distance_to_me"] < 900]

    if nearby_projectiles:
        # Find closest projectile
        closest = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]
        # Dodge perpendicular to projectile direction
        # The projectile direction is roughly toward us, so perpendicular is (-dy, dx)
        dodge_dx = -pdy
        dodge_dy = pdx
        mag = math.sqrt(dodge_dx**2 + dodge_dy**2)
        if mag > 0:
            dodge_dx /= mag
            dodge_dy /= mag
        else:
            dodge_dx, dodge_dy = 1, 0
        
        # Use E (Arcane Shift) if very close projectile and low HP
        if closest["distance_to_me"] < 400 and e_ready and my_hp_pct < 0.4:
            escape_x = my_x + dodge_dx * 475
            escape_y = my_y + dodge_dy * 475
            return (2, [[2], [escape_y, escape_x]])
        
        # Otherwise dodge by moving perpendicular
        dodge_target_x = my_x + dodge_dx * 300
        dodge_target_y = my_y + dodge_dy * 300
        return (1, [dodge_target_y, dodge_target_x])

    # Priority 2: Cast Q at enemy if in range and ready (Q range ~1150)
    if q_ready and enemy_dist < 1100 and enemy_dist > 300:
        # Lead the target slightly - aim at enemy position
        return (2, [[0], [enemy_y, enemy_x]])

    # Priority 3: Cast W at enemy if in range
    if w_ready and enemy_dist < 1000 and enemy_dist > 300:
        return (2, [[1], [enemy_y, enemy_x]])

    # Priority 4: Maintain optimal distance (~800-900 units) for safe Q poke
    optimal_range = 850
    
    if my_hp_pct < 0.25:
        # Low HP - retreat toward base
        retreat_x = my_x - enemy_dx * 0.5
        retreat_y = my_y - enemy_dy * 0.5
        return (1, [retreat_y, retreat_x])
    
    if enemy_dist < 500:
        # Too close, kite backwards
        retreat_x = my_x - enemy_dx * 0.6
        retreat_y = my_y - enemy_dy * 0.6
        return (1, [retreat_y, retreat_x])
    
    if enemy_dist > optimal_range + 200:
        # Too far, move closer but at an angle to be harder to hit
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        # Approach at ~30 degree angle (zigzag)
        time_offset = observation["game_time"] % 1000
        zigzag = math.pi / 6 if time_offset < 500 else -math.pi / 6
        approach_angle = angle_to_enemy + zigzag
        move_x = my_x + math.cos(approach_angle) * 300
        move_y = my_y + math.sin(approach_angle) * 300
        return (1, [move_y, move_x])
    
    # At optimal range - orbit/strafe to make enemy Q harder to land
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
    time_offset = observation["game_time"] % 800
    orbit_dir = 1 if time_offset < 400 else -1
    orbit_angle = angle_to_enemy + (math.pi / 2 * orbit_dir)
    orbit_x = my_x + math.cos(orbit_angle) * 250
    orbit_y = my_y + math.sin(orbit_angle) * 250
    return (1, [orbit_y, orbit_x])