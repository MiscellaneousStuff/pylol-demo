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

    def move_to(target_y, target_x):
        return (1, [target_y, target_x])

    def cast_spell(spell_idx, target_y, target_x):
        return (2, [[spell_idx], [target_y, target_x]])

    def auto_attack(target_y, target_x):
        return (2, [[0], [target_y, target_x]])

    game_time = observation.get("game_time", 0)

    # 1. DODGE: Only dodge projectiles that are actually dangerously close
    nearby_projectiles = [p for p in observation["projectiles"]
                         if p["my_team"] == 0 and p["distance_to_me"] < 450]

    if nearby_projectiles:
        closest_proj = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        proj_dx = closest_proj["dx_to_me"]
        proj_dy = closest_proj["dy_to_me"]
        proj_dist = closest_proj["distance_to_me"]

        if proj_dist < 400:
            # Dodge perpendicular to projectile travel direction
            perp_dx = -proj_dy
            perp_dy = proj_dx
            mag = math.sqrt(perp_dx**2 + perp_dy**2)
            if mag > 0:
                dodge_dist = 300
                option1_x = my_x + (perp_dx / mag) * dodge_dist
                option1_y = my_y + (perp_dy / mag) * dodge_dist
                option2_x = my_x - (perp_dx / mag) * dodge_dist
                option2_y = my_y - (perp_dy / mag) * dodge_dist

                # Choose option that keeps us closer to enemy (aggressive dodge)
                dist1_to_enemy = math.sqrt((option1_x - enemy_x)**2 + (option1_y - enemy_y)**2)
                dist2_to_enemy = math.sqrt((option2_x - enemy_x)**2 + (option2_y - enemy_y)**2)

                if dist1_to_enemy <= dist2_to_enemy:
                    if e_ready and proj_dist < 200:
                        return cast_spell(2, option1_y, option1_x)
                    return move_to(option1_y, option1_x)
                else:
                    if e_ready and proj_dist < 200:
                        return cast_spell(2, option2_y, option2_x)
                    return move_to(option2_y, option2_x)

    # 2. LOW HP: Retreat if critically low and enemy isn't lower
    if my_hp_pct < 0.2 and enemy_hp_pct > my_hp_pct + 0.1:
        retreat_angle = math.atan2(base_y - my_y, base_x - my_x)
        retreat_x = my_x + math.cos(retreat_angle) * 500
        retreat_y = my_y + math.sin(retreat_angle) * 500
        # Parting Q shot if possible
        if q_ready and enemy_dist < 1100:
            return cast_spell(0, enemy_y, enemy_x)
        return move_to(retreat_y, retreat_x)

    # 3. EXECUTE: Enemy is very low, go all-in
    if enemy_hp_pct < 0.2 and enemy_dist < 1200:
        if r_ready and enemy_dist < 3000:
            return cast_spell(3, enemy_y, enemy_x)
        if q_ready and enemy_dist < 1100:
            return cast_spell(0, enemy_y, enemy_x)
        if w_ready and enemy_dist < 1000:
            return cast_spell(1, enemy_y, enemy_x)
        if e_ready and enemy_dist > 600:
            # E forward to close gap for the kill
            e_x = my_x + enemy_dx * 0.4
            e_y = my_y + enemy_dy * 0.4
            return cast_spell(2, e_y, e_x)
        # Chase
        chase_x = my_x + enemy_dx * 0.7
        chase_y = my_y + enemy_dy * 0.7
        return move_to(chase_y, chase_x)

    # 4. COMBAT: Use R at long range if available and enemy is in sight
    if r_ready and enemy_dist < 2500 and enemy_dist > 1100 and my_mp_pct > 0.3:
        return cast_spell(3, enemy_y, enemy_x)

    # 5. COMBAT: Use Q aggressively - this is our bread and butter poke
    if q_ready and enemy_dist < 1100 and my_mp_pct > 0.1:
        # Lead the target slightly based on direction
        lead_factor = 0.15
        target_x = enemy_x + enemy_dx * lead_factor
        target_y = enemy_y + enemy_dy * lead_factor
        return cast_spell(0, enemy_y, enemy_x)

    # 6. COMBAT: Use W for extra damage when in range
    if w_ready and enemy_dist < 950 and my_mp_pct > 0.25:
        return cast_spell(1, enemy_y, enemy_x)

    # 7. AUTO ATTACK: When in auto range, auto attack the enemy
    if enemy_dist < 550:
        # Kite: auto then step back
        # If Q is on cooldown and we're in auto range, auto attack
        # Then reposition
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        # Step slightly back after auto
        kite_angle = angle_to_enemy + math.pi
        kite_x = my_x + math.cos(kite_angle) * 150
        kite_y = my_y + math.sin(kite_angle) * 150
        # Auto attack enemy position
        return cast_spell(0, enemy_y, enemy_x) if q_ready else move_to(kite_y, kite_x)

    # 8. APPROACH: Close distance to get into Q range (1100)
    # This is the KEY fix - we need to actually walk toward the enemy
    optimal_q_range = 900  # Sweet spot: close enough to Q, far enough to dodge

    if enemy_dist > optimal_q_range:
        # Walk directly toward enemy with slight lateral offset to be harder to hit
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        # Small lateral juke while approaching
        juke = math.sin(game_time * 0.005) * 0.3
        approach_angle = angle_to_enemy + juke
        # Move aggressively toward enemy
        step_size = min(400, enemy_dist - optimal_q_range + 200)
        approach_x = my_x + math.cos(approach_angle) * step_size
        approach_y = my_y + math.sin(approach_angle) * step_size
        return move_to(approach_y, approach_x)
    else:
        # In good range - orbit to dodge while waiting for cooldowns
        angle_to_enemy = math.atan2(enemy_dy, enemy_dx)
        # Alternate orbit direction to be unpredictable
        orbit_dir = 1 if math.sin(game_time * 0.004) > 0 else -1
        orbit_angle = angle_to_enemy + (math.pi / 2) * orbit_dir
        orbit_x = my_x + math.cos(orbit_angle) * 250
        orbit_y = my_y + math.sin(orbit_angle) * 250
        return move_to(orbit_y, orbit_x)