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

    # Normalize direction to enemy
    if enemy_dist > 0:
        nx = enemy_dx / enemy_dist
        ny = enemy_dy / enemy_dist
    else:
        nx, ny = 1, 0

    # --- Detect threatening projectiles with wider range ---
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    truly_threatening = None
    min_threat_dist = 9999

    for p in enemy_projectiles:
        pdx = p["dx_to_me"]
        pdy = p["dy_to_me"]
        pdist = math.sqrt(pdx**2 + pdy**2)

        # Wider detection: 15 to 500 units
        if pdist < 15 or pdist > 500:
            continue

        # Consider anything within 350 units as threatening
        if pdist < 350:
            if pdist < min_threat_dist:
                min_threat_dist = pdist
                truly_threatening = p

    # --- PRIORITY 0: Dodge incoming projectiles FIRST ---
    if truly_threatening is not None and min_threat_dist < 350:
        pdx = truly_threatening["dx_to_me"]
        pdy = truly_threatening["dy_to_me"]

        # Perpendicular dodge direction
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

            # Choose dodge direction: prefer staying at good range
            dot1 = perp1_x * (-nx) + perp1_y * (-ny)
            dot2 = perp2_x * (-nx) + perp2_y * (-ny)

            if my_hp_pct < 0.35:
                # Low HP - dodge away from enemy
                if dot1 >= dot2:
                    dodge_nx, dodge_ny = perp1_x, perp1_y
                else:
                    dodge_nx, dodge_ny = perp2_x, perp2_y
            else:
                # Healthy - dodge sideways (minimize distance change)
                if abs(dot1) <= abs(dot2):
                    dodge_nx, dodge_ny = perp1_x, perp1_y
                else:
                    dodge_nx, dodge_ny = perp2_x, perp2_y

            # Use E to dodge if projectile is very close and we're in danger
            if e_ready and min_threat_dist < 150 and my_hp_pct < 0.4:
                e_x = my_x + dodge_nx * 475
                e_y = my_y + dodge_ny * 475
                return cast_spell(2, e_y, e_x)

            dodge_dist = 320
            move_x = my_x + dodge_nx * dodge_dist
            move_y = my_y + dodge_ny * dodge_dist
            return move_to(move_y, move_x)

    # --- PRIORITY 1: Cast offensive spells ---
    # Q - Mystic Shot (~1150 range, 2000 speed projectile)
    # Lead the target: predict where enemy will be
    if q_ready and enemy_dist < 1000 and my_mp_pct > 0.05:
        # Lead prediction: assume enemy moves perpendicular or continues current direction
        # Projectile travel time = distance / 2000
        travel_time = enemy_dist / 2000.0
        # Estimate enemy movement: lead by a fixed offset in the direction they might be moving
        # Since we don't have velocity data, use a small lead based on game time oscillation
        # But mainly aim slightly ahead in the direction from their base toward us
        lead_dist = travel_time * 300  # assume ~300 units/sec movement
        # Lead perpendicular to the line between us for uncertainty
        t = game_time * 0.001
        lead_angle = math.sin(t * 5.0) * 0.3  # slight angle variation
        
        # Rotate the direction vector by lead_angle
        cos_a = math.cos(lead_angle)
        sin_a = math.sin(lead_angle)
        lead_nx = nx * cos_a - ny * sin_a
        lead_ny = nx * sin_a + ny * cos_a
        
        aim_x = enemy_x + lead_nx * lead_dist
        aim_y = enemy_y + lead_ny * lead_dist
        return cast_spell(0, aim_y, aim_x)

    # W - Essence Flux (~950 range, 1600 speed)
    if w_ready and enemy_dist < 850 and my_mp_pct > 0.15:
        # Similar lead but W is slower
        travel_time = enemy_dist / 1600.0
        lead_dist = travel_time * 250
        aim_x = enemy_x + nx * lead_dist
        aim_y = enemy_y + ny * lead_dist
        return cast_spell(1, aim_y, aim_x)

    # R - Trueshot Barrage for execute
    if r_ready and enemy_hp_pct < 0.3 and enemy_dist < 2500 and my_mp_pct > 0.1:
        # R is a wide beam, aim directly
        return cast_spell(3, enemy_y, enemy_x)

    # --- PRIORITY 2: Retreat if very low HP ---
    if my_hp_pct < 0.2 and my_hp_pct < enemy_hp_pct - 0.1:
        if e_ready and enemy_dist < 700:
            retreat_x = my_x - nx * 475
            retreat_y = my_y - ny * 475
            return cast_spell(2, retreat_y, retreat_x)
        retreat_x = my_x - nx * 500
        retreat_y = my_y - ny * 500
        return move_to(retreat_y, retreat_x)

    # --- PRIORITY 3: Kite / Positioning ---
    # After casting spells, move to maintain spacing and avoid being predictable
    # Optimal range: ~700 (inside Q range of 1050 but outside enemy melee/easy skillshot)
    
    # If too far, approach with zigzag
    if enemy_dist > 950:
        step = min(400, enemy_dist - 650)
        t = game_time * 0.001
        juke = math.sin(t * 19.0) * 200
        target_x = my_x + nx * step + (-ny) * juke
        target_y = my_y + ny * step + (nx) * juke
        return move_to(target_y, target_x)

    # In combat range: aggressive lateral movement with sharp direction changes
    # This makes us harder to hit while staying in spell range
    optimal_range = 650
    range_correction = (enemy_dist - optimal_range) * 0.35

    t = game_time * 0.001
    # Sharp triangular wave for unpredictable strafing
    phase = (t * 13.0) % (2 * math.pi)
    if phase < math.pi * 0.4:
        lateral = 300
    elif phase < math.pi * 0.8:
        lateral = -300
    elif phase < math.pi * 1.2:
        lateral = 200
    elif phase < math.pi * 1.6:
        lateral = -200
    else:
        lateral = 280

    # Add high-frequency jitter
    lateral += math.sin(t * 37.0) * 80

    move_x = my_x + nx * range_correction + (-ny) * lateral
    move_y = my_y + ny * range_correction + (nx) * lateral

    return move_to(move_y, move_x)