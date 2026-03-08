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

    game_time = observation.get("game_time", 0)

    def move_to(target_y, target_x):
        target_x = max(0, min(16000, target_x))
        target_y = max(0, min(16000, target_y))
        return (1, [target_y, target_x])

    def cast_spell(spell_idx, target_y, target_x):
        target_x = max(0, min(16000, target_x))
        target_y = max(0, min(16000, target_y))
        return (2, [[spell_idx], [target_y, target_x]])

    # 1. DODGE: Detect incoming enemy projectiles
    nearby_projectiles = [p for p in observation["projectiles"]
                         if p["my_team"] == 0 and p["distance_to_me"] < 900]

    if nearby_projectiles:
        closest_proj = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        proj_dx = closest_proj["dx_to_me"]
        proj_dy = closest_proj["dy_to_me"]
        proj_dist = closest_proj["distance_to_me"]
        proj_name = closest_proj.get("name", "")

        if proj_dist < 700:
            # Perpendicular dodge
            perp_dx = proj_dy
            perp_dy = -proj_dx
            mag = math.sqrt(perp_dx**2 + perp_dy**2)
            if mag > 0:
                dodge_dist = 450
                option1_x = my_x + (perp_dx / mag) * dodge_dist
                option1_y = my_y + (perp_dy / mag) * dodge_dist
                option2_x = my_x - (perp_dx / mag) * dodge_dist
                option2_y = my_y - (perp_dy / mag) * dodge_dist

                # Choose option closer to center of map
                dist1_center = abs(option1_x - 8000) + abs(option1_y - 8000)
                dist2_center = abs(option2_x - 8000) + abs(option2_y - 8000)
                best_x, best_y = (option1_x, option1_y) if dist1_center <= dist2_center else (option2_x, option2_y)

                # Use E to dodge very close projectiles
                if e_ready and proj_dist < 350:
                    return cast_spell(2, best_y, best_x)
                return move_to(best_y, best_x)

    # 2. EXECUTE with R: Enemy is low HP - R is GLOBAL range, use it!
    if r_ready and enemy_hp_pct < 0.30 and my_mp_pct > 0.1:
        # Lead the target slightly in direction they might be moving
        return cast_spell(3, enemy_y, enemy_x)

    # 3. EXECUTE: Enemy is very low, go all-in aggressively
    if enemy_hp_pct < 0.25 and my_hp_pct > 0.05:
        if q_ready and enemy_dist < 1150:
            return cast_spell(0, enemy_y, enemy_x)
        if w_ready and enemy_dist < 950:
            return cast_spell(1, enemy_y, enemy_x)
        # E forward aggressively to close gap for kill
        if e_ready and enemy_dist > 500 and enemy_dist < 2000:
            # E toward enemy
            dx = enemy_x - my_x
            dy = enemy_y - my_y
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 0:
                e_range = 475
                e_x = my_x + (dx / dist) * e_range
                e_y = my_y + (dy / dist) * e_range
                return cast_spell(2, e_y, e_x)
        # Chase hard
        return move_to(enemy_y, enemy_x)

    # 4. LOW HP: Retreat if critically low and enemy isn't lower
    if my_hp_pct < 0.15 and enemy_hp_pct > my_hp_pct + 0.05:
        # Parting Q shot
        if q_ready and enemy_dist < 1150:
            return cast_spell(0, enemy_y, enemy_x)
        # E away
        if e_ready:
            retreat_x = my_x + (my_x - enemy_x) * 0.5
            retreat_y = my_y + (my_y - enemy_y) * 0.5
            return cast_spell(2, retreat_y, retreat_x)
        # Run away
        retreat_x = my_x + (my_x - enemy_x) * 0.5
        retreat_y = my_y + (my_y - enemy_y) * 0.5
        return move_to(retreat_y, retreat_x)

    # 5. COMBAT: Q poke - bread and butter
    if q_ready and enemy_dist < 1150 and my_mp_pct > 0.08:
        return cast_spell(0, enemy_y, enemy_x)

    # 6. COMBAT: W for extra damage
    if w_ready and enemy_dist < 950 and my_mp_pct > 0.2:
        return cast_spell(1, enemy_y, enemy_x)

    # 7. AUTO ATTACK range: kite
    if enemy_dist < 550:
        # Auto attack by moving toward enemy briefly, then kite back
        away_x = my_x + (my_x - enemy_x) * 0.4
        away_y = my_y + (my_y - enemy_y) * 0.4
        return move_to(away_y, away_x)

    # 8. APPROACH: Close distance to get into Q range
    optimal_range = 900
    if enemy_dist > optimal_range:
        dx = enemy_x - my_x
        dy = enemy_y - my_y
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            nx = dx / dist
            ny = dy / dist
            # When far away, move directly without juking (juke only when close)
            if enemy_dist > 2000:
                # Move directly toward enemy, full speed
                target_x = my_x + nx * 800
                target_y = my_y + ny * 800
                return move_to(target_y, target_x)
            else:
                # Add slight juke when approaching within skillshot range
                juke_amplitude = 200
                juke = math.sin(game_time * 0.01) * juke_amplitude
                perp_x = -ny * juke
                perp_y = nx * juke
                step_size = min(600, enemy_dist - optimal_range + 400)
                target_x = my_x + nx * step_size + perp_x
                target_y = my_y + ny * step_size + perp_y
                return move_to(target_y, target_x)
        return move_to(enemy_y, enemy_x)
    else:
        # In good range - orbit to dodge while waiting for cooldowns
        dx = enemy_x - my_x
        dy = enemy_y - my_y
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            nx = dx / dist
            ny = dy / dist
            orbit_dir = 1 if math.sin(game_time * 0.008) > 0 else -1
            orbit_x = my_x + (-ny * orbit_dir) * 350
            orbit_y = my_y + (nx * orbit_dir) * 350
            return move_to(orbit_y, orbit_x)
        return move_to(my_y, my_x)