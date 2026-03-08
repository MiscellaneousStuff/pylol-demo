def act(self, observation):
    import math

    my_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 1)
    enemy_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 0)

    my_hp_pct = my_champ["current_hp"] / max(my_champ["max_hp"], 1)
    enemy_hp_pct = enemy_champ["current_hp"] / max(enemy_champ["max_hp"], 1)
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

    # Only consider truly threatening enemy projectiles (very close)
    threatening = []
    for p in observation["projectiles"]:
        if p["my_team"] == 0 and p["distance_to_me"] < 300:
            threatening.append(p)

    # PRIORITY 1: Use E aggressively to close gap and land point-blank abilities
    # E into close range then spam Q/W at point blank where they can't dodge
    if e_ready and enemy_dist > 500 and enemy_dist < 1200 and my_hp_pct > 0.3:
        # E toward enemy to get close for guaranteed hits
        # Aim E to land about 300 units from enemy
        angle_to = math.atan2(enemy_dy, enemy_dx)
        # E has 475 range, position to land close to enemy
        e_target_x = enemy_x - math.cos(angle_to) * 250
        e_target_y = enemy_y - math.sin(angle_to) * 250
        return (2, [[2], [e_target_y, e_target_x]])

    # PRIORITY 2: SPAM Q at enemy - this is the #1 source of damage
    # Lead the shot based on enemy's likely movement direction
    if enemy_dist < 1100 and q_ready:
        # Lead the target - predict movement
        # Use angle variation to spread shots and increase hit chance
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        # Add small random-ish lead based on game time to vary aim
        # Alternate between leading left and right of enemy
        lead_offset = math.sin(game_time * 0.013) * 150
        lead_x = enemy_x + math.cos(angle_to_enemy + math.pi/2) * lead_offset
        lead_y = enemy_y + math.sin(angle_to_enemy + math.pi/2) * lead_offset
        return (2, [[0], [lead_y, lead_x]])

    # PRIORITY 3: Cast W for mark damage - slightly wider hitbox
    if enemy_dist < 1000 and w_ready:
        # Aim W with slight lead in opposite direction of Q lead
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        lead_offset = math.cos(game_time * 0.011) * 120
        lead_x = enemy_x + math.cos(angle_to_enemy + math.pi/2) * lead_offset
        lead_y = enemy_y + math.sin(angle_to_enemy + math.pi/2) * lead_offset
        return (2, [[1], [lead_y, lead_x]])

    # PRIORITY 4: Use R frequently - wide beam is harder to dodge
    if r_ready and enemy_dist < 2000:
        return (2, [[3], [enemy_y, enemy_x]])

    # PRIORITY 5: Dodge ONLY very close threatening projectiles
    if threatening:
        closest = min(threatening, key=lambda p: p["distance_to_me"])
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]
        # Perpendicular dodge
        perp_x = -pdy
        perp_y = pdx
        mag = math.sqrt(perp_x ** 2 + perp_y ** 2)
        if mag > 0:
            perp_x /= mag
            perp_y /= mag
        dodge_x = my_x + perp_x * 280
        dodge_y = my_y + perp_y * 280
        return (1, [dodge_y, dodge_x])

    # PRIORITY 6: Positioning - stay in Q range with unpredictable movement
    if enemy_dist < 300:
        # Too close, kite back
        angle_away = math.atan2(-enemy_dy, -enemy_dx)
        mx = my_x + math.cos(angle_away) * 350
        my = my_y + math.sin(angle_away) * 350
        return (1, [my, mx])

    if enemy_dist > 1050:
        # Too far, close the gap with juking approach
        angle_to = math.atan2(enemy_dy, enemy_dx)
        # Use irregular juke pattern using prime-based timing
        juke = math.sin(game_time * 0.007) * math.pi / 3.5
        move_angle = angle_to + juke
        mx = my_x + math.cos(move_angle) * 350
        my = my_y + math.sin(move_angle) * 350
        return (1, [my, mx])

    # In optimal range: fast irregular juking to avoid predictability
    angle_to = math.atan2(enemy_dy, enemy_dx)
    # Use multiple sine waves for unpredictable movement
    t = game_time
    juke1 = math.sin(t * 0.011) * 0.7
    juke2 = math.sin(t * 0.007 + 2.1) * 0.5
    juke3 = math.sin(t * 0.019 + 0.7) * 0.3
    combined_juke = juke1 + juke2 + juke3  # ranges roughly -1.5 to 1.5
    orbit_angle = angle_to + (math.pi / 2) * combined_juke
    mx = my_x + math.cos(orbit_angle) * 250
    my = my_y + math.sin(orbit_angle) * 250
    return (1, [my, mx])