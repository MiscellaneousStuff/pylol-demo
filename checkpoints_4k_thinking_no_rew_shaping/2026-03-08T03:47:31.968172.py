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

    # Identify truly threatening enemy projectiles heading toward us
    threatening = []
    for p in observation["projectiles"]:
        if p["my_team"] == 0:
            dist = p["distance_to_me"]
            # Only consider projectiles that are close enough to be a real threat
            if dist < 500:
                threatening.append(p)

    # PRIORITY 0: Dodge close threatening projectiles FIRST (survival)
    # This prevents the massive HP drops we've been seeing from enemy R
    if threatening:
        closest = min(threatening, key=lambda p: p["distance_to_me"])
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]
        # Move perpendicular to projectile direction
        perp_x = -pdy
        perp_y = pdx
        mag = math.sqrt(perp_x ** 2 + perp_y ** 2)
        if mag > 0:
            perp_x /= mag
            perp_y /= mag

        # Use E to dodge if projectile is very close and E is ready
        if closest["distance_to_me"] < 250 and e_ready:
            e_x = my_x + perp_x * 475
            e_y = my_y + perp_y * 475
            return (2, [[2], [e_y, e_x]])

        dodge_x = my_x + perp_x * 350
        dodge_y = my_y + perp_y * 350
        return (1, [dodge_y, dodge_x])

    # PRIORITY 1: R is GLOBAL range - use it liberally, especially when far away
    # No cooldowns means we can spam R for massive damage while approaching
    if r_ready:
        # Lead the target slightly when far away
        angle_to = math.atan2(enemy_dy, enemy_dx)
        # More lead at longer distances
        lead_amount = min(enemy_dist * 0.1, 300)
        lead_offset = math.sin(game_time * 0.017) * lead_amount
        r_x = enemy_x + math.cos(angle_to + math.pi / 2) * lead_offset
        r_y = enemy_y + math.sin(angle_to + math.pi / 2) * lead_offset
        return (2, [[3], [r_y, r_x]])

    # PRIORITY 2: Q spam when in range (1150 range)
    if q_ready and enemy_dist < 1150:
        angle_to = math.atan2(enemy_dy, enemy_dx)
        # Vary aim to increase hit chance
        lead_offset = math.sin(game_time * 0.013) * 130
        q_x = enemy_x + math.cos(angle_to + math.pi / 2) * lead_offset
        q_y = enemy_y + math.sin(angle_to + math.pi / 2) * lead_offset
        return (2, [[0], [q_y, q_x]])

    # PRIORITY 3: W for mark damage
    if w_ready and enemy_dist < 1000:
        angle_to = math.atan2(enemy_dy, enemy_dx)
        lead_offset = math.cos(game_time * 0.011) * 100
        w_x = enemy_x + math.cos(angle_to + math.pi / 2) * lead_offset
        w_y = enemy_y + math.sin(angle_to + math.pi / 2) * lead_offset
        return (2, [[1], [w_y, w_x]])

    # PRIORITY 4: Use E to close gap when far away
    if e_ready and enemy_dist > 1200 and my_hp_pct > 0.25:
        angle_to = math.atan2(enemy_dy, enemy_dx)
        e_x = my_x + math.cos(angle_to) * 475
        e_y = my_y + math.sin(angle_to) * 475
        return (2, [[2], [e_y, e_x]])

    # PRIORITY 5: Movement/Positioning
    if enemy_dist > 1000:
        # Approach enemy directly but with slight juke to avoid skillshots
        angle_to = math.atan2(enemy_dy, enemy_dx)
        juke = math.sin(game_time * 0.009) * math.pi / 6
        move_angle = angle_to + juke
        mx = my_x + math.cos(move_angle) * 400
        my = my_y + math.sin(move_angle) * 400
        return (1, [my, mx])

    if enemy_dist < 350:
        # Too close, kite back slightly
        angle_away = math.atan2(-enemy_dy, -enemy_dx)
        mx = my_x + math.cos(angle_away) * 350
        my = my_y + math.sin(angle_away) * 350
        return (1, [my, mx])

    # In optimal range (350-1000): unpredictable juking movement
    angle_to = math.atan2(enemy_dy, enemy_dx)
    t = game_time
    juke1 = math.sin(t * 0.013) * 0.8
    juke2 = math.sin(t * 0.0071 + 1.9) * 0.5
    juke3 = math.sin(t * 0.023 + 0.5) * 0.3
    combined = juke1 + juke2 + juke3
    orbit_angle = angle_to + (math.pi / 2) * combined
    mx = my_x + math.cos(orbit_angle) * 280
    my = my_y + math.sin(orbit_angle) * 280
    return (1, [my, mx])