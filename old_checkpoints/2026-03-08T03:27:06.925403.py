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
    game_time = observation.get("game_time", 0)

    if not hasattr(self, '_tick_count'):
        self._tick_count = 0
    self._tick_count += 1

    # Direction unit vector toward enemy
    if enemy_dist > 1:
        nx = enemy_dx / enemy_dist
        ny = enemy_dy / enemy_dist
    else:
        nx, ny = 1, 0

    perp_x = -ny
    perp_y = nx

    def move_to(target_y, target_x):
        target_x = max(0, min(16000, target_x))
        target_y = max(0, min(16000, target_y))
        return (1, [target_y, target_x])

    def cast_spell(spell_idx, target_y, target_x):
        target_x = max(0, min(16000, target_x))
        target_y = max(0, min(16000, target_y))
        return (2, [[spell_idx], [target_y, target_x]])

    q_ready = my_champ["q_cooldown"] == 0
    w_ready = my_champ["w_cooldown"] == 0
    e_ready = my_champ["e_cooldown"] == 0
    r_ready = my_champ["r_cooldown"] == 0

    # Find only VERY close enemy projectiles (truly imminent threats)
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    imminent_proj = None
    imminent_dist = 9999
    for p in enemy_projectiles:
        pdx = p["dx_to_me"]
        pdy = p["dy_to_me"]
        pdist = math.sqrt(pdx**2 + pdy**2)
        if 15 < pdist < 200:
            if pdist < imminent_dist:
                imminent_dist = pdist
                imminent_proj = p

    def get_dodge_move(proj, dodge_dist=350):
        pdx = proj["dx_to_me"]
        pdy = proj["dy_to_me"]
        p1x, p1y = pdy, -pdx
        p2x, p2y = -pdy, pdx
        mag = math.sqrt(p1x**2 + p1y**2)
        if mag > 0:
            p1x /= mag; p1y /= mag
            p2x /= mag; p2y /= mag
        opt_range = 750
        pos1_x = my_x + p1x * dodge_dist
        pos1_y = my_y + p1y * dodge_dist
        pos2_x = my_x + p2x * dodge_dist
        pos2_y = my_y + p2y * dodge_dist
        dist1 = abs(math.sqrt((pos1_x - enemy_x)**2 + (pos1_y - enemy_y)**2) - opt_range)
        dist2 = abs(math.sqrt((pos2_x - enemy_x)**2 + (pos2_y - enemy_y)**2) - opt_range)
        if dist1 <= dist2:
            return pos1_x, pos1_y
        else:
            return pos2_x, pos2_y

    # ============================================================
    # ABSOLUTE PRIORITY 0: Retreat when critically low HP
    # ============================================================
    if my_hp_pct < 0.15 and my_hp_pct < enemy_hp_pct:
        retreat_x = my_x - nx * 600
        retreat_y = my_y - ny * 600
        t = game_time * 0.01
        retreat_x += perp_x * math.sin(t * 7) * 300
        retreat_y += perp_y * math.sin(t * 7) * 300
        if e_ready and enemy_dist < 700:
            return cast_spell(2, retreat_y, retreat_x)
        return move_to(retreat_y, retreat_x)

    # ============================================================
    # PRIORITY 1: R for execute on low HP enemy
    # ============================================================
    if r_ready and enemy_hp_pct < 0.25 and my_mp_pct > 0.1:
        return cast_spell(3, enemy_y, enemy_x)

    # ============================================================
    # PRIORITY 2: ALWAYS CAST Q WHEN READY AND IN RANGE
    # This is the #1 damage source - must fire on cooldown
    # ============================================================
    if q_ready and enemy_dist < 1050 and my_mp_pct > 0.05:
        return cast_spell(0, enemy_y, enemy_x)

    # ============================================================
    # PRIORITY 3: CAST W WHEN READY AND IN RANGE
    # ============================================================
    if w_ready and enemy_dist < 900 and my_mp_pct > 0.15:
        return cast_spell(1, enemy_y, enemy_x)

    # ============================================================
    # PRIORITY 4: CLOSE DISTANCE if too far to fight
    # ============================================================
    if enemy_dist > 1100:
        step = min(800, enemy_dist - 800)
        t = game_time * 0.01
        juke = math.sin(t * 5) * 200
        target_x = my_x + nx * step + perp_x * juke
        target_y = my_y + ny * step + perp_y * juke
        return move_to(target_y, target_x)

    # ============================================================
    # PRIORITY 5: DODGE imminent projectile (< 200 units only)
    # Only dodge when spells are on cooldown
    # ============================================================
    if imminent_proj is not None:
        if e_ready and imminent_dist < 100 and my_hp_pct < 0.3:
            dodge_x, dodge_y = get_dodge_move(imminent_proj, 475)
            return cast_spell(2, dodge_y, dodge_x)
        dodge_x, dodge_y = get_dodge_move(imminent_proj, 350)
        return move_to(dodge_y, dodge_x)

    # ============================================================
    # PRIORITY 6: REPOSITION - strafe at optimal range
    # ============================================================
    optimal_range = 750
    range_error = enemy_dist - optimal_range
    approach_factor = 0.4 if range_error > 0 else 0.3

    t = game_time * 0.01
    phase = math.sin(t * 6.0)
    if phase > 0.2:
        lateral = 400
    elif phase < -0.2:
        lateral = -400
    else:
        lateral = 350 * (1 if math.sin(t * 15.0) > 0 else -1)

    move_x = my_x + nx * range_error * approach_factor + perp_x * lateral
    move_y = my_y + ny * range_error * approach_factor + perp_y * lateral

    return move_to(move_y, move_x)