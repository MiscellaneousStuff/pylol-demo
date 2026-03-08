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
    enemy_dist = math.sqrt(enemy_dx**2 + enemy_dy**2)
    enemy_x = my_x + enemy_dx
    enemy_y = my_y + enemy_dy

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

    # Gather enemy projectiles
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    
    # Find the most threatening projectile (closest one within dodge range)
    closest_proj = None
    closest_proj_dist = 9999
    for p in enemy_projectiles:
        pdist = p["distance_to_me"]
        if pdist < closest_proj_dist and pdist > 10:
            closest_proj_dist = pdist
            closest_proj = p

    # --- PRIORITY 1: Dodge projectiles that are close ---
    # Increased threshold from 250 to 550 to dodge much earlier
    if closest_proj is not None and closest_proj_dist < 550:
        pdx = closest_proj["dx_to_me"]
        pdy = closest_proj["dy_to_me"]
        pdist = closest_proj_dist

        # Calculate perpendicular dodge directions
        perp1_x = pdy
        perp1_y = -pdx
        perp2_x = -pdy
        perp2_y = pdx

        mag = math.sqrt(perp1_x**2 + perp1_y**2)
        if mag > 0:
            perp1_x /= mag
            perp1_y /= mag
            perp2_x /= mag
            perp2_y /= mag

            # Pick dodge direction that moves us away from enemy if we're low HP,
            # otherwise pick more aggressive dodge
            if my_hp_pct < 0.4:
                # Prefer dodge direction that increases distance from enemy
                dot1 = perp1_x * (-enemy_dx) + perp1_y * (-enemy_dy)
                dot2 = perp2_x * (-enemy_dx) + perp2_y * (-enemy_dy)
            else:
                # Prefer dodge direction closer to enemy (aggressive)
                dot1 = perp1_x * enemy_dx + perp1_y * enemy_dy
                dot2 = perp2_x * enemy_dx + perp2_y * enemy_dy

            if dot1 >= dot2:
                dodge_nx, dodge_ny = perp1_x, perp1_y
            else:
                dodge_nx, dodge_ny = perp2_x, perp2_y

            # Use E to dodge if projectile is very close and threatening
            if e_ready and pdist < 200 and my_hp_pct < 0.5:
                e_x = my_x + dodge_nx * 475
                e_y = my_y + dodge_ny * 475
                return cast_spell(2, e_y, e_x)

            dodge_dist = 300
            move_x = my_x + dodge_nx * dodge_dist
            move_y = my_y + dodge_ny * dodge_dist
            return move_to(move_y, move_x)

    # --- PRIORITY 2: Retreat if significantly HP disadvantaged ---
    hp_diff = my_hp_pct - enemy_hp_pct
    if my_hp_pct < 0.35 and hp_diff < -0.15:
        # We're low and enemy is healthier - retreat
        if e_ready and enemy_dist < 700:
            if enemy_dist > 0:
                retreat_x = my_x - (enemy_dx / enemy_dist) * 475
                retreat_y = my_y - (enemy_dy / enemy_dist) * 475
                return cast_spell(2, retreat_y, retreat_x)
        # Just run away
        if enemy_dist > 0:
            retreat_x = my_x - (enemy_dx / enemy_dist) * 500
            retreat_y = my_y - (enemy_dy / enemy_dist) * 500
        else:
            retreat_x = my_x - 500
            retreat_y = my_y - 500
        return move_to(retreat_y, retreat_x)

    # --- PRIORITY 3: Cast spells offensively ---
    # Only engage if no imminent projectile to dodge (handled above)
    
    # R - Execute low HP enemies
    if r_ready and enemy_hp_pct < 0.25 and my_mp_pct > 0.1 and enemy_dist < 3000:
        return cast_spell(3, enemy_y, enemy_x)

    # Q - Primary poke, 1150 range skillshot. Aim directly at enemy.
    if q_ready and enemy_dist < 1050 and my_mp_pct > 0.05:
        # Aim at enemy position - simple direct aim since we can't predict movement
        return cast_spell(0, enemy_y, enemy_x)

    # W - Secondary poke, 950 range
    if w_ready and enemy_dist < 900 and my_mp_pct > 0.15:
        return cast_spell(1, enemy_y, enemy_x)

    # --- PRIORITY 4: Kiting movement ---
    
    if enemy_dist > 0:
        nx = enemy_dx / enemy_dist
        ny = enemy_dy / enemy_dist
    else:
        nx, ny = 1, 0

    # If too far, approach but with lateral movement to be harder to hit
    if enemy_dist > 1000:
        step = min(400, enemy_dist - 750)
        # Add significant lateral juke while approaching
        t = game_time * 0.003
        juke_amount = math.sin(t * 11.0) * 300
        target_x = my_x + nx * step + (-ny) * juke_amount
        target_y = my_y + ny * step + (nx) * juke_amount
        return move_to(target_y, target_x)

    # In combat range: aggressive lateral movement to dodge while staying in range
    # Optimal range ~800 for Q but not too close
    optimal_range = 800
    range_correction = (enemy_dist - optimal_range) * 0.4

    # Sharp, fast lateral jukes - change direction rapidly
    t = game_time * 0.001
    # Use multiple sine waves at different frequencies for unpredictable movement
    lateral = math.sin(t * 17.0) * 200 + math.sin(t * 7.3) * 150
    # Occasionally reverse direction sharply
    if abs(math.sin(t * 23.0)) > 0.85:
        lateral = -lateral * 1.5

    move_x = my_x + nx * range_correction + (-ny) * lateral
    move_y = my_y + ny * range_correction + (nx) * lateral

    return move_to(move_y, move_x)