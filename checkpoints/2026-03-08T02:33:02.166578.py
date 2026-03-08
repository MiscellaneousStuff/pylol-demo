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
        self._dodge_sign = 1
    self._tick_count += 1

    # Direction unit vector toward enemy
    if enemy_dist > 0:
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

    # --- Detect ACTUALLY THREATENING enemy projectiles ---
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    threatening_proj = None
    threatening_proj_dist = 9999
    for p in enemy_projectiles:
        pdx = p["dx_to_me"]
        pdy = p["dy_to_me"]
        pdist = math.sqrt(pdx**2 + pdy**2)
        if pdist < 20:
            continue
        # Only consider projectiles that are relatively close AND moving toward us
        # A projectile moving toward us: its position relative to us should be getting smaller
        # We approximate: if the projectile is close enough, it's a threat
        # Filter out projectiles that are far or have clearly passed us
        # dx_to_me, dy_to_me is projectile position relative to me
        # If the projectile name contains known skillshot names and distance is small, dodge
        if pdist < 350 and pdist < threatening_proj_dist:
            threatening_proj_dist = pdist
            threatening_proj = p

    def get_dodge_move(proj, dodge_dist=350):
        pdx = proj["dx_to_me"]
        pdy = proj["dy_to_me"]
        p1x, p1y = pdy, -pdx
        p2x, p2y = -pdy, pdx
        mag = math.sqrt(p1x**2 + p1y**2)
        if mag > 0:
            p1x /= mag; p1y /= mag
            p2x /= mag; p2y /= mag
        if self._dodge_sign > 0:
            dx, dy = p1x, p1y
        else:
            dx, dy = p2x, p2y
        self._dodge_sign *= -1
        return my_x + dx * dodge_dist, my_y + dy * dodge_dist

    # ====================================================================
    # PRIORITY 0: DODGE only very close threatening projectiles (< 350)
    # ====================================================================
    if threatening_proj is not None and threatening_proj_dist < 350:
        if e_ready and threatening_proj_dist < 150 and my_hp_pct < 0.3:
            dodge_x, dodge_y = get_dodge_move(threatening_proj, 475)
            return cast_spell(2, dodge_y, dodge_x)
        dodge_x, dodge_y = get_dodge_move(threatening_proj, 350)
        return move_to(dodge_y, dodge_x)

    # ====================================================================
    # PRIORITY 1: Retreat when critically low HP
    # ====================================================================
    if my_hp_pct < 0.15 and my_hp_pct < enemy_hp_pct:
        retreat_x = my_x - nx * 600
        retreat_y = my_y - ny * 600
        if e_ready and enemy_dist < 700:
            return cast_spell(2, retreat_y, retreat_x)
        return move_to(retreat_y, retreat_x)

    # ====================================================================
    # PRIORITY 2: R for execute on low HP enemy
    # ====================================================================
    if r_ready and enemy_hp_pct < 0.25 and enemy_dist < 2500 and my_mp_pct > 0.1:
        return cast_spell(3, enemy_y, enemy_x)

    # ====================================================================
    # PRIORITY 3: ATTACK - alternate between spells/autos and movement
    # Every other tick: cast spell or auto. Other ticks: reposition.
    # ====================================================================
    should_attack = (self._tick_count % 2 == 0)

    if should_attack:
        # Lead prediction for skillshots
        if enemy_dist > 0:
            # Estimate travel time for Q (speed ~2000)
            q_travel = enemy_dist / 2000.0
            # Simple lead: aim slightly ahead (we don't know enemy velocity, so aim at them)
            lead_x = enemy_x
            lead_y = enemy_y
        else:
            lead_x = enemy_x
            lead_y = enemy_y

        # Q - primary poke, longest range
        if q_ready and enemy_dist < 1050 and my_mp_pct > 0.05:
            return cast_spell(0, lead_y, lead_x)

        # W - secondary poke
        if w_ready and enemy_dist < 900 and my_mp_pct > 0.15:
            return cast_spell(1, lead_y, lead_x)

        # Auto attack if in range (~550 for Ezreal)
        if enemy_dist < 550:
            return cast_spell(0, enemy_y, enemy_x) if q_ready else (2, [[4], [enemy_y, enemy_x]])

    # ====================================================================
    # PRIORITY 4: REPOSITION - strafe at optimal range
    # ====================================================================
    # Optimal range: ~700 (within Q range, outside easy enemy skillshot range)
    optimal_range = 700
    range_error = enemy_dist - optimal_range

    # If too far, move toward enemy; if too close, move away
    approach_factor = 0.5 if range_error > 0 else 0.3

    # Lateral movement for unpredictability
    t = game_time * 0.01
    phase = math.sin(t * 8.0)
    if phase > 0.15:
        lateral = 380
    elif phase < -0.15:
        lateral = -380
    else:
        lateral = 300 * (1 if math.sin(t * 19.0) > 0 else -1)

    move_x = my_x + nx * range_error * approach_factor + perp_x * lateral
    move_y = my_y + ny * range_error * approach_factor + perp_y * lateral

    return move_to(move_y, move_x)