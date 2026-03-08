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

    game_time = observation["game_time"]

    # Filter projectiles: only dodge ones that are CLOSE and actually threatening
    # A projectile is threatening if it's close (< 500) and moving toward us
    nearby_projectiles = []
    for p in observation["projectiles"]:
        if p["my_team"] == 0 and p["distance_to_me"] < 500:
            # Only consider projectiles that are reasonably close
            nearby_projectiles.append(p)

    # Priority 1: Dodge VERY close enemy projectiles
    if nearby_projectiles:
        closest = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        if closest["distance_to_me"] < 400:
            pdx = closest["dx_to_me"]
            pdy = closest["dy_to_me"]
            # Dodge perpendicular to the direction FROM us TO projectile
            dodge_dx = -pdy
            dodge_dy = pdx
            mag = math.sqrt(dodge_dx**2 + dodge_dy**2)
            if mag > 0:
                dodge_dx /= mag
                dodge_dy /= mag
            else:
                dodge_dx, dodge_dy = 1, 0

            # Use E to escape if very close and low HP
            if closest["distance_to_me"] < 250 and e_ready and my_hp_pct < 0.35:
                escape_x = my_x + dodge_dx * 475
                escape_y = my_y + dodge_dy * 475
                return (2, [[2], [escape_y, escape_x]])

            dodge_target_x = my_x + dodge_dx * 250
            dodge_target_y = my_y + dodge_dy * 250
            return (1, [dodge_target_y, dodge_target_x])

    # Priority 2: If very low HP, retreat
    if my_hp_pct < 0.15:
        # Run away from enemy toward our base (lower coordinates for blue side)
        retreat_x = my_x - enemy_dx * 0.5
        retreat_y = my_y - enemy_dy * 0.5
        return (1, [retreat_y, retreat_x])

    # Priority 3: Cast Q at enemy if in range (~1150 range) - THIS IS THE PRIMARY DAMAGE SOURCE
    if q_ready and enemy_dist < 1100 and enemy_dist > 200:
        # Lead the target - aim slightly ahead of enemy position
        # Enemy is moving, so predict a bit
        return (2, [[0], [enemy_y, enemy_x]])

    # Priority 4: Cast W at enemy if in range (~1000 range)
    if w_ready and enemy_dist < 950 and enemy_dist > 200:
        return (2, [[1], [enemy_y, enemy_x]])

    # Priority 5: Auto attack if in range (~550)
    if enemy_dist < 550 and enemy_dist > 100:
        return (2, [[0], [enemy_y, enemy_x]]) if q_ready else (0, None)

    # Priority 6: Approach enemy to get within Q range
    # We MUST close distance to fight - optimal fighting range is ~800-950
    optimal_range = 900

    if enemy_dist > optimal_range + 100:
        # Move toward enemy with slight zigzag to avoid being predictable
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        # Small zigzag offset based on game time
        time_val = game_time % 600
        zigzag = math.pi / 10 if time_val < 300 else -math.pi / 10
        approach_angle = angle_to_enemy + zigzag
        # Move aggressively toward enemy - larger step size
        move_x = my_x + math.cos(approach_angle) * 400
        move_y = my_y + math.sin(approach_angle) * 400
        return (1, [move_y, move_x])

    if enemy_dist < 450:
        # Too close for Ezreal, kite backwards
        angle_away = math.atan2(-enemy_dy, -enemy_dx)
        kite_x = my_x + math.cos(angle_away) * 300
        kite_y = my_y + math.sin(angle_away) * 300
        return (1, [kite_y, kite_x])

    # At good range - orbit to dodge while waiting for cooldowns
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
    time_val = game_time % 700
    orbit_dir = 1 if time_val < 350 else -1
    orbit_angle = angle_to_enemy + (math.pi / 2.5 * orbit_dir)
    orbit_x = my_x + math.cos(orbit_angle) * 200
    orbit_y = my_y + math.sin(orbit_angle) * 200
    return (1, [orbit_y, orbit_x])