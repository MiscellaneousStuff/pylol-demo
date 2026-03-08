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

    # PRIORITY 1: SPAM Q at enemy - this is the #1 source of damage
    # Ezreal Q range ~1150, no cooldowns means cast every tick possible
    if enemy_dist < 1100 and q_ready:
        # Aim slightly ahead of enemy to lead the shot
        # Simple lead: offset in the direction they might be moving
        return (2, [[0], [enemy_y, enemy_x]])

    # PRIORITY 2: Cast W for extra poke/mark damage
    if enemy_dist < 1000 and w_ready:
        return (2, [[1], [enemy_y, enemy_x]])

    # PRIORITY 3: Use R when enemy is low for execute
    if r_ready and enemy_hp_pct < 0.35 and enemy_dist < 2000:
        return (2, [[3], [enemy_y, enemy_x]])

    # PRIORITY 4: Dodge ONLY very close threatening projectiles
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

        # Use E only for extremely close projectiles
        if closest["distance_to_me"] < 150 and e_ready:
            e_x = my_x + perp_x * 475
            e_y = my_y + perp_y * 475
            return (2, [[2], [e_y, e_x]])

        return (1, [dodge_y, dodge_x])

    # PRIORITY 5: Positioning - stay in Q range while juking
    optimal_range = 750

    if enemy_dist < 350:
        # Too close, kite back
        angle_away = math.atan2(-enemy_dy, -enemy_dx)
        mx = my_x + math.cos(angle_away) * 350
        my = my_y + math.sin(angle_away) * 350
        return (1, [my, mx])

    if enemy_dist > 1050:
        # Too far, close the gap at an angle to juke
        angle_to = math.atan2(enemy_dy, enemy_dx)
        juke = math.sin(game_time * 0.006) * math.pi / 4
        move_angle = angle_to + juke
        mx = my_x + math.cos(move_angle) * 350
        my = my_y + math.sin(move_angle) * 350
        return (1, [my, mx])

    # In optimal range: orbit rapidly to dodge skillshots
    angle_to = math.atan2(enemy_dy, enemy_dx)
    # Fast oscillating juke pattern - switch direction frequently
    juke_dir = 1 if int(game_time / 250) % 2 == 0 else -1
    orbit_angle = angle_to + (math.pi / 2) * juke_dir
    mx = my_x + math.cos(orbit_angle) * 250
    my = my_y + math.sin(orbit_angle) * 250
    return (1, [my, mx])