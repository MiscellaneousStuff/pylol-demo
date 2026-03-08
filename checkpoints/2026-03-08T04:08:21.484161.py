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

    # Priority 1: Dodge incoming enemy projectiles
    if nearby_projectiles:
        closest_proj = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        proj_dx = closest_proj["dx_to_me"]
        proj_dy = closest_proj["dy_to_me"]
        proj_dist = closest_proj["distance_to_me"]
        
        # Calculate perpendicular dodge direction
        # Alternate dodge direction based on time to be unpredictable
        if int(game_time / 300) % 2 == 0:
            dodge_dir_x = -proj_dy
            dodge_dir_y = proj_dx
        else:
            dodge_dir_x = proj_dy
            dodge_dir_y = -proj_dx
        
        mag = math.sqrt(dodge_dir_x**2 + dodge_dir_y**2)
        if mag > 0 and proj_dist < 400:
            # Use E (Arcane Shift) to blink perpendicular to dodge while dealing damage
            # Blink toward enemy's flank
            dodge_target_x = my_x + (dodge_dir_x / mag) * 300
            dodge_target_y = my_y + (dodge_dir_y / mag) * 300
            # Use E to blink-dodge
            return (2, [[2], [dodge_target_y, dodge_target_x]])
        elif proj_dist < 600:
            # If projectile further, try to cast Q at enemy while sidestepping
            dodge_target_x = my_x + (dodge_dir_x / mag) * 250 if mag > 0 else my_x + 200
            dodge_target_y = my_y + (dodge_dir_y / mag) * 250 if mag > 0 else my_y + 200
            return (1, [dodge_target_y, dodge_target_x])

    # Priority 2: Spam abilities at enemy - no cooldowns means maximum DPS
    # Use R (Trueshot Barrage) at long range for big damage
    if enemy_dist > 1000:
        # Cast R toward enemy for long-range poke while approaching
        return (2, [[3], [enemy_y, enemy_x]])

    # Use E (Arcane Shift) aggressively to blink toward enemy flank
    # This does damage AND repositions us to dodge
    if enemy_dist > 400:
        # Blink to a position offset from the enemy (flanking angle)
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        # Offset to the side so we don't blink into their Q line
        offset = math.pi / 4 if int(game_time / 200) % 2 == 0 else -math.pi / 4
        blink_x = my_x + math.cos(angle_to_enemy + offset) * min(enemy_dist - 100, 475)
        blink_y = my_y + math.sin(angle_to_enemy + offset) * min(enemy_dist - 100, 475)
        return (2, [[2], [blink_y, blink_x]])

    # In close range: cycle through abilities rapidly
    # Rotation: Q -> W -> E -> Q -> W -> E (all no cooldown)
    cycle = int(game_time / 150) % 4
    
    if cycle == 0:
        # Cast Q at enemy
        return (2, [[0], [enemy_y, enemy_x]])
    elif cycle == 1:
        # Cast W at enemy
        return (2, [[1], [enemy_y, enemy_x]])
    elif cycle == 2:
        # Cast E to reposition (orbit around enemy)
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        orbit_x = enemy_x + math.cos(angle_to_enemy + math.pi / 3) * 350
        orbit_y = enemy_y + math.sin(angle_to_enemy + math.pi / 3) * 350
        return (2, [[2], [orbit_y, orbit_x]])
    else:
        # Cast R through enemy
        return (2, [[3], [enemy_y, enemy_x]])