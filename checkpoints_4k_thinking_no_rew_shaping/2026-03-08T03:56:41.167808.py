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
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)

    # Only consider enemy projectiles that are CLOSE and likely heading toward us
    # Check that the projectile is between us and enemy (same sign as enemy direction)
    # and within a tight radius
    threatening = []
    for p in observation["projectiles"]:
        if p["my_team"] == 0:
            dist = p["distance_to_me"]
            pdx = p["dx_to_me"]
            pdy = p["dy_to_me"]
            # Only threatening if close AND roughly in the direction of enemy
            # (meaning it's between us and enemy, heading toward us)
            if dist < 400:
                # Check if projectile is on the same side as enemy (heading toward us)
                dot = pdx * enemy_dx + pdy * enemy_dy
                if dot > 0 or dist < 200:
                    threatening.append(p)

    # PRIORITY 0: Cast Q at enemy when in range - THIS IS THE HIGHEST DPS ACTION
    # No cooldowns means we should Q every single tick possible
    if q_ready and enemy_dist < 1100:
        # Lead prediction: aim slightly ahead of enemy movement
        lead_offset = math.sin(game_time * 0.019) * 150
        aim_x = enemy_x + math.cos(angle_to_enemy + math.pi / 2) * lead_offset
        aim_y = enemy_y + math.sin(angle_to_enemy + math.pi / 2) * lead_offset
        return (2, [[0], [aim_y, aim_x]])

    # PRIORITY 1: Dodge VERY close projectiles (only after Q is cast)
    if threatening:
        closest = min(threatening, key=lambda p: p["distance_to_me"])
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]
        perp_x = -pdy
        perp_y = pdx
        mag = math.sqrt(perp_x ** 2 + perp_y ** 2)
        if mag > 0:
            perp_x /= mag
            perp_y /= mag

        # Use E to dodge if very close
        if closest["distance_to_me"] < 200 and e_ready:
            e_x = my_x + perp_x * 475
            e_y = my_y + perp_y * 475
            return (2, [[2], [e_y, e_x]])

        dodge_x = my_x + perp_x * 350
        dodge_y = my_y + perp_y * 350
        return (1, [dodge_y, dodge_x])

    # PRIORITY 2: Cast W for mark damage when in range
    if w_ready and enemy_dist < 1000:
        return (2, [[1], [enemy_y, enemy_x]])

    # PRIORITY 3: Use R occasionally (every ~8 ticks) for burst damage
    tick = int(game_time / 250)
    if r_ready and tick % 8 == 0:
        return (2, [[3], [enemy_y, enemy_x]])

    # PRIORITY 4: Use E to close gap when far
    if e_ready and enemy_dist > 1300 and my_hp_pct > 0.25:
        e_x = my_x + math.cos(angle_to_enemy) * 475
        e_y = my_y + math.sin(angle_to_enemy) * 475
        return (2, [[2], [e_y, e_x]])

    # PRIORITY 5: Movement and positioning
    # Far away: rush toward enemy with juke pattern
    if enemy_dist > 1000:
        juke = math.sin(game_time * 0.011) * math.pi / 4
        move_angle = angle_to_enemy + juke
        mx = my_x + math.cos(move_angle) * 400
        my = my_y + math.sin(move_angle) * 400
        return (1, [my, mx])

    # Too close: kite back
    if enemy_dist < 350:
        angle_away = math.atan2(-enemy_dy, -enemy_dx)
        mx = my_x + math.cos(angle_away) * 350
        my = my_y + math.sin(angle_away) * 350
        return (1, [my, mx])

    # Optimal range (350-1000): unpredictable orbiting
    t = game_time
    juke1 = math.sin(t * 0.015) * 0.7
    juke2 = math.sin(t * 0.0083 + 2.1) * 0.5
    juke3 = math.sin(t * 0.027 + 0.7) * 0.4
    combined = juke1 + juke2 + juke3
    orbit_angle = angle_to_enemy + (math.pi / 2) * combined
    mx = my_x + math.cos(orbit_angle) * 300
    my = my_y + math.sin(orbit_angle) * 300
    return (1, [my, mx])