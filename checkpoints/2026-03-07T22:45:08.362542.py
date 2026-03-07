def act(self, observation):
    import math

    my_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 1)
    enemy_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 0)

    my_hp_pct = my_champ["current_hp"] / max(my_champ["max_hp"], 1)
    enemy_hp_pct = enemy_champ["current_hp"] / max(enemy_champ["max_hp"], 1)
    my_mp_pct = my_champ["current_mp"] / max(my_champ["max_mp"], 1)
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

    team = 100 if my_champ["user_id"] == 1 else 200
    if team == 100:
        base_x, base_y = 500, 500
    else:
        base_x, base_y = 14000, 14000

    # Helper: move to a point at a given distance in a direction
    def move_to(target_y, target_x):
        return (1, [target_y, target_x])

    def cast_spell(spell_idx, target_y, target_x):
        return (2, [[spell_idx], [target_y, target_x]])

    # 1. HIGHEST PRIORITY: Dodge incoming enemy projectiles
    nearby_projectiles = [p for p in observation["projectiles"]
                         if p["my_team"] == 0 and p["distance_to_me"] < 900]

    if nearby_projectiles:
        # Find the closest projectile
        closest_proj = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        proj_dx = closest_proj["dx_to_me"]
        proj_dy = closest_proj["dy_to_me"]
        proj_dist = closest_proj["distance_to_me"]

        if proj_dist < 600:
            # Dodge perpendicular to the projectile's direction toward us
            # Projectile direction is (dx_to_me, dy_to_me) from proj to us
            # We want to move perpendicular
            perp_dx = -proj_dy
            perp_dy = proj_dx
            mag = math.sqrt(perp_dx**2 + perp_dy**2)
            if mag > 0:
                dodge_dist = 350
                # Pick the perpendicular direction that moves us away from enemy too
                option1_x = my_x + (perp_dx / mag) * dodge_dist
                option1_y = my_y + (perp_dy / mag) * dodge_dist
                option2_x = my_x - (perp_dx / mag) * dodge_dist
                option2_y = my_y - (perp_dy / mag) * dodge_dist

                # Choose the option that is farther from enemy (safer)
                dist1 = math.sqrt((option1_x - enemy_x)**2 + (option1_y - enemy_y)**2)
                dist2 = math.sqrt((option2_x - enemy_x)**2 + (option2_y - enemy_y)**2)

                if dist1 >= dist2:
                    # If E is ready, use it to dodge (Ezreal E is a blink)
                    if e_ready and proj_dist < 350:
                        return cast_spell(2, option1_y, option1_x)
                    return move_to(option1_y, option1_x)
                else:
                    if e_ready and proj_dist < 350:
                        return cast_spell(2, option2_y, option2_x)
                    return move_to(option2_y, option2_x)

    # 2. LOW HP: Retreat if we're low and enemy isn't lower
    if my_hp_pct < 0.25 and enemy_hp_pct >= my_hp_pct:
        # Run toward base
        retreat_angle = math.atan2(base_y - my_y, base_x - my_x)
        retreat_x = my_x + math.cos(retreat_angle) * 400
        retreat_y = my_y + math.sin(retreat_angle) * 400
        # Throw a Q behind us as we retreat if possible
        if q_ready and enemy_dist < 1100:
            return cast_spell(0, enemy_y, enemy_x)
        return move_to(retreat_y, retreat_x)

    # 3. EXECUTE: If enemy is very low, all-in
    if enemy_hp_pct < 0.15 and enemy_dist < 1100:
        if r_ready:
            return cast_spell(3, enemy_y, enemy_x)
        if q_ready:
            return cast_spell(0, enemy_y, enemy_x)
        if w_ready and enemy_dist < 800:
            return cast_spell(1, enemy_y, enemy_x)
        # Chase for auto
        if enemy_dist > 500:
            return move_to(my_y + enemy_dy * 0.5, my_x + enemy_dx * 0.5)

    # 4. POKE WITH Q: Stay at range and use Q to deal damage without taking autos
    optimal_range = 900  # Ezreal Q range ~1150, stay at range where we can Q but they can't auto
    
    if q_ready and enemy_dist < 1100 and my_mp_pct > 0.15:
        # Lead the target slightly - cast Q at enemy position
        return cast_spell(0, enemy_y, enemy_x)

    if w_ready and enemy_dist < 900 and my_mp_pct > 0.3:
        return cast_spell(1, enemy_y, enemy_x)

    # 5. POSITIONING: Maintain optimal range with lateral movement (makes us harder to hit)
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
    game_time = observation.get("game_time", 0)
    
    # Zigzag: oscillate perpendicular to enemy direction
    zigzag_offset = math.sin(game_time * 0.003) * (math.pi / 3)
    
    if enemy_dist < 550:
        # Too close, kite back with perpendicular movement
        kite_angle = angle_to_enemy + math.pi + zigzag_offset
        kite_x = my_x + math.cos(kite_angle) * 350
        kite_y = my_y + math.sin(kite_angle) * 350
        return move_to(kite_y, kite_x)
    elif enemy_dist > optimal_range + 200:
        # Too far, approach but with angle to make dodging easier
        approach_angle = angle_to_enemy + zigzag_offset * 0.5
        approach_x = my_x + math.cos(approach_angle) * 300
        approach_y = my_y + math.sin(approach_angle) * 300
        return move_to(approach_y, approach_x)
    else:
        # Good range - orbit the enemy to dodge skillshots while waiting for cooldowns
        orbit_angle = angle_to_enemy + math.pi / 2 + zigzag_offset
        orbit_x = my_x + math.cos(orbit_angle) * 250
        orbit_y = my_y + math.sin(orbit_angle) * 250
        return move_to(orbit_y, orbit_x)