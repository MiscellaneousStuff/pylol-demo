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

    if enemy_dist > 0:
        nx = enemy_dx / enemy_dist
        ny = enemy_dy / enemy_dist
    else:
        nx, ny = 1, 0

    def move_to(target_y, target_x):
        target_x = max(0, min(16000, target_x))
        target_y = max(0, min(16000, target_y))
        return (1, [target_y, target_x])

    def cast_spell(spell_idx, target_y, target_x):
        target_x = max(0, min(16000, target_x))
        target_y = max(0, min(16000, target_y))
        return (2, [[spell_idx], [target_y, target_x]])

    # --- Detect truly threatening projectiles (approaching us) ---
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    threatening_proj = None
    min_threat_dist = 9999

    for p in enemy_projectiles:
        pdx = p["dx_to_me"]
        pdy = p["dy_to_me"]
        pdist = math.sqrt(pdx**2 + pdy**2)

        if pdist < 15 or pdist > 600:
            continue

        # Check if projectile is actually approaching us
        # A projectile moving toward us: its position vector (dx,dy) and its implicit
        # velocity should point in roughly opposite directions
        # If the projectile is close and getting closer, it's threatening
        # Simple heuristic: projectile within 300 units is dangerous
        if pdist < 300:
            if pdist < min_threat_dist:
                min_threat_dist = pdist
                threatening_proj = p

    # --- PRIORITY 0: ALWAYS cast Q when ready and enemy in range ---
    # Q is Ezreal's primary damage. Cast it BEFORE dodging since it's quick.
    # Only skip if a projectile is EXTREMELY close (< 150 units)
    cast_q_first = q_ready and enemy_dist < 1050 and my_mp_pct > 0.05
    must_dodge_now = threatening_proj is not None and min_threat_dist < 150

    if cast_q_first and not must_dodge_now:
        # Lead the target based on distance
        travel_time = enemy_dist / 2000.0
        lead_dist = travel_time * 280
        # Aim directly at enemy with slight lead toward us (they tend to approach)
        aim_x = enemy_x + nx * lead_dist * 0.3
        aim_y = enemy_y + ny * lead_dist * 0.3
        return cast_spell(0, aim_y, aim_x)

    # --- PRIORITY 1: Dodge very close projectiles ---
    if threatening_proj is not None and min_threat_dist < 300:
        pdx = threatening_proj["dx_to_me"]
        pdy = threatening_proj["dy_to_me"]

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

            # Choose direction that keeps us at good range from enemy
            # Prefer the side that doesn't move us closer if we're low HP
            dot1 = perp1_x * (-nx) + perp1_y * (-ny)
            dot2 = perp2_x * (-nx) + perp2_y * (-ny)

            if my_hp_pct < 0.3:
                dodge_nx, dodge_ny = (perp1_x, perp1_y) if dot1 >= dot2 else (perp2_x, perp2_y)
            else:
                dodge_nx, dodge_ny = (perp1_x, perp1_y) if abs(dot1) <= abs(dot2) else (perp2_x, perp2_y)

            # Use E to dodge if projectile is extremely close and we're in danger
            if e_ready and min_threat_dist < 120 and my_hp_pct < 0.35:
                e_x = my_x + dodge_nx * 475
                e_y = my_y + dodge_ny * 475
                return cast_spell(2, e_y, e_x)

            dodge_dist = 350
            move_x = my_x + dodge_nx * dodge_dist
            move_y = my_y + dodge_ny * dodge_dist
            return move_to(move_y, move_x)

    # --- PRIORITY 2: Cast W when Q on cooldown and enemy in range ---
    if w_ready and enemy_dist < 900 and my_mp_pct > 0.15:
        travel_time = enemy_dist / 1600.0
        lead_dist = travel_time * 200
        aim_x = enemy_x + nx * lead_dist * 0.3
        aim_y = enemy_y + ny * lead_dist * 0.3
        return cast_spell(1, aim_y, aim_x)

    # --- PRIORITY 3: R for execute ---
    if r_ready and enemy_hp_pct < 0.25 and enemy_dist < 2500 and my_mp_pct > 0.1:
        return cast_spell(3, enemy_y, enemy_x)

    # --- PRIORITY 4: Retreat if very low HP ---
    if my_hp_pct < 0.2 and my_hp_pct < enemy_hp_pct - 0.15:
        if e_ready and enemy_dist < 700:
            retreat_x = my_x - nx * 475
            retreat_y = my_y - ny * 475
            return cast_spell(2, retreat_y, retreat_x)
        retreat_x = my_x - nx * 600
        retreat_y = my_y - ny * 600
        return move_to(retreat_y, retreat_x)

    # --- PRIORITY 5: Auto-attack if in range (~550 units) and spells on cooldown ---
    if enemy_dist < 550 and not q_ready:
        return cast_spell(0, enemy_y, enemy_x)  # This will attempt auto if spell fails

    # --- PRIORITY 6: Positioning / Kiting ---
    # Optimal range: ~750 (inside Q range but hard for enemy to hit us)
    optimal_range = 750

    if enemy_dist > 1100:
        # Too far - approach with zigzag to avoid predictability
        step = min(400, enemy_dist - optimal_range)
        t = game_time * 0.001
        juke = math.sin(t * 23.0) * 180
        target_x = my_x + nx * step + (-ny) * juke
        target_y = my_y + ny * step + (nx) * juke
        return move_to(target_y, target_x)

    # In combat range: sharp unpredictable strafing
    range_correction = (enemy_dist - optimal_range) * 0.4

    t = game_time * 0.001
    # Use fast alternating pattern for unpredictability
    phase = (t * 17.0) % (2 * math.pi)
    if phase < math.pi * 0.3:
        lateral = 350
    elif phase < math.pi * 0.7:
        lateral = -350
    elif phase < math.pi * 1.0:
        lateral = 280
    elif phase < math.pi * 1.4:
        lateral = -280
    elif phase < math.pi * 1.7:
        lateral = 320
    else:
        lateral = -200

    # High-frequency jitter on top
    lateral += math.sin(t * 41.0) * 100

    move_x = my_x + nx * range_correction + (-ny) * lateral
    move_y = my_y + ny * range_correction + (nx) * lateral

    return move_to(move_y, move_x)