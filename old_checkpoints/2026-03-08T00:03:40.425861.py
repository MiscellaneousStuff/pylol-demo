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

    # Analyze enemy projectiles heading toward us
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    
    # Only dodge projectiles that are actually close and dangerous
    dangerous_projectiles = []
    for p in enemy_projectiles:
        pdist = p["distance_to_me"]
        # Only dodge when projectile is genuinely close and threatening
        if pdist < 500 and pdist > 50:
            dangerous_projectiles.append(p)

    # ===== PRIORITY 1: Dodge very close projectiles =====
    if dangerous_projectiles:
        closest = min(dangerous_projectiles, key=lambda p: p["distance_to_me"])
        pdist = closest["distance_to_me"]
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]
        
        # Perpendicular dodge
        perp1_x = pdy
        perp1_y = -pdx
        perp2_x = -pdy
        perp2_y = pdx
        
        # Pick perpendicular direction that keeps us closer to enemy (don't run away)
        dot1 = perp1_x * enemy_dx + perp1_y * enemy_dy
        dot2 = perp2_x * enemy_dx + perp2_y * enemy_dy
        
        if dot1 >= dot2:
            dodge_nx, dodge_ny = perp1_x, perp1_y
        else:
            dodge_nx, dodge_ny = perp2_x, perp2_y
        
        mag = math.sqrt(dodge_nx**2 + dodge_ny**2)
        if mag > 0:
            dodge_nx /= mag
            dodge_ny /= mag
            
            # Use E to dodge very close projectiles only if really needed
            if e_ready and pdist < 250:
                e_x = my_x + dodge_nx * 475
                e_y = my_y + dodge_ny * 475
                return cast_spell(2, e_y, e_x)
            
            # Sidestep
            move_x = my_x + dodge_nx * 300
            move_y = my_y + dodge_ny * 300
            return move_to(move_y, move_x)

    # ===== PRIORITY 2: Execute low HP enemy with R =====
    if r_ready and enemy_hp_pct < 0.25 and enemy_dist < 3000 and my_mp_pct > 0.1:
        return cast_spell(3, enemy_y, enemy_x)

    # ===== PRIORITY 3: Cast Q when in range - THIS IS THE BREAD AND BUTTER =====
    if q_ready and enemy_dist < 1100 and my_mp_pct > 0.05:
        # Lead the target slightly - aim a bit ahead of enemy position
        # For now aim directly, Q is fast enough
        return cast_spell(0, enemy_y, enemy_x)

    # ===== PRIORITY 4: Cast W when in range for extra damage =====
    if w_ready and enemy_dist < 900 and my_mp_pct > 0.15:
        return cast_spell(1, enemy_y, enemy_x)

    # ===== PRIORITY 5: Auto attack when in auto range =====
    if enemy_dist < 600:
        # Auto attack the enemy
        return cast_spell(0, enemy_y, enemy_x) if q_ready else move_to(enemy_y, enemy_x)

    # ===== PRIORITY 6: Retreat if very low HP =====
    if my_hp_pct < 0.15 and enemy_hp_pct > my_hp_pct + 0.15:
        if e_ready:
            rdx = my_x - enemy_x
            rdy = my_y - enemy_y
            rdist = math.sqrt(rdx**2 + rdy**2)
            if rdist > 0:
                retreat_x = my_x + (rdx / rdist) * 475
                retreat_y = my_y + (rdy / rdist) * 475
                return cast_spell(2, retreat_y, retreat_x)
        retreat_x = my_x + (my_x - enemy_x) * 0.5
        retreat_y = my_y + (my_y - enemy_y) * 0.5
        return move_to(retreat_y, retreat_x)

    # ===== PRIORITY 7: AGGRESSIVELY CLOSE DISTANCE to get into Q range =====
    # The main problem: we need to actually get within 1100 range to use Q
    # Move DIRECTLY toward the enemy with urgency
    
    if enemy_dist > 1050:
        # We are too far - rush toward enemy aggressively
        # Move directly at the enemy, with slight lateral jitter to avoid skillshots
        dx = enemy_x - my_x
        dy = enemy_y - my_y
        dist = math.sqrt(dx**2 + dy**2)
        if dist == 0:
            dist = 1
        nx = dx / dist
        ny = dy / dist
        
        # Add small perpendicular jitter to make us harder to hit while approaching
        juke_dir = 1 if (int(game_time * 0.004) % 2 == 0) else -1
        perp_x = -ny * juke_dir * 100
        perp_y = nx * juke_dir * 100
        
        # Move a large step toward enemy - be aggressive
        step = min(800, enemy_dist - 800)
        target_x = my_x + nx * step + perp_x
        target_y = my_y + ny * step + perp_y
        return move_to(target_y, target_x)
    
    # ===== PRIORITY 8: In range - orbit and wait for cooldowns =====
    # We're in Q range but Q is on cooldown, orbit to dodge while staying in range
    dx = enemy_x - my_x
    dy = enemy_y - my_y
    dist = math.sqrt(dx**2 + dy**2)
    if dist == 0:
        dist = 1
    nx = dx / dist
    ny = dy / dist
    
    # Orbit at ~900 range (comfortable Q range)
    optimal_range = 900
    
    # Rapid orbit direction changes to be unpredictable
    orbit_dir = 1 if (int(game_time * 0.003) % 2 == 0) else -1
    
    # Also adjust distance toward optimal range
    range_adjust = (enemy_dist - optimal_range) * 0.3
    
    orbit_x = my_x + nx * range_adjust + (-ny * orbit_dir) * 300
    orbit_y = my_y + ny * range_adjust + (nx * orbit_dir) * 300
    return move_to(orbit_y, orbit_x)