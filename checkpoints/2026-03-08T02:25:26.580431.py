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

    # Gather enemy projectiles - only those actually heading toward us
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]

    # Filter for projectiles that are actually approaching us and close
    # A projectile is approaching if the dot product of its velocity direction
    # and the vector FROM projectile TO us is positive
    truly_threatening = None
    min_threat_dist = 9999
    for p in enemy_projectiles:
        pdx = p["dx_to_me"]  # vector from me to projectile
        pdy = p["dy_to_me"]
        pdist = math.sqrt(pdx**2 + pdy**2)
        
        if pdist < 10 or pdist > 400:
            continue
        
        # We need to check if projectile is moving toward us
        # dx_to_me is projectile position relative to me
        # If projectile is at pdx,pdy from me, and it's an enemy skillshot,
        # it's threatening if it's close and getting closer
        # For Ezreal Q - it's a line skillshot, check if we're roughly in its path
        # Simple heuristic: if the projectile is within 400 units and
        # the angle between (projectile->me) and projectile travel direction is small
        
        # Since we don't have velocity components directly, use a simpler approach:
        # Only consider very close projectiles (< 250 units) as immediate threats
        if pdist < 250:
            if pdist < min_threat_dist:
                min_threat_dist = pdist
                truly_threatening = p

    # --- PRIORITY 1: Cast spells offensively FIRST (this was the main bug) ---
    # Q - Primary damage, ~1150 range. Cast whenever ready and in range
    if q_ready and enemy_dist < 1050 and my_mp_pct > 0.05:
        # Lead the target slightly
        if enemy_dist > 0:
            # Aim directly at enemy with slight randomization
            t = game_time * 0.001
            aim_offset_x = math.sin(t * 7.0) * 40
            aim_offset_y = math.cos(t * 7.0) * 40
            return cast_spell(0, enemy_y + aim_offset_y, enemy_x + aim_offset_x)

    # W - Secondary poke, ~950 range
    if w_ready and enemy_dist < 900 and my_mp_pct > 0.15:
        return cast_spell(1, enemy_y, enemy_x)

    # R - Execute low HP enemies
    if r_ready and enemy_hp_pct < 0.25 and enemy_dist < 3000 and my_mp_pct > 0.1:
        return cast_spell(3, enemy_y, enemy_x)

    # --- PRIORITY 2: Dodge truly threatening projectiles ---
    if truly_threatening is not None and min_threat_dist < 250:
        pdx = truly_threatening["dx_to_me"]
        pdy = truly_threatening["dy_to_me"]

        # Perpendicular dodge
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

            # Pick direction that keeps us at good range from enemy
            dot1 = perp1_x * (-enemy_dx) + perp1_y * (-enemy_dy)
            dot2 = perp2_x * (-enemy_dx) + perp2_y * (-enemy_dy)

            if my_hp_pct < 0.3:
                # Low HP: dodge away from enemy
                if dot1 >= dot2:
                    dodge_nx, dodge_ny = perp1_x, perp1_y
                else:
                    dodge_nx, dodge_ny = perp2_x, perp2_y
            else:
                # Healthy: dodge toward favorable position
                if dot1 <= dot2:
                    dodge_nx, dodge_ny = perp1_x, perp1_y
                else:
                    dodge_nx, dodge_ny = perp2_x, perp2_y

            # Use E for emergency dodge if very close and low HP
            if e_ready and min_threat_dist < 120 and my_hp_pct < 0.35:
                e_x = my_x + dodge_nx * 475
                e_y = my_y + dodge_ny * 475
                return cast_spell(2, e_y, e_x)

            dodge_dist = 280
            move_x = my_x + dodge_nx * dodge_dist
            move_y = my_y + dodge_ny * dodge_dist
            return move_to(move_y, move_x)

    # --- PRIORITY 3: Retreat if very low HP ---
    if my_hp_pct < 0.2 and my_hp_pct < enemy_hp_pct - 0.15:
        if e_ready and enemy_dist < 600:
            if enemy_dist > 0:
                retreat_x = my_x - (enemy_dx / enemy_dist) * 475
                retreat_y = my_y - (enemy_dy / enemy_dist) * 475
                return cast_spell(2, retreat_y, retreat_x)
        if enemy_dist > 0:
            retreat_x = my_x - (enemy_dx / enemy_dist) * 500
            retreat_y = my_y - (enemy_dy / enemy_dist) * 500
        else:
            retreat_x = my_x - 500
            retreat_y = my_y - 500
        return move_to(retreat_y, retreat_x)

    # --- PRIORITY 4: Positioning with constant movement ---
    if enemy_dist > 0:
        nx = enemy_dx / enemy_dist
        ny = enemy_dy / enemy_dist
    else:
        nx, ny = 1, 0

    # If too far, close distance aggressively to get into Q range
    if enemy_dist > 1000:
        step = min(500, enemy_dist - 700)
        # Zigzag while approaching
        t = game_time * 0.003
        juke = math.sin(t * 17.0) * 250
        target_x = my_x + nx * step + (-ny) * juke
        target_y = my_y + ny * step + (nx) * juke
        return move_to(target_y, target_x)

    # In combat range: maintain ~650 range with aggressive lateral movement
    # This ensures we're always in Q range (1050) while staying mobile
    optimal_range = 650
    range_correction = (enemy_dist - optimal_range) * 0.4

    # Rapid direction changes - never stand still
    t = game_time * 0.001
    # Use sharp triangular wave for quick direction changes
    phase = (t * 15.0) % (2 * math.pi)
    if phase < math.pi:
        lateral = 250
    else:
        lateral = -250
    
    # Add some randomness via higher frequency
    lateral += math.sin(t * 31.0) * 100

    move_x = my_x + nx * range_correction + (-ny) * lateral
    move_y = my_y + ny * range_correction + (nx) * lateral

    return move_to(move_y, move_x)