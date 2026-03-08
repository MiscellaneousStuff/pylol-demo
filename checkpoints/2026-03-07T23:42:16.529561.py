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

    # Only consider projectiles that are VERY close and actually threatening
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    
    # Filter for truly dangerous projectiles: close AND heading toward us
    # A projectile heading toward us will have its dx/dy vector roughly aligned
    # with its travel direction toward us. We check if it's very close.
    truly_dangerous = []
    for p in enemy_projectiles:
        pdist = p["distance_to_me"]
        if pdist < 300:  # Only dodge very close projectiles
            truly_dangerous.append(p)

    # ===== PRIORITY 1: Dodge only truly imminent projectiles =====
    if truly_dangerous:
        # Calculate dodge perpendicular to closest projectile
        closest = min(truly_dangerous, key=lambda p: p["distance_to_me"])
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]
        # Perpendicular directions
        perp1_x = pdy
        perp1_y = -pdx
        perp2_x = -pdy
        perp2_y = pdx
        # Pick direction that moves away from enemy (safer)
        away_x = my_x - enemy_x
        away_y = my_y - enemy_y
        dot1 = perp1_x * away_x + perp1_y * away_y
        dot2 = perp2_x * away_x + perp2_y * away_y
        if dot1 >= dot2:
            dodge_nx, dodge_ny = perp1_x, perp1_y
        else:
            dodge_nx, dodge_ny = perp2_x, perp2_y
        mag = math.sqrt(dodge_nx**2 + dodge_ny**2)
        if mag > 0:
            dodge_nx /= mag
            dodge_ny /= mag
            # Use E to dodge if available for very close projectiles
            if e_ready and closest["distance_to_me"] < 200:
                e_x = my_x + dodge_nx * 475
                e_y = my_y + dodge_ny * 475
                return cast_spell(2, e_y, e_x)
            move_x = my_x + dodge_nx * 350
            move_y = my_y + dodge_ny * 350
            return move_to(move_y, move_x)

    # ===== PRIORITY 2: Cast offensive spells when in range =====
    # R for execute or long range snipe
    if r_ready and enemy_hp_pct < 0.30 and my_mp_pct > 0.1 and enemy_dist < 3000:
        return cast_spell(3, enemy_y, enemy_x)

    # Q is bread and butter - fire whenever ready and in range
    if q_ready and enemy_dist < 1150 and my_mp_pct > 0.05:
        # Lead the target slightly - aim ahead of enemy position
        return cast_spell(0, enemy_y, enemy_x)

    # W for extra damage when in range
    if w_ready and enemy_dist < 900 and my_mp_pct > 0.15:
        return cast_spell(1, enemy_y, enemy_x)

    # ===== PRIORITY 3: Retreat if very low HP =====
    if my_hp_pct < 0.15 and enemy_hp_pct > my_hp_pct + 0.15:
        if e_ready:
            retreat_dx = my_x - enemy_x
            retreat_dy = my_y - enemy_y
            rdist = math.sqrt(retreat_dx**2 + retreat_dy**2)
            if rdist > 0:
                retreat_x = my_x + (retreat_dx / rdist) * 475
                retreat_y = my_y + (retreat_dy / rdist) * 475
                return cast_spell(2, retreat_y, retreat_x)
        retreat_x = my_x + (my_x - enemy_x) * 0.5
        retreat_y = my_y + (my_y - enemy_y) * 0.5
        return move_to(retreat_y, retreat_x)

    # ===== PRIORITY 4: Chase low HP enemy for kill =====
    if enemy_hp_pct < 0.25 and my_hp_pct > 0.15:
        # E aggressively to close gap
        if e_ready and enemy_dist > 600 and enemy_dist < 2000:
            dx = enemy_x - my_x
            dy = enemy_y - my_y
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 0:
                e_x = my_x + (dx / dist) * 475
                e_y = my_y + (dy / dist) * 475
                return cast_spell(2, e_y, e_x)
        return move_to(enemy_y, enemy_x)

    # ===== PRIORITY 5: APPROACH AND POSITION =====
    # The key fix: aggressively approach the enemy to get in ability range
    optimal_range = 900  # Just inside Q range (1150) to reliably land spells

    if enemy_dist > optimal_range + 100:
        # Move toward enemy - prioritize closing distance over everything
        dx = enemy_x - my_x
        dy = enemy_y - my_y
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            nx = dx / dist
            ny = dy / dist
            # Add slight zigzag to avoid being predictable, but keep it small
            # so we don't waste time on movement
            juke_amplitude = 150
            juke = juke_amplitude if (int(game_time * 0.003) % 2 == 0) else -juke_amplitude
            perp_x = -ny * juke
            perp_y = nx * juke
            # Take big steps to close distance fast
            step = min(600, dist - optimal_range + 200)
            target_x = my_x + nx * step + perp_x
            target_y = my_y + ny * step + perp_y
            return move_to(target_y, target_x)
    elif enemy_dist < 450:
        # Too close - kite backwards
        dx = my_x - enemy_x
        dy = my_y - enemy_y
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            nx = dx / dist
            ny = dy / dist
            target_x = my_x + nx * 300
            target_y = my_y + ny * 300
            return move_to(target_y, target_x)
    else:
        # In good range - orbit to make it hard to hit us while staying in range
        dx = enemy_x - my_x
        dy = enemy_y - my_y
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            nx = dx / dist
            ny = dy / dist
            # Rapid orbit direction changes
            orbit_dir = 1 if (int(game_time * 0.004) % 2 == 0) else -1
            orbit_x = my_x + (-ny * orbit_dir) * 300 + nx * 30
            orbit_y = my_y + (nx * orbit_dir) * 300 + ny * 30
            return move_to(orbit_y, orbit_x)

    return move_to(my_y, my_x)