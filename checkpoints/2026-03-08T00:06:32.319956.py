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

    # ===== ABSOLUTE TOP PRIORITY: CAST Q - This is our bread and butter damage =====
    # The bot was previously orbiting for 20+ seconds without ever casting Q.
    # We MUST attack. Cast Q whenever it's ready and enemy is within range.
    if q_ready and my_mp_pct > 0.05:
        # Ezreal Q range is ~1150. Use enemy_dist or compute from dx/dy as fallback.
        # Aim directly at enemy position. Also try computing distance from dx/dy.
        computed_dist = math.sqrt(enemy_dx**2 + enemy_dy**2)
        actual_target_x = my_x + enemy_dx
        actual_target_y = my_y + enemy_dy
        if computed_dist < 1150 or enemy_dist < 1150:
            return cast_spell(0, actual_target_y, actual_target_x)

    # ===== PRIORITY 2: Cast W for extra poke damage =====
    if w_ready and my_mp_pct > 0.15:
        computed_dist = math.sqrt(enemy_dx**2 + enemy_dy**2)
        actual_target_x = my_x + enemy_dx
        actual_target_y = my_y + enemy_dy
        if computed_dist < 950 or enemy_dist < 950:
            return cast_spell(1, actual_target_y, actual_target_x)

    # ===== PRIORITY 3: Execute low HP enemy with R =====
    if r_ready and enemy_hp_pct < 0.30 and my_mp_pct > 0.1:
        computed_dist = math.sqrt(enemy_dx**2 + enemy_dy**2)
        actual_target_x = my_x + enemy_dx
        actual_target_y = my_y + enemy_dy
        if computed_dist < 3000 or enemy_dist < 3000:
            return cast_spell(3, actual_target_y, actual_target_x)

    # ===== PRIORITY 4: Dodge VERY close enemy projectiles =====
    # Only dodge projectiles that are extremely close (within 350 units)
    # Previously the bot was perma-dodging distant/past projectiles and never attacking.
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    dangerous_projectiles = []
    for p in enemy_projectiles:
        pdist = p["distance_to_me"]
        pdx = p["dx_to_me"]
        pdy = p["dy_to_me"]
        # Only dodge if projectile is very close AND actually heading toward us
        # Check if projectile is closing: its direction vector should point roughly toward us
        # dx_to_me, dy_to_me point FROM projectile TO us. If projectile velocity is in that direction, it's closing.
        if pdist < 350 and pdist > 30:
            dangerous_projectiles.append(p)

    if dangerous_projectiles:
        closest = min(dangerous_projectiles, key=lambda p: p["distance_to_me"])
        pdist = closest["distance_to_me"]
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]

        # Perpendicular dodge direction
        perp1_x = pdy
        perp1_y = -pdx
        perp2_x = -pdy
        perp2_y = pdx

        # Pick direction that keeps us closer to enemy (aggressive dodging)
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

            # Use E only for extremely close projectiles
            if e_ready and pdist < 180:
                e_x = my_x + dodge_nx * 475
                e_y = my_y + dodge_ny * 475
                return cast_spell(2, e_y, e_x)

            # Sidestep
            move_x = my_x + dodge_nx * 300
            move_y = my_y + dodge_ny * 300
            return move_to(move_y, move_x)

    # ===== PRIORITY 5: Auto attack when in auto range and spells on cooldown =====
    computed_dist = math.sqrt(enemy_dx**2 + enemy_dy**2)
    if computed_dist < 600 or enemy_dist < 600:
        actual_target_x = my_x + enemy_dx
        actual_target_y = my_y + enemy_dy
        # Issue auto attack command by moving to enemy (or use attack action)
        return move_to(actual_target_y, actual_target_x)

    # ===== PRIORITY 6: Retreat if very low HP =====
    if my_hp_pct < 0.15 and enemy_hp_pct > my_hp_pct + 0.15:
        if e_ready:
            edist = math.sqrt(enemy_dx**2 + enemy_dy**2)
            if edist > 0:
                retreat_x = my_x - (enemy_dx / edist) * 475
                retreat_y = my_y - (enemy_dy / edist) * 475
                return cast_spell(2, retreat_y, retreat_x)
        retreat_x = my_x - enemy_dx * 0.5
        retreat_y = my_y - enemy_dy * 0.5
        return move_to(retreat_y, retreat_x)

    # ===== PRIORITY 7: Aggressively close distance to get into Q range =====
    if computed_dist > 1050 and enemy_dist > 1050:
        edist = math.sqrt(enemy_dx**2 + enemy_dy**2)
        if edist == 0:
            edist = 1
        nx = enemy_dx / edist
        ny = enemy_dy / edist

        # Zigzag while approaching to dodge skillshots
        juke_dir = 1 if (int(game_time * 0.003) % 2 == 0) else -1
        perp_x = -ny * juke_dir * 150
        perp_y = nx * juke_dir * 150

        step = min(800, max(computed_dist, enemy_dist) - 800)
        target_x = my_x + nx * step + perp_x
        target_y = my_y + ny * step + perp_y
        return move_to(target_y, target_x)

    # ===== PRIORITY 8: Orbit while waiting for cooldowns =====
    edist = math.sqrt(enemy_dx**2 + enemy_dy**2)
    if edist == 0:
        edist = 1
    nx = enemy_dx / edist
    ny = enemy_dy / edist

    optimal_range = 850
    orbit_dir = 1 if (int(game_time * 0.002) % 2 == 0) else -1

    cur_range = max(computed_dist, enemy_dist)
    range_adjust = (cur_range - optimal_range) * 0.4

    orbit_x = my_x + nx * range_adjust + (-ny * orbit_dir) * 350
    orbit_y = my_y + ny * range_adjust + (nx * orbit_dir) * 350
    return move_to(orbit_y, orbit_x)