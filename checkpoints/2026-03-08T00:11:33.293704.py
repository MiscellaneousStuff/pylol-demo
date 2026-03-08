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

    # Find truly threatening projectiles - only those very close and likely to hit
    threatening_proj = None
    threatening_dist = 9999
    for p in enemy_projectiles:
        pdist = p["distance_to_me"]
        pdx = p["dx_to_me"]
        pdy = p["dy_to_me"]
        # Only consider projectiles that are close enough to be an immediate threat
        # and are actually approaching us (distance < 300 is danger zone)
        if pdist < 300 and pdist > 10:
            if pdist < threatening_dist:
                threatening_dist = pdist
                threatening_proj = p

    # --- PRIORITY 1: Dodge only very close, truly threatening projectiles ---
    if threatening_proj is not None and threatening_dist < 300:
        pdx = threatening_proj["dx_to_me"]
        pdy = threatening_proj["dy_to_me"]

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

            # Pick dodge direction that moves away from enemy if low HP, else aggressive
            if my_hp_pct < 0.4:
                dot1 = perp1_x * (-enemy_dx) + perp1_y * (-enemy_dy)
                dot2 = perp2_x * (-enemy_dx) + perp2_y * (-enemy_dy)
            else:
                dot1 = perp1_x * enemy_dx + perp1_y * enemy_dy
                dot2 = perp2_x * enemy_dx + perp2_y * enemy_dy

            if dot1 >= dot2:
                dodge_nx, dodge_ny = perp1_x, perp1_y
            else:
                dodge_nx, dodge_ny = perp2_x, perp2_y

            # Use E to dodge if projectile is extremely close and we're in danger
            if e_ready and threatening_dist < 150 and my_hp_pct < 0.4:
                e_x = my_x + dodge_nx * 475
                e_y = my_y + dodge_ny * 475
                return cast_spell(2, e_y, e_x)

            dodge_dist = 250
            move_x = my_x + dodge_nx * dodge_dist
            move_y = my_y + dodge_ny * dodge_dist
            return move_to(move_y, move_x)

    # --- PRIORITY 2: Retreat if very low HP ---
    hp_diff = my_hp_pct - enemy_hp_pct
    if my_hp_pct < 0.25 and hp_diff < -0.2:
        if e_ready and enemy_dist < 700:
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

    # --- PRIORITY 3: Cast spells offensively - THIS IS CRITICAL ---
    # Lead the target slightly based on distance for skillshots
    lead_factor = 0.15  # Small lead since we can't predict movement well

    # R - Execute low HP enemies at long range
    if r_ready and enemy_hp_pct < 0.25 and my_mp_pct > 0.1 and enemy_dist < 3000:
        return cast_spell(3, enemy_y, enemy_x)

    # Q - Primary damage, 1150 range. Use on cooldown when in range!
    if q_ready and enemy_dist < 1050 and my_mp_pct > 0.05:
        # Slight lead - aim a bit ahead of enemy position
        # Use game time modulation to vary aim slightly for unpredictability
        t = game_time * 0.001
        aim_offset_x = math.sin(t * 5.0) * 50
        aim_offset_y = math.cos(t * 5.0) * 50
        return cast_spell(0, enemy_y + aim_offset_y, enemy_x + aim_offset_x)

    # W - Secondary poke, 950 range
    if w_ready and enemy_dist < 900 and my_mp_pct > 0.15:
        return cast_spell(1, enemy_y, enemy_x)

    # Auto attack if in auto range (~550) and no spells available
    if enemy_dist < 550 and not q_ready and not w_ready:
        return cast_spell(0, enemy_y, enemy_x)  # This won't cast if on CD, but attempt auto

    # --- PRIORITY 4: Positioning and kiting ---
    if enemy_dist > 0:
        nx = enemy_dx / enemy_dist
        ny = enemy_dy / enemy_dist
    else:
        nx, ny = 1, 0

    # If too far, close distance to get into Q range
    if enemy_dist > 1000:
        step = min(400, enemy_dist - 800)
        # Add lateral juke while approaching to avoid being predictable
        t = game_time * 0.003
        juke_amount = math.sin(t * 13.0) * 200
        target_x = my_x + nx * step + (-ny) * juke_amount
        target_y = my_y + ny * step + (nx) * juke_amount
        return move_to(target_y, target_x)

    # In combat range: maintain ~750 range (good for Q poke) with sharp lateral jukes
    optimal_range = 750
    range_correction = (enemy_dist - optimal_range) * 0.5

    # Sharp, unpredictable lateral movement
    t = game_time * 0.001
    # Quick direction changes to dodge incoming skillshots preemptively
    lateral = math.sin(t * 19.0) * 180 + math.sin(t * 8.7) * 120
    # Sharp reversal occasionally
    if abs(math.sin(t * 29.0)) > 0.8:
        lateral = -lateral * 1.3

    move_x = my_x + nx * range_correction + (-ny) * lateral
    move_y = my_y + ny * range_correction + (nx) * lateral

    return move_to(move_y, move_x)