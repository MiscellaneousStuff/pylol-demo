def act(self, observation):
    import math  # YOU MUST IMPORT THIS MODULE EVERY SINGLE TIME. DO NOT IMPORT ANY OTHER MODULES

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
    enemy_target_x = my_x + enemy_dx
    enemy_target_y = my_y + enemy_dy

    q_ready = my_champ["q_cooldown"] == 0
    w_ready = my_champ["w_cooldown"] == 0
    e_ready = my_champ["e_cooldown"] == 0
    r_ready = my_champ["r_cooldown"] == 0

    team = 100 if my_champ["user_id"] == 1 else 200
    if team == 100:
        base_x, base_y = 500, 500
    else:
        base_x, base_y = 12000, 12000

    def move_direction(dy, dx, dist=300):
        mag = math.sqrt(dy**2 + dx**2)
        if mag > 0:
            return (1, [my_y + (dy / mag) * dist, my_x + (dx / mag) * dist])
        return (1, [my_y - 200, my_x - 200])

    def toward_base(dist=400):
        return move_direction(base_y - my_y, base_x - my_x, dist)

    # Classify projectiles by threat level
    # A projectile is threatening if it's close AND heading toward us
    close_projectiles = []
    medium_projectiles = []
    for p in observation["projectiles"]:
        if p["my_team"] == 0:
            pdist = p["distance_to_me"]
            # Check if projectile is heading roughly toward us
            # dx_to_me and dy_to_me point from us to projectile
            # If projectile speed vector dot (vector from proj to us) > 0, it's coming toward us
            # We approximate: if distance is small enough, it's threatening
            if pdist < 300:
                close_projectiles.append(p)
            elif pdist < 600:
                medium_projectiles.append(p)

    def get_dodge_move(proj, dodge_dist=280):
        pdx = proj["dx_to_me"]
        pdy = proj["dy_to_me"]
        # Perpendicular directions to projectile travel path
        p1x, p1y = -pdy, pdx
        p2x, p2y = pdy, -pdx
        # Pick the direction that moves us away from enemy (safer)
        away_dx = -enemy_dx
        away_dy = -enemy_dy
        dot1 = p1x * away_dx + p1y * away_dy
        dot2 = p2x * away_dx + p2y * away_dy
        if dot1 >= dot2:
            return move_direction(p1y, p1x, dodge_dist)
        else:
            return move_direction(p2y, p2x, dodge_dist)

    # =============================================
    # PRIORITY 0: RETREAT at very low HP
    # =============================================
    if my_hp_pct < 0.20:
        if e_ready:
            # E toward base for escape
            bdy = base_y - my_y
            bdx = base_x - my_x
            mag = math.sqrt(bdy**2 + bdx**2)
            if mag > 0:
                ey = my_y + (bdy / mag) * 475
                ex = my_x + (bdx / mag) * 475
                return (2, [[2], [ey, ex]])
        return toward_base(500)

    # =============================================
    # PRIORITY 1: DODGE very close projectiles (< 300 range)
    # These are imminent threats - dodge BEFORE anything else
    # =============================================
    if close_projectiles:
        closest = min(close_projectiles, key=lambda p: p["distance_to_me"])
        # If E is ready and multiple close projectiles, E out
        if e_ready and len(close_projectiles) >= 2:
            pdx = closest["dx_to_me"]
            pdy = closest["dy_to_me"]
            perp_x = -pdy
            perp_y = pdx
            mag = math.sqrt(perp_x**2 + perp_y**2)
            if mag > 0:
                ex = my_x + (perp_x / mag) * 475
                ey = my_y + (perp_y / mag) * 475
                return (2, [[2], [ey, ex]])
        return get_dodge_move(closest, 300)

    # =============================================
    # PRIORITY 2: CAST ABILITIES offensively
    # Lead the target - predict where enemy will be
    # =============================================
    # Simple lead: aim slightly ahead of enemy's apparent motion
    # Use a small offset in the direction from base to enemy (enemies tend to push forward)
    lead_factor = 0.15 if enemy_dist > 400 else 0.05
    lead_x = enemy_target_x + enemy_dx * lead_factor
    lead_y = enemy_target_y + enemy_dy * lead_factor

    # Q - primary poke (1100 range, fast projectile)
    if q_ready and enemy_dist < 1050 and my_mp_pct > 0.08:
        return (2, [[0], [lead_y, lead_x]])

    # W - secondary poke (1000 range)
    if w_ready and enemy_dist < 900 and my_mp_pct > 0.12:
        return (2, [[1], [lead_y, lead_x]])

    # R - execute low HP enemies or long range snipe
    if r_ready and enemy_hp_pct < 0.25 and enemy_dist < 1500 and my_mp_pct > 0.15:
        return (2, [[3], [lead_y, lead_x]])

    # =============================================
    # PRIORITY 3: DODGE medium range projectiles (300-600)
    # Now that we've checked abilities, dodge medium threats
    # =============================================
    if medium_projectiles:
        closest = min(medium_projectiles, key=lambda p: p["distance_to_me"])
        return get_dodge_move(closest, 250)

    # =============================================
    # PRIORITY 4: PLAY SAFE at HP disadvantage
    # =============================================
    if my_hp_pct < 0.40 and my_hp_pct < enemy_hp_pct - 0.15:
        return toward_base(350)

    # =============================================
    # PRIORITY 5: KITE back if enemy too close
    # =============================================
    if enemy_dist < 350:
        away_dx = -enemy_dx
        away_dy = -enemy_dy
        return move_direction(away_dy, away_dx, 280)

    # =============================================
    # PRIORITY 6: ACTIVE JUKING - move unpredictably between actions
    # Use sinusoidal pattern based on game time proxy (position-based) to be hard to hit
    # =============================================
    optimal_range = 650
    dist_from_base = math.sqrt((my_x - base_x)**2 + (my_y - base_y)**2)
    if dist_from_base > 9500:
        return toward_base(200)

    # Calculate angle to enemy
    angle_to_enemy = math.atan2(enemy_dy, enemy_dx)

    if enemy_dist > optimal_range + 250:
        # Approach but with lateral juke movement
        juke_phase = math.sin(my_x * 0.08 + my_y * 0.11) * 0.7
        nx = my_x + math.cos(angle_to_enemy + juke_phase) * 220
        ny = my_y + math.sin(angle_to_enemy + juke_phase) * 220
        return (1, [ny, nx])
    elif enemy_dist < optimal_range - 100:
        # Too close, back off with lateral movement
        juke_phase = math.sin(my_x * 0.1 + my_y * 0.06) * 0.6
        nx = my_x + math.cos(angle_to_enemy + math.pi + juke_phase) * 200
        ny = my_y + math.sin(angle_to_enemy + math.pi + juke_phase) * 200
        return (1, [ny, nx])
    else:
        # At optimal range - orbit with rapid direction changes to be unpredictable
        # Faster oscillation makes us harder to hit
        phase = math.sin(my_x * 0.12 + my_y * 0.09)
        orbit_dir = math.pi / 2 if phase > 0 else -math.pi / 2
        nx = my_x + math.cos(angle_to_enemy + orbit_dir) * 200
        ny = my_y + math.sin(angle_to_enemy + orbit_dir) * 200
        return (1, [ny, nx])