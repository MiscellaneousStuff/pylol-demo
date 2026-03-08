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
                         if p["my_team"] == 0 and p["distance_to_me"] < 600]

    game_time = observation["game_time"]

    # Calculate angle to enemy
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)

    # Priority 1: Dodge incoming enemy projectiles that are close
    if nearby_projectiles:
        closest_proj = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        proj_dx = closest_proj["dx_to_me"]
        proj_dy = closest_proj["dy_to_me"]
        proj_dist = closest_proj["distance_to_me"]

        # Calculate perpendicular dodge direction
        # Alternate dodge direction based on game time for unpredictability
        if int(game_time / 250) % 2 == 0:
            dodge_dir_x = -proj_dy
            dodge_dir_y = proj_dx
        else:
            dodge_dir_x = proj_dy
            dodge_dir_y = -proj_dx

        mag = math.sqrt(dodge_dir_x**2 + dodge_dir_y**2)
        if mag > 0 and proj_dist < 350:
            # Very close projectile - use E to blink dodge
            dodge_x = my_x + (dodge_dir_x / mag) * 400
            dodge_y = my_y + (dodge_dir_y / mag) * 400
            # Clamp to map bounds
            dodge_x = max(200, min(15800, dodge_x))
            dodge_y = max(200, min(15800, dodge_y))
            return (2, [[2], [dodge_y, dodge_x]])
        elif mag > 0 and proj_dist < 600:
            # Further projectile - sidestep while still approaching
            dodge_x = my_x + (dodge_dir_x / mag) * 300
            dodge_y = my_y + (dodge_dir_y / mag) * 300
            dodge_x = max(200, min(15800, dodge_x))
            dodge_y = max(200, min(15800, dodge_y))
            return (1, [dodge_y, dodge_x])

    # Priority 2: Close range combat - spam abilities when close to enemy
    if enemy_dist < 500:
        # Cycle through abilities rapidly - all no cooldown
        cycle = int(game_time / 100) % 6
        if cycle == 0:
            # Q at enemy
            return (2, [[0], [enemy_y, enemy_x]])
        elif cycle == 1:
            # W at enemy
            return (2, [[1], [enemy_y, enemy_x]])
        elif cycle == 2:
            # E to orbit around enemy (deal damage + reposition)
            orbit_angle = angle_to_enemy + math.pi / 2
            orbit_x = enemy_x + math.cos(orbit_angle) * 350
            orbit_y = enemy_y + math.sin(orbit_angle) * 350
            orbit_x = max(200, min(15800, orbit_x))
            orbit_y = max(200, min(15800, orbit_y))
            return (2, [[2], [orbit_y, orbit_x]])
        elif cycle == 3:
            # Q at enemy again
            return (2, [[0], [enemy_y, enemy_x]])
        elif cycle == 4:
            # R through enemy
            return (2, [[3], [enemy_y, enemy_x]])
        else:
            # Auto attack
            return (2, [[0], [enemy_y, enemy_x]])

    # Priority 3: Medium range - use E to blink in aggressively, Q/W to poke
    if enemy_dist < 1200:
        cycle = int(game_time / 120) % 5
        if cycle == 0:
            # Cast Q at enemy (long range poke)
            return (2, [[0], [enemy_y, enemy_x]])
        elif cycle == 1:
            # Cast W at enemy
            return (2, [[1], [enemy_y, enemy_x]])
        elif cycle == 2:
            # E blink toward enemy to close gap (deals damage on arrival)
            blink_x = my_x + math.cos(angle_to_enemy) * 450
            blink_y = my_y + math.sin(angle_to_enemy) * 450
            blink_x = max(200, min(15800, blink_x))
            blink_y = max(200, min(15800, blink_y))
            return (2, [[2], [blink_y, blink_x]])
        elif cycle == 3:
            # Move toward enemy at an angle (zigzag approach)
            zigzag_offset = math.pi / 4 if int(game_time / 200) % 2 == 0 else -math.pi / 4
            move_x = my_x + math.cos(angle_to_enemy + zigzag_offset) * 400
            move_y = my_y + math.sin(angle_to_enemy + zigzag_offset) * 400
            move_x = max(200, min(15800, move_x))
            move_y = max(200, min(15800, move_y))
            return (1, [move_y, move_x])
        else:
            # Q again
            return (2, [[0], [enemy_y, enemy_x]])

    # Priority 4: Long range - approach enemy with zigzag movement, cast Q/R while moving
    cycle = int(game_time / 150) % 4
    if cycle == 0:
        # Cast Q toward enemy while approaching
        return (2, [[0], [enemy_y, enemy_x]])
    elif cycle == 1:
        # Move toward enemy at an angle (zigzag to dodge)
        zigzag_offset = math.pi / 3 if int(game_time / 250) % 2 == 0 else -math.pi / 3
        move_x = my_x + math.cos(angle_to_enemy + zigzag_offset) * 500
        move_y = my_y + math.sin(angle_to_enemy + zigzag_offset) * 500
        move_x = max(200, min(15800, move_x))
        move_y = max(200, min(15800, move_y))
        return (1, [move_y, move_x])
    elif cycle == 2:
        # Cast R at enemy for long range damage
        return (2, [[3], [enemy_y, enemy_x]])
    else:
        # Move toward enemy straight to close distance
        move_x = my_x + math.cos(angle_to_enemy) * 500
        move_y = my_y + math.sin(angle_to_enemy) * 500
        move_x = max(200, min(15800, move_x))
        move_y = max(200, min(15800, move_y))
        return (1, [move_y, move_x])