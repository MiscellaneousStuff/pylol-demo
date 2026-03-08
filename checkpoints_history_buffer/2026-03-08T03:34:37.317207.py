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

    # Filter projectiles: only enemy projectiles that are CLOSE and MOVING TOWARD us
    threatening_projectiles = []
    for p in observation["projectiles"]:
        if p["my_team"] == 0 and p["distance_to_me"] < 350:
            # Check if projectile is moving toward us using dx/dy direction
            # If dx_to_me and dy_to_me are both small and getting smaller, it's approaching
            # A simple heuristic: if distance < 350, it's threatening enough to dodge
            threatening_projectiles.append(p)

    # Priority 0: CAST Q whenever ready and enemy is in range - THIS IS CRITICAL
    # Ezreal Q range is ~1150, cast it aggressively
    if q_ready and enemy_dist < 1100:
        # Lead the target slightly - aim at enemy position
        # Predict enemy movement: enemy is at (enemy_x, enemy_y)
        # Simple lead: aim slightly ahead in the direction they might be moving
        target_x = enemy_x
        target_y = enemy_y
        return (2, [[0], [target_y, target_x]])

    # Priority 1: Cast W if Q is on cooldown and enemy in range
    if w_ready and enemy_dist < 950 and not q_ready:
        return (2, [[1], [enemy_y, enemy_x]])

    # Priority 2: Dodge VERY close threatening projectiles (only after casting)
    if threatening_projectiles:
        closest = min(threatening_projectiles, key=lambda p: p["distance_to_me"])
        if closest["distance_to_me"] < 300:
            pdx = closest["dx_to_me"]
            pdy = closest["dy_to_me"]
            # Dodge perpendicular to direction from us to projectile
            dodge_dx = -pdy
            dodge_dy = pdx
            mag = math.sqrt(dodge_dx**2 + dodge_dy**2)
            if mag > 0:
                dodge_dx /= mag
                dodge_dy /= mag
            else:
                dodge_dx, dodge_dy = 1, 0

            # Use E to escape if very low HP and projectile very close
            if closest["distance_to_me"] < 200 and e_ready and my_hp_pct < 0.25:
                escape_x = my_x + dodge_dx * 475
                escape_y = my_y + dodge_dy * 475
                return (2, [[2], [escape_y, escape_x]])

            dodge_target_x = my_x + dodge_dx * 250
            dodge_target_y = my_y + dodge_dy * 250
            return (1, [dodge_target_y, dodge_target_x])

    # Priority 3: If very low HP, retreat using E if available
    if my_hp_pct < 0.15:
        if e_ready:
            # E away from enemy
            angle_away = math.atan2(-enemy_dy, -enemy_dx)
            escape_x = my_x + math.cos(angle_away) * 475
            escape_y = my_y + math.sin(angle_away) * 475
            return (2, [[2], [escape_y, escape_x]])
        # Run away from enemy
        retreat_x = my_x - enemy_dx * 0.5
        retreat_y = my_y - enemy_dy * 0.5
        return (1, [retreat_y, retreat_x])

    # Priority 4: Auto attack if in range (~550) and abilities on cooldown
    if enemy_dist < 550 and not q_ready:
        # Move to auto attack range - stay at edge
        return (0, None)  # auto attacks happen automatically in range

    # Priority 5: Approach enemy to get within Q range
    # Optimal range for Ezreal: ~800-950 (inside Q range, outside melee)
    optimal_range = 850

    if enemy_dist > 1100:
        # Too far - approach aggressively with zigzag
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        # Zigzag based on game time to be unpredictable
        time_val = game_time % 400
        zigzag = math.pi / 12 if time_val < 200 else -math.pi / 12
        approach_angle = angle_to_enemy + zigzag
        move_x = my_x + math.cos(approach_angle) * 450
        move_y = my_y + math.sin(approach_angle) * 450
        return (1, [move_y, move_x])

    if enemy_dist < 400:
        # Too close - kite backwards
        angle_away = math.atan2(-enemy_dy, -enemy_dx)
        kite_x = my_x + math.cos(angle_away) * 300
        kite_y = my_y + math.sin(angle_away) * 300
        return (1, [kite_y, kite_x])

    # At good range (400-1100) - orbit to dodge while waiting for cooldowns
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
    # Alternate orbit direction more frequently for better dodging
    time_val = game_time % 500
    orbit_dir = 1 if time_val < 250 else -1
    orbit_angle = angle_to_enemy + (math.pi / 2 * orbit_dir)
    orbit_x = my_x + math.cos(orbit_angle) * 200
    orbit_y = my_y + math.sin(orbit_angle) * 200
    return (1, [orbit_y, orbit_x])