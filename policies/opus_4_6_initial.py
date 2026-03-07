def act(self, observation):
    import math  # YOU MUST IMPORT THIS MODULE EVERY SINGLE TIME. DO NOT IMPORT ANY OTHER MODULES

    print("OBSERVATION:", observation)
    my_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 1)
    enemy_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 0)
    nearby_projectiles = [p for p in observation["projectiles"]
                         if p["my_team"] == 0 and p["distance_to_me"] < 700]

    my_hp_pct = my_champ["current_hp"] / max(my_champ["max_hp"], 1)
    enemy_hp_pct = enemy_champ["current_hp"] / max(enemy_champ["max_hp"], 1)
    my_mp_pct = my_champ["current_mp"] / max(my_champ["max_mp"], 1)
    my_x = my_champ["position"]["X"]
    my_y = my_champ["position"]["Y"]
    enemy_dx = enemy_champ["dx_to_me"]
    enemy_dy = enemy_champ["dy_to_me"]
    enemy_dist = enemy_champ["distance_to_me"]

    # Blue side base direction - retreat toward lower coordinates
    base_x, base_y = 500, 500

    def move_direction(dy, dx, dist=300):
        mag = math.sqrt(dy**2 + dx**2)
        if mag > 0:
            return (1, [my_y + (dy / mag) * dist, my_x + (dx / mag) * dist])
        return (1, [my_y - 200, my_x - 200])  # default move toward base

    def toward_base(dist=400):
        return move_direction(base_y - my_y, base_x - my_x, dist)

    # =============================================
    # PRIORITY 1: SURVIVE - retreat at low HP
    # =============================================
    if my_hp_pct < 0.35:
        return toward_base(500)

    # =============================================
    # PRIORITY 2: DODGE incoming enemy skillshots
    # =============================================
    if nearby_projectiles:
        closest = min(nearby_projectiles, key=lambda p: p["distance_to_me"])
        pdx = closest["dx_to_me"]
        pdy = closest["dy_to_me"]

        # Two perpendicular directions to the projectile offset
        p1x, p1y = -pdy, pdx
        p2x, p2y = pdy, -pdx

        # Choose perpendicular direction biased toward base/safety
        bx = base_x - my_x
        by = base_y - my_y

        dot1 = p1x * bx + p1y * by
        dot2 = p2x * bx + p2y * by

        if dot1 >= dot2:
            return move_direction(p1y, p1x, 300)
        else:
            return move_direction(p2y, p2x, 300)

    # =============================================
    # PRIORITY 3: PLAY SAFE when HP disadvantage
    # =============================================
    if my_hp_pct < 0.50 and my_hp_pct < enemy_hp_pct - 0.15:
        # Retreat toward base but stay available for poke
        return toward_base(300)

    # =============================================
    # PRIORITY 4: USE ABILITIES offensively
    # =============================================
    enemy_target_y = my_y + enemy_dy
    enemy_target_x = my_x + enemy_dx
    q_ready = my_champ["q_cooldown"] == 0
    w_ready = my_champ["w_cooldown"] == 0
    e_ready = my_champ["e_cooldown"] == 0
    r_ready = my_champ["r_cooldown"] == 0

    # R - use when enemy is low for kill potential
    if r_ready and enemy_hp_pct < 0.25 and enemy_dist < 1200 and my_mp_pct > 0.15:
        return (2, [[3], [enemy_target_y, enemy_target_x]])

    # Q - primary poke, use whenever available and in range
    if q_ready and enemy_dist < 1050 and my_mp_pct > 0.12:
        return (2, [[0], [enemy_target_y, enemy_target_x]])

    # W - secondary ability
    if w_ready and enemy_dist < 850 and my_mp_pct > 0.15:
        return (2, [[1], [enemy_target_y, enemy_target_x]])

    # E - use carefully, possibly a dash or short range ability
    if e_ready and enemy_dist < 600 and my_hp_pct > 0.6 and my_mp_pct > 0.15:
        return (2, [[2], [enemy_target_y, enemy_target_x]])

    # =============================================
    # PRIORITY 5: KITE - back off after using spells
    # =============================================
    if enemy_dist < 450:
        # Kite back - blend away from enemy + toward base
        away_dx = -enemy_dx
        away_dy = -enemy_dy
        away_mag = math.sqrt(away_dx**2 + away_dy**2)
        if away_mag > 0:
            away_dx /= away_mag
            away_dy /= away_mag

        to_base_dx = base_x - my_x
        to_base_dy = base_y - my_y
        to_base_mag = math.sqrt(to_base_dx**2 + to_base_dy**2)
        if to_base_mag > 0:
            to_base_dx /= to_base_mag
            to_base_dy /= to_base_mag

        blend_dx = away_dx * 0.5 + to_base_dx * 0.5
        blend_dy = away_dy * 0.5 + to_base_dy * 0.5

        return move_direction(blend_dy, blend_dx, 250)

    # =============================================
    # PRIORITY 6: POSITION - approach or orbit
    # =============================================
    optimal_range = 750

    # Don't overextend past a certain point
    dist_from_base = math.sqrt((my_x - base_x)**2 + (my_y - base_y)**2)
    if dist_from_base > 10000:
        return toward_base(200)

    if enemy_dist > optimal_range + 150:
        # Approach with lateral jitter to dodge skillshots
        angle = math.atan2(enemy_dy, enemy_dx)
        jitter = math.sin((my_x * 0.03 + my_y * 0.04)) * 0.6
        nx = my_x + math.cos(angle + jitter) * 200
        ny = my_y + math.sin(angle + jitter) * 200
        return (1, [ny, nx])
    else:
        # Orbit at optimal range with direction changes for juking
        angle = math.atan2(enemy_dy, enemy_dx)
        phase = math.sin((my_x * 0.025 + my_y * 0.035))
        orbit_dir = math.pi / 2 if phase > 0 else -math.pi / 2
        nx = my_x + math.cos(angle + orbit_dir) * 180
        ny = my_y + math.sin(angle + orbit_dir) * 180
        return (1, [ny, nx])