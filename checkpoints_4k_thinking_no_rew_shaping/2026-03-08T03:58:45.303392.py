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
    hp_advantage = my_hp_pct - enemy_hp_pct

    # Filter for truly threatening enemy projectiles
    threatening = []
    for p in observation["projectiles"]:
        if p["my_team"] == 0:
            dist = p["distance_to_me"]
            pdx = p["dx_to_me"]
            pdy = p["dy_to_me"]
            if dist < 400:
                dot = pdx * enemy_dx + pdy * enemy_dy
                if dot > 0 or dist < 200:
                    threatening.append(p)

    # AGGRESSIVE MODE: When we have HP advantage > 20%, use E to engage
    if hp_advantage > 0.2 and e_ready and enemy_dist > 400 and enemy_dist < 1500:
        # E toward enemy to get in point-blank Q range
        e_target_dist = min(475, enemy_dist - 200)
        e_x = my_x + math.cos(angle_to_enemy) * e_target_dist
        e_y = my_y + math.sin(angle_to_enemy) * e_target_dist
        return (2, [[2], [e_y, e_x]])

    # PRIORITY 0: Cast Q at enemy - HIGHEST DPS, no cooldowns = spam every tick
    # Aim directly at enemy (no lead prediction - was causing misses)
    if q_ready and enemy_dist < 1100:
        return (2, [[0], [enemy_y, enemy_x]])

    # PRIORITY 1: Dodge very close threatening projectiles
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

        # E dodge only for extremely close projectiles
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

    # PRIORITY 3: Use R more frequently (every ~4 ticks = ~1 second) for burst
    tick = int(game_time / 250)
    if r_ready and tick % 4 == 0:
        return (2, [[3], [enemy_y, enemy_x]])

    # PRIORITY 4: Use E to close gap when far away
    if e_ready and enemy_dist > 1300 and my_hp_pct > 0.25:
        e_x = my_x + math.cos(angle_to_enemy) * 475
        e_y = my_y + math.sin(angle_to_enemy) * 475
        return (2, [[2], [e_y, e_x]])

    # PRIORITY 5: Movement and positioning
    # Far away: rush toward enemy with juke
    if enemy_dist > 1000:
        juke = math.sin(game_time * 0.011) * math.pi / 4
        move_angle = angle_to_enemy + juke
        mx = my_x + math.cos(move_angle) * 400
        my_ = my_y + math.sin(move_angle) * 400
        return (1, [my_, mx])

    # Too close: kite back
    if enemy_dist < 350:
        angle_away = math.atan2(-enemy_dy, -enemy_dx)
        mx = my_x + math.cos(angle_away) * 350
        my_ = my_y + math.sin(angle_away) * 350
        return (1, [my_, mx])

    # Optimal range (350-1000): rapid unpredictable orbiting
    t = game_time
    juke1 = math.sin(t * 0.015) * 0.7
    juke2 = math.sin(t * 0.0083 + 2.1) * 0.5
    juke3 = math.sin(t * 0.027 + 0.7) * 0.4
    combined = juke1 + juke2 + juke3
    orbit_angle = angle_to_enemy + (math.pi / 2) * combined
    mx = my_x + math.cos(orbit_angle) * 300
    my_ = my_y + math.sin(orbit_angle) * 300
    return (1, [my_, mx])