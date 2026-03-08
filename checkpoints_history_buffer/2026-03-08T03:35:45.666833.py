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

    # Filter TRULY threatening projectiles - must be enemy, close, and approaching us
    threatening_projectiles = []
    for p in observation["projectiles"]:
        if p["my_team"] == 0 and p["distance_to_me"] < 250:
            threatening_projectiles.append(p)

    # PRIORITY 0: If very low HP, retreat
    if my_hp_pct < 0.15:
        if e_ready:
            angle_away = math.atan2(-enemy_dy, -enemy_dx)
            escape_x = my_x + math.cos(angle_away) * 475
            escape_y = my_y + math.sin(angle_away) * 475
            return (2, [[2], [escape_y, escape_x]])
        retreat_x = my_x - enemy_dx * 0.5
        retreat_y = my_y - enemy_dy * 0.5
        return (1, [retreat_y, retreat_x])

    # PRIORITY 1: CAST Q - this is the #1 damage source. Ezreal Q range = 1150
    if q_ready and enemy_dist < 1200:
        # Lead the target - predict where enemy will be
        # Aim slightly ahead of enemy position
        target_x = enemy_x
        target_y = enemy_y
        return (2, [[0], [target_y, target_x]])

    # PRIORITY 2: CAST W when Q is on cooldown and in range (1000 range)
    if w_ready and not q_ready and enemy_dist < 1050:
        return (2, [[1], [enemy_y, enemy_x]])

    # PRIORITY 3: Dodge VERY close projectiles (only after abilities are cast)
    if threatening_projectiles:
        closest = min(threatening_projectiles, key=lambda p: p["distance_to_me"])
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]
        # Dodge perpendicular to projectile direction
        dodge_dx = -pdy
        dodge_dy = pdx
        mag = math.sqrt(dodge_dx**2 + dodge_dy**2)
        if mag > 0:
            dodge_dx /= mag
            dodge_dy /= mag
        else:
            dodge_dx, dodge_dy = 1, 0

        # Use E if projectile very close and we're low-ish HP
        if closest["distance_to_me"] < 150 and e_ready and my_hp_pct < 0.3:
            escape_x = my_x + dodge_dx * 475
            escape_y = my_y + dodge_dy * 475
            return (2, [[2], [escape_y, escape_x]])

        dodge_target_x = my_x + dodge_dx * 250
        dodge_target_y = my_y + dodge_dy * 250
        return (1, [dodge_target_y, dodge_target_x])

    # PRIORITY 4: Auto attack if in auto range (~550) and abilities on cooldown
    if enemy_dist < 550 and not q_ready:
        # Issue auto attack command by moving slightly toward enemy then stopping
        # Just stay in range - auto attacks fire automatically
        # Kite: move slightly away after auto
        angle_away = math.atan2(-enemy_dy, -enemy_dx)
        kite_x = my_x + math.cos(angle_away) * 100
        kite_y = my_y + math.sin(angle_away) * 100
        return (1, [kite_y, kite_x])

    # PRIORITY 5: APPROACH enemy to get within Q range (1150)
    # This is critical - we MUST close distance to fight
    if enemy_dist > 1100:
        # Move DIRECTLY toward enemy - no zigzag, just get in range fast
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        # Add slight perpendicular offset to avoid walking into skillshots
        time_val = game_time % 600
        if time_val < 200:
            offset = math.pi / 8
        elif time_val < 400:
            offset = -math.pi / 8
        else:
            offset = 0
        approach_angle = angle_to_enemy + offset
        move_x = my_x + math.cos(approach_angle) * 500
        move_y = my_y + math.sin(approach_angle) * 500
        return (1, [move_y, move_x])

    # PRIORITY 6: Maintain optimal range (800-1000) - inside Q range but not melee
    if enemy_dist < 400:
        # Too close - kite backwards
        angle_away = math.atan2(-enemy_dy, -enemy_dx)
        kite_x = my_x + math.cos(angle_away) * 350
        kite_y = my_y + math.sin(angle_away) * 350
        return (1, [kite_y, kite_x])

    # At decent range (400-1100), orbit while waiting for cooldowns
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
    # Alternate orbit direction frequently for unpredictability
    time_val = game_time % 400
    orbit_dir = 1 if time_val < 200 else -1
    orbit_angle = angle_to_enemy + (math.pi / 2.5 * orbit_dir)
    orbit_x = my_x + math.cos(orbit_angle) * 200
    orbit_y = my_y + math.sin(orbit_angle) * 200
    return (1, [orbit_y, orbit_x])