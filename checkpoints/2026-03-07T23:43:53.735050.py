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

    # Analyze enemy projectiles - detect incoming threats early
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    
    # Check for projectiles heading toward us within dodge range
    # We need to dodge at 600+ range because at 2000 speed, 300 range = 0.15s (too late)
    dangerous_projectiles = []
    for p in enemy_projectiles:
        pdist = p["distance_to_me"]
        if pdist < 700 and pdist > 0:
            # Check if projectile is actually heading toward us (closing distance)
            # A projectile's dx_to_me/dy_to_me points from projectile to us
            # If the projectile is moving toward us, we should dodge
            dangerous_projectiles.append(p)

    # ===== PRIORITY 1: Dodge incoming projectiles =====
    if dangerous_projectiles:
        closest = min(dangerous_projectiles, key=lambda p: p["distance_to_me"])
        pdist = closest["distance_to_me"]
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]
        
        # Perpendicular to the vector from projectile to us
        perp1_x = pdy
        perp1_y = -pdx
        perp2_x = -pdy
        perp2_y = pdx
        
        # Pick direction that also moves slightly away from enemy
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
            
            # Use E to dodge very close projectiles
            if e_ready and pdist < 350:
                e_x = my_x + dodge_nx * 475
                e_y = my_y + dodge_ny * 475
                return cast_spell(2, e_y, e_x)
            
            # Otherwise sidestep - move 300 units perpendicular
            move_x = my_x + dodge_nx * 350
            move_y = my_y + dodge_ny * 350
            return move_to(move_y, move_x)

    # ===== PRIORITY 2: Execute low HP enemy =====
    if r_ready and enemy_hp_pct < 0.25 and enemy_dist < 3000 and my_mp_pct > 0.1:
        return cast_spell(3, enemy_y, enemy_x)

    # ===== PRIORITY 3: Cast Q - bread and butter poke =====
    # Q has 1150 range, cast whenever ready and in range
    if q_ready and enemy_dist < 1100 and my_mp_pct > 0.05:
        # Lead the target - predict where enemy will be
        # Aim directly at enemy for now
        return cast_spell(0, enemy_y, enemy_x)

    # ===== PRIORITY 4: Cast W for extra damage when in range =====
    if w_ready and enemy_dist < 900 and my_mp_pct > 0.15:
        return cast_spell(1, enemy_y, enemy_x)

    # ===== PRIORITY 5: Retreat if very low HP =====
    if my_hp_pct < 0.20 and enemy_hp_pct > my_hp_pct + 0.10:
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

    # ===== PRIORITY 6: Chase low HP enemy =====
    if enemy_hp_pct < 0.25 and my_hp_pct > 0.20:
        if e_ready and enemy_dist > 700 and enemy_dist < 1800:
            dx = enemy_x - my_x
            dy = enemy_y - my_y
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 0:
                e_x = my_x + (dx / dist) * 475
                e_y = my_y + (dy / dist) * 475
                return cast_spell(2, e_y, e_x)
        return move_to(enemy_y, enemy_x)

    # ===== PRIORITY 7: Position and kite - ALWAYS BE MOVING =====
    # Optimal range: ~850 (inside Q range of 1150, outside danger zone)
    optimal_range = 850
    
    dx = enemy_x - my_x
    dy = enemy_y - my_y
    dist = math.sqrt(dx**2 + dy**2)
    if dist == 0:
        dist = 1
    nx = dx / dist
    ny = dy / dist

    if enemy_dist > optimal_range + 200:
        # Too far - approach enemy but with lateral movement to dodge
        # Alternate side every ~0.5 seconds for unpredictable movement
        juke_dir = 1 if (int(game_time * 0.005) % 2 == 0) else -1
        perp_x = -ny * juke_dir * 250
        perp_y = nx * juke_dir * 250
        step = min(500, enemy_dist - optimal_range)
        target_x = my_x + nx * step + perp_x
        target_y = my_y + ny * step + perp_y
        return move_to(target_y, target_x)
    elif enemy_dist < 500:
        # Too close - kite back while moving laterally
        juke_dir = 1 if (int(game_time * 0.004) % 2 == 0) else -1
        back_x = my_x - nx * 300 + (-ny * juke_dir * 200)
        back_y = my_y - ny * 300 + (nx * juke_dir * 200)
        return move_to(back_y, back_x)
    else:
        # Good range - orbit rapidly to dodge skillshots while staying in Q range
        # Change direction frequently to be unpredictable
        orbit_dir = 1 if (int(game_time * 0.003) % 2 == 0) else -1
        orbit_x = my_x + (-ny * orbit_dir) * 350
        orbit_y = my_y + (nx * orbit_dir) * 350
        return move_to(orbit_y, orbit_x)