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

    # Identify threatening enemy projectiles - wider detection for fast projectiles like R
    threatening = []
    for p in observation["projectiles"]:
        if p["my_team"] == 0:
            dist = p["distance_to_me"]
            if dist < 600:
                threatening.append(p)

    # PRIORITY 0: Dodge close threatening projectiles FIRST (survival is paramount)
    if threatening:
        closest = min(threatening, key=lambda p: p["distance_to_me"])
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]
        # Move perpendicular to the vector from me to projectile
        perp_x = -pdy
        perp_y = pdx
        mag = math.sqrt(perp_x ** 2 + perp_y ** 2)
        if mag > 0:
            perp_x /= mag
            perp_y /= mag

        # Use E to dodge if projectile is very close and E is ready
        if closest["distance_to_me"] < 300 and e_ready:
            e_x = my_x + perp_x * 475
            e_y = my_y + perp_y * 475
            return (2, [[2], [e_y, e_x]])

        dodge_x = my_x + perp_x * 400
        dodge_y = my_y + perp_y * 400
        return (1, [dodge_y, dodge_x])

    # Use tick counter to alternate between casting abilities and moving
    # This prevents the bot from standing still spamming one ability
    tick = int(game_time / 250)

    # Compute aim point with lead prediction to hit juking enemies
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
    lead_offset = math.sin(game_time * 0.017) * 200
    aim_x = enemy_x + math.cos(angle_to_enemy + math.pi / 2) * lead_offset
    aim_y = enemy_y + math.sin(angle_to_enemy + math.pi / 2) * lead_offset

    # CAST PHASE: every other tick, cast an ability
    if tick % 2 == 0:
        # Q is highest DPS, use when in range (1150)
        if q_ready and enemy_dist < 1150:
            return (2, [[0], [aim_y, aim_x]])

        # W for mark damage when in range (1000)
        if w_ready and enemy_dist < 1000:
            return (2, [[1], [aim_y, aim_x]])

        # R (global range) - use sparingly, every 6th tick to avoid standing still
        if r_ready and tick % 6 == 0:
            return (2, [[3], [aim_y, aim_x]])

    # MOVE PHASE: odd ticks or when no ability was appropriate

    # Use E to close gap when very far away
    if e_ready and enemy_dist > 1500 and my_hp_pct > 0.3:
        e_x = my_x + math.cos(angle_to_enemy) * 475
        e_y = my_y + math.sin(angle_to_enemy) * 475
        return (2, [[2], [e_y, e_x]])

    # Far away: approach with juke pattern to avoid skillshots
    if enemy_dist > 1000:
        juke = math.sin(game_time * 0.009) * math.pi / 5
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

    # Optimal range (350-1000): unpredictable orbiting/juking
    t = game_time
    juke1 = math.sin(t * 0.013) * 0.8
    juke2 = math.sin(t * 0.0071 + 1.9) * 0.5
    juke3 = math.sin(t * 0.023 + 0.5) * 0.3
    combined = juke1 + juke2 + juke3
    orbit_angle = angle_to_enemy + (math.pi / 2) * combined
    mx = my_x + math.cos(orbit_angle) * 280
    my = my_y + math.sin(orbit_angle) * 280
    return (1, [my, mx])