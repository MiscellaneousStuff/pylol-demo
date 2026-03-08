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

    # Detect nearby enemy projectiles
    nearby_projectiles = [p for p in observation["projectiles"]
                         if p["my_team"] == 0 and p["distance_to_me"] < 900]

    # PRIORITY 1: Dodge incoming projectiles
    if nearby_projectiles:
        # Find the closest/most threatening projectile
        closest_proj = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        proj_dx = closest_proj["dx_to_me"]
        proj_dy = closest_proj["dy_to_me"]
        proj_dist = closest_proj["distance_to_me"]

        # If projectile is close, dodge perpendicular to its travel direction
        if proj_dist < 700:
            # Perpendicular direction (rotate 90 degrees)
            perp_dx = -proj_dy
            perp_dy = proj_dx
            mag = math.sqrt(perp_dx**2 + perp_dy**2)
            if mag > 0:
                perp_dx /= mag
                perp_dy /= mag

            # Choose dodge direction - use game time to vary dodge direction
            # Also add a component away from enemy to maintain range
            dodge_dist = 350
            dodge_x = my_x + perp_dx * dodge_dist
            dodge_y = my_y + perp_dy * dodge_dist

            # Use E (Arcane Shift) to dodge if projectile is very close
            if proj_dist < 400 and e_ready:
                return (2, [[2], [dodge_y, dodge_x]])

            return (1, [dodge_y, dodge_x])

    # PRIORITY 2: Attack with abilities when in range
    # Optimal range for Ezreal Q is around 800-1000 units
    optimal_range = 800

    if enemy_dist < 1200:
        # Cast Q (Mystic Shot) - spam it since no cooldowns
        if q_ready:
            # Lead the target slightly - aim at enemy position
            # Add slight prediction based on their movement
            return (2, [[0], [enemy_y, enemy_x]])

        # Cast W through enemy
        if w_ready:
            return (2, [[1], [enemy_y, enemy_x]])

        # Cast R if enemy is low HP
        if r_ready and enemy_hp_pct < 0.4:
            return (2, [[3], [enemy_y, enemy_x]])

    # PRIORITY 3: Positioning - maintain optimal range while wiggling
    if enemy_dist < 500:
        # Too close - back off while moving perpendicular (don't retreat in straight line)
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        # Move away at an angle (not straight back)
        wiggle_offset = math.sin(observation["game_time"] * 0.01) * math.pi / 3
        retreat_angle = angle_to_enemy - math.pi + wiggle_offset
        move_x = my_x + math.cos(retreat_angle) * 400
        move_y = my_y + math.sin(retreat_angle) * 400
        return (1, [move_y, move_x])

    if enemy_dist > 1000:
        # Too far - approach but at an angle (not straight line)
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        wiggle_offset = math.sin(observation["game_time"] * 0.008) * math.pi / 4
        approach_angle = angle_to_enemy + wiggle_offset
        move_x = my_x + math.cos(approach_angle) * 300
        move_y = my_y + math.sin(approach_angle) * 300
        return (1, [move_y, move_x])

    # At good range - orbit/wiggle to be hard to hit while casting Q
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
    # Orbit perpendicular with wiggle
    orbit_direction = 1 if int(observation["game_time"] / 500) % 2 == 0 else -1
    orbit_angle = angle_to_enemy + (math.pi / 2) * orbit_direction
    move_x = my_x + math.cos(orbit_angle) * 250
    move_y = my_y + math.sin(orbit_angle) * 250
    return (1, [move_y, move_x])