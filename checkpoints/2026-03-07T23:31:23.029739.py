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

    game_time = observation.get("game_time", 0)

    def move_to(target_y, target_x):
        target_x = max(0, min(16000, target_x))
        target_y = max(0, min(16000, target_y))
        return (1, [target_y, target_x])

    def cast_spell(spell_idx, target_y, target_x):
        target_x = max(0, min(16000, target_x))
        target_y = max(0, min(16000, target_y))
        return (2, [[spell_idx], [target_y, target_x]])

    # 1. DODGE: Detect enemy projectiles with generous range for fast projectiles
    nearby_projectiles = [p for p in observation["projectiles"]
                         if p["my_team"] == 0 and p["distance_to_me"] < 1000]

    if nearby_projectiles:
        closest_proj = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        proj_dx = closest_proj["dx_to_me"]  # vector from projectile to me
        proj_dy = closest_proj["dy_to_me"]
        proj_dist = closest_proj["distance_to_me"]

        # The projectile is moving TOWARD us (dx_to_me is shrinking over time)
        # We want to dodge perpendicular to the projectile's travel direction
        # Travel direction is roughly (-proj_dx, -proj_dy) normalized
        # Perpendicular to travel: (proj_dy, -proj_dx) or (-proj_dy, proj_dx)
        
        if proj_dist < 800:
            perp_dx = proj_dy
            perp_dy = -proj_dx
            mag = math.sqrt(perp_dx**2 + perp_dy**2)
            if mag > 0:
                dodge_dist = 400
                option1_x = my_x + (perp_dx / mag) * dodge_dist
                option1_y = my_y + (perp_dy / mag) * dodge_dist
                option2_x = my_x - (perp_dx / mag) * dodge_dist
                option2_y = my_y - (perp_dy / mag) * dodge_dist

                # Choose option that keeps us in bounds and closer to center of map
                dist1_center = abs(option1_x - 8000) + abs(option1_y - 8000)
                dist2_center = abs(option2_x - 8000) + abs(option2_y - 8000)

                best_x, best_y = (option1_x, option1_y) if dist1_center <= dist2_center else (option2_x, option2_y)

                # Use E (Arcane Shift) to dodge if projectile is very close
                if e_ready and proj_dist < 400:
                    return cast_spell(2, best_y, best_x)
                return move_to(best_y, best_x)

    # 2. LOW HP: Retreat if critically low and enemy isn't lower
    if my_hp_pct < 0.15 and enemy_hp_pct > my_hp_pct + 0.1:
        retreat_x = my_x + (my_x - enemy_x) * 0.5
        retreat_y = my_y + (my_y - enemy_y) * 0.5
        # Parting Q shot if possible
        if q_ready and enemy_dist < 1100:
            return cast_spell(0, enemy_y, enemy_x)
        if e_ready:
            return cast_spell(2, retreat_y, retreat_x)
        return move_to(retreat_y, retreat_x)

    # 3. EXECUTE: Enemy is very low, go all-in
    if enemy_hp_pct < 0.25 and my_hp_pct > 0.1:
        if r_ready and enemy_dist < 5000 and enemy_dist > 1100:
            return cast_spell(3, enemy_y, enemy_x)
        if q_ready and enemy_dist < 1100:
            return cast_spell(0, enemy_y, enemy_x)
        if w_ready and enemy_dist < 950:
            return cast_spell(1, enemy_y, enemy_x)
        if e_ready and enemy_dist > 600 and enemy_dist < 1500:
            # E forward to close gap
            mid_x = (my_x + enemy_x) / 2
            mid_y = (my_y + enemy_y) / 2
            return cast_spell(2, mid_y, mid_x)
        # Chase toward enemy
        return move_to(enemy_y, enemy_x)

    # 4. COMBAT: Use R at long range if available
    if r_ready and enemy_dist < 4000 and enemy_dist > 1200 and my_mp_pct > 0.3:
        # Lead the target: aim slightly ahead
        return cast_spell(3, enemy_y, enemy_x)

    # 5. COMBAT: Use Q aggressively - bread and butter poke
    if q_ready and enemy_dist < 1100 and my_mp_pct > 0.1:
        return cast_spell(0, enemy_y, enemy_x)

    # 6. COMBAT: Use W for extra damage when in range
    if w_ready and enemy_dist < 950 and my_mp_pct > 0.25:
        return cast_spell(1, enemy_y, enemy_x)

    # 7. AUTO ATTACK: When in auto range
    if enemy_dist < 550:
        if q_ready:
            return cast_spell(0, enemy_y, enemy_x)
        # Kite back after auto
        away_x = my_x + (my_x - enemy_x) * 0.3
        away_y = my_y + (my_y - enemy_y) * 0.3
        return move_to(away_y, away_x)

    # 8. APPROACH: Close distance to get into Q range
    # Move DIRECTLY toward enemy position
    optimal_range = 850
    if enemy_dist > optimal_range:
        # Walk toward enemy - use actual enemy position as target
        # Add slight lateral juke to avoid skillshots while approaching
        dx = enemy_x - my_x
        dy = enemy_y - my_y
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            # Normalize direction toward enemy
            nx = dx / dist
            ny = dy / dist
            # Add perpendicular juke component
            juke_amplitude = 150
            juke = math.sin(game_time * 0.008) * juke_amplitude
            perp_x = -ny * juke
            perp_y = nx * juke
            step_size = min(500, enemy_dist - optimal_range + 300)
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
            orbit_dir = 1 if math.sin(game_time * 0.006) > 0 else -1
            orbit_x = my_x + (-ny * orbit_dir) * 300
            orbit_y = my_y + (nx * orbit_dir) * 300
            return move_to(orbit_y, orbit_x)
        return move_to(my_y, my_x)