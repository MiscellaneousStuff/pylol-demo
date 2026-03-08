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

    # Gather enemy projectiles sorted by distance
    enemy_projectiles = sorted(
        [p for p in observation["projectiles"] if p["my_team"] == 0],
        key=lambda p: p["distance_to_me"]
    )

    # Only consider truly dangerous projectiles (close ones)
    dangerous = [p for p in enemy_projectiles if p["distance_to_me"] < 400]

    # Helper: perpendicular dodge position that tries to stay near combat range
    def get_dodge_pos(proj, dodge_dist=300):
        pdx = proj["dx_to_me"]
        pdy = proj["dy_to_me"]
        perp1_x, perp1_y = -pdy, pdx
        perp2_x, perp2_y = pdy, -pdx
        mag = math.sqrt(perp1_x**2 + perp1_y**2)
        if mag < 1:
            return my_x + dodge_dist, my_y
        opt1_x = my_x + (perp1_x / mag) * dodge_dist
        opt1_y = my_y + (perp1_y / mag) * dodge_dist
        opt2_x = my_x + (perp2_x / mag) * dodge_dist
        opt2_y = my_y + (perp2_y / mag) * dodge_dist
        # Prefer option that keeps us at ~450 range from enemy
        dist1 = math.sqrt((opt1_x - enemy_x)**2 + (opt1_y - enemy_y)**2)
        dist2 = math.sqrt((opt2_x - enemy_x)**2 + (opt2_y - enemy_y)**2)
        target = 450
        if abs(dist1 - target) < abs(dist2 - target):
            return max(200, min(15800, opt1_x)), max(200, min(15800, opt1_y))
        else:
            return max(200, min(15800, opt2_x)), max(200, min(15800, opt2_y))

    # PRIORITY 1: Dodge very close projectiles by walking perpendicular
    # Only dodge if projectile is truly threatening (< 350 distance)
    if dangerous and dangerous[0]["distance_to_me"] < 350:
        p = dangerous[0]
        dx, dy = get_dodge_pos(p, 320)
        return (1, [dy, dx])

    # PRIORITY 2: Close range (< 500) - maximum DPS with interleaved movement
    if enemy_dist < 500:
        cycle = tick % 6
        if cycle == 0:
            # Q at enemy
            return (2, [[0], [enemy_y, enemy_x]])
        elif cycle == 1:
            # Orbit sideways (dodge pattern while staying in range)
            orbit_dir = math.pi / 2 if tick % 8 < 4 else -math.pi / 2
            move_x = my_x + math.cos(angle_to_enemy + orbit_dir) * 250
            move_y = my_y + math.sin(angle_to_enemy + orbit_dir) * 250
            move_x = max(200, min(15800, move_x))
            move_y = max(200, min(15800, move_y))
            return (1, [move_y, move_x])
        elif cycle == 2:
            # W at enemy
            return (2, [[1], [enemy_y, enemy_x]])
        elif cycle == 3:
            # E blink to flanking position around enemy (deals damage + repositions)
            flank_angle = angle_to_enemy + (math.pi / 2 if tick % 10 < 5 else -math.pi / 2)
            e_x = my_x + math.cos(flank_angle) * 350
            e_y = my_y + math.sin(flank_angle) * 350
            e_x = max(200, min(15800, e_x))
            e_y = max(200, min(15800, e_y))
            return (2, [[2], [e_y, e_x]])
        elif cycle == 4:
            # R at enemy (no cooldowns = free damage)
            return (2, [[3], [enemy_y, enemy_x]])
        else:
            # Auto attack enemy
            return (2, [[0], [enemy_y, enemy_x]])

    # PRIORITY 3: Medium range (500-850) - poke and close gap
    if enemy_dist < 850:
        cycle = tick % 5
        if cycle == 0:
            # Q at enemy (long range poke)
            return (2, [[0], [enemy_y, enemy_x]])
        elif cycle == 1:
            # Zigzag approach toward enemy
            zigzag = math.pi / 4 if tick % 6 < 3 else -math.pi / 4
            move_x = my_x + math.cos(angle_to_enemy + zigzag) * 350
            move_y = my_y + math.sin(angle_to_enemy + zigzag) * 350
            move_x = max(200, min(15800, move_x))
            move_y = max(200, min(15800, move_y))
            return (1, [move_y, move_x])
        elif cycle == 2:
            # E blink toward enemy (aggressive gap close + damage)
            offset = math.pi / 6 if tick % 4 < 2 else -math.pi / 6
            blink_x = my_x + math.cos(angle_to_enemy + offset) * 475
            blink_y = my_y + math.sin(angle_to_enemy + offset) * 475
            blink_x = max(200, min(15800, blink_x))
            blink_y = max(200, min(15800, blink_y))
            return (2, [[2], [blink_y, blink_x]])
        elif cycle == 3:
            # W at enemy
            return (2, [[1], [enemy_y, enemy_x]])
        else:
            # Move straight toward enemy
            move_x = my_x + math.cos(angle_to_enemy) * 400
            move_y = my_y + math.sin(angle_to_enemy) * 400
            move_x = max(200, min(15800, move_x))
            move_y = max(200, min(15800, move_y))
            return (1, [move_y, move_x])

    # PRIORITY 4: Long range (> 850) - close distance FAST
    cycle = tick % 3
    if cycle == 0:
        # E blink toward enemy to close gap fast
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
        move_x = my_x + math.cos(angle_to_enemy + zigzag) * 500
        move_y = my_y + math.sin(angle_to_enemy + zigzag) * 500
        move_x = max(200, min(15800, move_x))
        move_y = max(200, min(15800, move_y))
        return (1, [move_y, move_x])