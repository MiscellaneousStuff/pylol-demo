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

    # Track state for alternating attack/move via game_time
    # Use a simple frame-based approach: cast spell, then move, then cast, etc.
    # We want to kite: spell -> move -> spell -> move
    
    # Check for extremely close enemy projectiles that we MUST dodge
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    imminent_threat = None
    for p in enemy_projectiles:
        pdist = p["distance_to_me"]
        if pdist < 250 and pdist > 20:
            if imminent_threat is None or pdist < imminent_threat["distance_to_me"]:
                imminent_threat = p

    # If a projectile is EXTREMELY close, dodge with E or sidestep
    if imminent_threat is not None:
        pdx = imminent_threat["dx_to_me"]
        pdy = imminent_threat["dy_to_me"]
        pdist = imminent_threat["distance_to_me"]
        
        # Perpendicular dodge
        perp1_x = pdy
        perp1_y = -pdx
        perp2_x = -pdy
        perp2_y = pdx
        
        # Pick direction closer to enemy (aggressive dodge)
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
            
            # Use E for very close projectiles if HP is low
            if e_ready and pdist < 150 and my_hp_pct < 0.5:
                e_x = my_x + dodge_nx * 475
                e_y = my_y + dodge_ny * 475
                return cast_spell(2, e_y, e_x)
            
            move_x = my_x + dodge_nx * 350
            move_y = my_y + dodge_ny * 350
            return move_to(move_y, move_x)

    # ===== ATTACK PHASE: Use spells aggressively =====
    
    # Lead the target: predict where enemy is moving
    # Simple lead: aim slightly ahead in the direction enemy appears to be moving
    # Since we don't have velocity, aim at enemy position with slight offset
    # Use a small random-ish offset based on game_time to vary aim
    lead_offset = 80  # Small lead amount
    # Vary lead direction to be unpredictable
    lead_angle = (game_time * 0.007) % (2 * math.pi)
    lead_x = enemy_x + math.cos(lead_angle) * lead_offset
    lead_y = enemy_y + math.sin(lead_angle) * lead_offset

    # Q - Primary damage, 1150 range, cast whenever ready
    if q_ready and enemy_dist < 1150 and my_mp_pct > 0.05:
        return cast_spell(0, lead_y, lead_x)

    # W - Secondary poke, 950 range
    if w_ready and enemy_dist < 950 and my_mp_pct > 0.15:
        return cast_spell(1, lead_y, lead_x)

    # R - Execute low HP enemies from any range
    if r_ready and enemy_hp_pct < 0.25 and my_mp_pct > 0.1 and enemy_dist < 3000:
        return cast_spell(3, enemy_y, enemy_x)

    # ===== LOW HP: Retreat if very low =====
    if my_hp_pct < 0.15 and enemy_hp_pct > my_hp_pct + 0.15:
        if e_ready and enemy_dist < 600:
            if enemy_dist > 0:
                retreat_x = my_x - (enemy_dx / enemy_dist) * 475
                retreat_y = my_y - (enemy_dy / enemy_dist) * 475
                return cast_spell(2, retreat_y, retreat_x)
        retreat_x = my_x - enemy_dx * 0.5
        retreat_y = my_y - enemy_dy * 0.5
        return move_to(retreat_y, retreat_x)

    # ===== MOVEMENT PHASE: Kite and position while spells are on cooldown =====
    
    # If we're too far, close the distance aggressively
    if enemy_dist > 1050:
        if enemy_dist > 0:
            nx = enemy_dx / enemy_dist
            ny = enemy_dy / enemy_dist
        else:
            nx, ny = 0, 0
        
        # Zigzag approach - change direction more frequently for unpredictability
        juke_phase = math.sin(game_time * 0.012) 
        perp_x = -ny * juke_phase * 200
        perp_y = nx * juke_phase * 200
        
        step = min(600, enemy_dist - 700)
        target_x = my_x + nx * step + perp_x
        target_y = my_y + ny * step + perp_y
        return move_to(target_y, target_x)

    # Optimal kiting range: stay at ~800-900 for Q range but dodge-able
    # Move erratically while maintaining range
    if enemy_dist > 0:
        nx = enemy_dx / enemy_dist
        ny = enemy_dy / enemy_dist
    else:
        nx, ny = 1, 0

    # Target range of ~850 units (comfortable Q range with room to dodge)
    optimal_range = 850
    range_diff = enemy_dist - optimal_range
    
    # Erratic lateral movement - use sine waves with different frequencies
    # to create unpredictable movement patterns that are hard to predict
    t = game_time * 0.001
    lateral_amount = math.sin(t * 7.3) * 250 + math.sin(t * 13.1) * 150
    
    # Move toward/away from optimal range + lateral juke
    move_x = my_x + nx * range_diff * 0.5 + (-ny) * lateral_amount
    move_y = my_y + ny * range_diff * 0.5 + (nx) * lateral_amount
    
    return move_to(move_y, move_x)