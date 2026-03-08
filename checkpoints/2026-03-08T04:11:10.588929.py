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
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
    game_time = observation["game_time"]
    tick = int(game_time / 250)

    # Gather all enemy projectiles sorted by distance
    enemy_projectiles = sorted(
        [p for p in observation["projectiles"] if p["my_team"] == 0],
        key=lambda p: p["distance_to_me"]
    )
    
    close_projectiles = [p for p in enemy_projectiles if p["distance_to_me"] < 600]

    # Helper: compute perpendicular dodge position
    def get_dodge_pos(proj, dodge_dist=350):
        pdx = proj["dx_to_me"]
        pdy = proj["dy_to_me"]
        # Perpendicular directions
        perp1_x, perp1_y = -pdy, pdx
        perp2_x, perp2_y = pdy, -pdx
        
        # Choose direction that moves us away from enemy (safer) or alternate
        # Pick the one that keeps us at reasonable range from enemy
        mag1 = math.sqrt(perp1_x**2 + perp1_y**2)
        if mag1 == 0:
            return my_x + dodge_dist, my_y
        
        opt1_x = my_x + (perp1_x / mag1) * dodge_dist
        opt1_y = my_y + (perp1_y / mag1) * dodge_dist
        opt2_x = my_x + (perp2_x / mag1) * dodge_dist
        opt2_y = my_y + (perp2_y / mag1) * dodge_dist
        
        # Pick the one that doesn't move us too close to enemy
        dist1 = math.sqrt((opt1_x - enemy_x)**2 + (opt1_y - enemy_y)**2)
        dist2 = math.sqrt((opt2_x - enemy_x)**2 + (opt2_y - enemy_y)**2)
        
        # Prefer the dodge that keeps us at ~400-600 range if close, or closer if far
        if enemy_dist < 500:
            # When close, dodge away from enemy
            if dist1 > dist2:
                dx, dy = opt1_x, opt1_y
            else:
                dx, dy = opt2_x, opt2_y
        else:
            # When far, alternate to be unpredictable
            if tick % 2 == 0:
                dx, dy = opt1_x, opt1_y
            else:
                dx, dy = opt2_x, opt2_y
        
        return max(200, min(15800, dx)), max(200, min(15800, dy))

    # PRIORITY 1: Dodge very close projectiles - ALWAYS dodge these
    if close_projectiles:
        closest = close_projectiles[0]
        if closest["distance_to_me"] < 350:
            # Emergency dodge with E blink (fastest escape)
            dx, dy = get_dodge_pos(closest, 475)
            return (2, [[2], [dy, dx]])
        elif closest["distance_to_me"] < 600:
            # Walk dodge
            dx, dy = get_dodge_pos(closest, 350)
            return (1, [dy, dx])

    # PRIORITY 2: Close range combat (< 550) - alternate attack and reposition
    if enemy_dist < 550:
        cycle = tick % 6
        if cycle == 0:
            # Q at enemy
            return (2, [[0], [enemy_y, enemy_x]])
        elif cycle == 1:
            # Sidestep/orbit - move perpendicular to enemy
            orbit_angle = angle_to_enemy + (math.pi / 2 if tick % 4 < 2 else -math.pi / 2)
            move_x = my_x + math.cos(orbit_angle) * 300
            move_y = my_y + math.sin(orbit_angle) * 300
            move_x = max(200, min(15800, move_x))
            move_y = max(200, min(15800, move_y))
            return (1, [move_y, move_x])
        elif cycle == 2:
            # W at enemy
            return (2, [[1], [enemy_y, enemy_x]])
        elif cycle == 3:
            # Sidestep again (opposite direction)
            orbit_angle = angle_to_enemy + (-math.pi / 2 if tick % 4 < 2 else math.pi / 2)
            move_x = my_x + math.cos(orbit_angle) * 300
            move_y = my_y + math.sin(orbit_angle) * 300
            move_x = max(200, min(15800, move_x))
            move_y = max(200, min(15800, move_y))
            return (1, [move_y, move_x])
        elif cycle == 4:
            # R through enemy
            return (2, [[3], [enemy_y, enemy_x]])
        else:
            # E to reposition to flank (not directly on enemy)
            orbit_angle = angle_to_enemy + (math.pi / 3 if tick % 8 < 4 else -math.pi / 3)
            e_x = enemy_x + math.cos(orbit_angle) * 350
            e_y = enemy_y + math.sin(orbit_angle) * 350
            e_x = max(200, min(15800, e_x))
            e_y = max(200, min(15800, e_y))
            return (2, [[2], [e_y, e_x]])

    # PRIORITY 3: Medium range (550-1000) - poke and close gap with zigzag
    if enemy_dist < 1000:
        cycle = tick % 4
        if cycle == 0:
            # Q at enemy (long range poke)
            return (2, [[0], [enemy_y, enemy_x]])
        elif cycle == 1:
            # Zigzag approach
            zigzag = math.pi / 4 if tick % 6 < 3 else -math.pi / 4
            move_x = my_x + math.cos(angle_to_enemy + zigzag) * 400
            move_y = my_y + math.sin(angle_to_enemy + zigzag) * 400
            move_x = max(200, min(15800, move_x))
            move_y = max(200, min(15800, move_y))
            return (1, [move_y, move_x])
        elif cycle == 2:
            # W at enemy
            return (2, [[1], [enemy_y, enemy_x]])
        else:
            # E blink toward enemy but offset to side
            offset = math.pi / 6 if tick % 4 < 2 else -math.pi / 6
            blink_x = my_x + math.cos(angle_to_enemy + offset) * 475
            blink_y = my_y + math.sin(angle_to_enemy + offset) * 475
            blink_x = max(200, min(15800, blink_x))
            blink_y = max(200, min(15800, blink_y))
            return (2, [[2], [blink_y, blink_x]])

    # PRIORITY 4: Long range (> 1000) - close distance FAST with zigzag
    cycle = tick % 3
    if cycle == 0:
        # E blink toward enemy to close gap
        blink_x = my_x + math.cos(angle_to_enemy) * 475
        blink_y = my_y + math.sin(angle_to_enemy) * 475
        blink_x = max(200, min(15800, blink_x))
        blink_y = max(200, min(15800, blink_y))
        return (2, [[2], [blink_y, blink_x]])
    elif cycle == 1:
        # Q at enemy while approaching
        return (2, [[0], [enemy_y, enemy_x]])
    else:
        # Zigzag move toward enemy
        zigzag = math.pi / 5 if tick % 4 < 2 else -math.pi / 5
        move_x = my_x + math.cos(angle_to_enemy + zigzag) * 600
        move_y = my_y + math.sin(angle_to_enemy + zigzag) * 600
        move_x = max(200, min(15800, move_x))
        move_y = max(200, min(15800, move_y))
        return (1, [move_y, move_x])