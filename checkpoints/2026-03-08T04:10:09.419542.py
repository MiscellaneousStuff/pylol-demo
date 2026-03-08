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

    nearby_projectiles = [p for p in observation["projectiles"]
                         if p["my_team"] == 0 and p["distance_to_me"] < 400]

    game_time = observation["game_time"]
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)

    # Tick counter - game_time increments by ~250 per step
    tick = int(game_time / 250)

    # Priority 1: Dodge VERY close enemy projectiles (< 400 units)
    if nearby_projectiles:
        closest_proj = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        proj_dx = closest_proj["dx_to_me"]
        proj_dy = closest_proj["dy_to_me"]
        proj_dist = closest_proj["distance_to_me"]

        if proj_dist < 300:
            # Perpendicular dodge - alternate direction each tick
            if tick % 2 == 0:
                dodge_dir_x = -proj_dy
                dodge_dir_y = proj_dx
            else:
                dodge_dir_x = proj_dy
                dodge_dir_y = -proj_dx

            mag = math.sqrt(dodge_dir_x**2 + dodge_dir_y**2)
            if mag > 0:
                # Use E to blink dodge if very close
                dodge_x = my_x + (dodge_dir_x / mag) * 400
                dodge_y = my_y + (dodge_dir_y / mag) * 400
                dodge_x = max(200, min(15800, dodge_x))
                dodge_y = max(200, min(15800, dodge_y))
                return (2, [[2], [dodge_y, dodge_x]])

    # Priority 2: Close range combat (< 600 units) - spam abilities aggressively
    if enemy_dist < 600:
        cycle = tick % 5
        if cycle == 0:
            # Q at enemy
            return (2, [[0], [enemy_y, enemy_x]])
        elif cycle == 1:
            # E onto enemy (blink damage + reposition)
            # Blink to just behind/beside enemy for safety
            orbit_angle = angle_to_enemy + (math.pi / 3 if tick % 4 < 2 else -math.pi / 3)
            e_x = enemy_x + math.cos(orbit_angle) * 200
            e_y = enemy_y + math.sin(orbit_angle) * 200
            e_x = max(200, min(15800, e_x))
            e_y = max(200, min(15800, e_y))
            return (2, [[2], [e_y, e_x]])
        elif cycle == 2:
            # W at enemy
            return (2, [[1], [enemy_y, enemy_x]])
        elif cycle == 3:
            # R through enemy
            return (2, [[3], [enemy_y, enemy_x]])
        else:
            # Q again
            return (2, [[0], [enemy_y, enemy_x]])

    # Priority 3: Medium range (600-1200) - poke and close gap
    if enemy_dist < 1200:
        cycle = tick % 4
        if cycle == 0:
            # Q at enemy
            return (2, [[0], [enemy_y, enemy_x]])
        elif cycle == 1:
            # E blink toward enemy aggressively
            blink_x = my_x + math.cos(angle_to_enemy) * 475
            blink_y = my_y + math.sin(angle_to_enemy) * 475
            blink_x = max(200, min(15800, blink_x))
            blink_y = max(200, min(15800, blink_y))
            return (2, [[2], [blink_y, blink_x]])
        elif cycle == 2:
            # W at enemy
            return (2, [[1], [enemy_y, enemy_x]])
        else:
            # Move toward enemy with slight zigzag
            zigzag = math.pi / 6 if tick % 6 < 3 else -math.pi / 6
            move_x = my_x + math.cos(angle_to_enemy + zigzag) * 500
            move_y = my_y + math.sin(angle_to_enemy + zigzag) * 500
            move_x = max(200, min(15800, move_x))
            move_y = max(200, min(15800, move_y))
            return (1, [move_y, move_x])

    # Priority 4: Long range (> 1200) - MUST close distance quickly
    # Alternate: move toward enemy, then cast long-range ability
    cycle = tick % 3
    if cycle == 0:
        # Move toward enemy with zigzag
        zigzag = math.pi / 5 if tick % 4 < 2 else -math.pi / 5
        move_x = my_x + math.cos(angle_to_enemy + zigzag) * 600
        move_y = my_y + math.sin(angle_to_enemy + zigzag) * 600
        move_x = max(200, min(15800, move_x))
        move_y = max(200, min(15800, move_y))
        return (1, [move_y, move_x])
    elif cycle == 1:
        # E blink toward enemy to close gap fast
        blink_x = my_x + math.cos(angle_to_enemy) * 475
        blink_y = my_y + math.sin(angle_to_enemy) * 475
        blink_x = max(200, min(15800, blink_x))
        blink_y = max(200, min(15800, blink_y))
        return (2, [[2], [blink_y, blink_x]])
    else:
        # Move straight toward enemy
        move_x = my_x + math.cos(angle_to_enemy) * 600
        move_y = my_y + math.sin(angle_to_enemy) * 600
        move_x = max(200, min(15800, move_x))
        move_y = max(200, min(15800, move_y))
        return (1, [move_y, move_x])