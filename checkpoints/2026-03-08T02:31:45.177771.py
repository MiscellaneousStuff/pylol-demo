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

    # Initialize persistent state for alternating cast/move
    if not hasattr(self, '_last_action_was_spell'):
        self._last_action_was_spell = False
        self._dodge_sign = 1

    # Direction unit vector toward enemy
    if enemy_dist > 0:
        nx = enemy_dx / enemy_dist
        ny = enemy_dy / enemy_dist
    else:
        nx, ny = 1, 0

    # Perpendicular unit vectors (lateral movement relative to enemy direction)
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

    # --- Detect enemy projectiles ---
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    closest_proj = None
    closest_proj_dist = 9999
    for p in enemy_projectiles:
        pdx = p["dx_to_me"]
        pdy = p["dy_to_me"]
        pdist = math.sqrt(pdx**2 + pdy**2)
        if pdist < 15:
            continue
        if pdist < closest_proj_dist:
            closest_proj_dist = pdist
            closest_proj = p

    def get_dodge_move(proj, dodge_dist=400):
        """Return dodge target (x, y) perpendicular to incoming projectile."""
        pdx = proj["dx_to_me"]
        pdy = proj["dy_to_me"]
        # Two perpendicular directions to the projectile's relative position
        p1x, p1y = pdy, -pdx
        p2x, p2y = -pdy, pdx
        mag = math.sqrt(p1x**2 + p1y**2)
        if mag > 0:
            p1x /= mag; p1y /= mag
            p2x /= mag; p2y /= mag

        # Pick the direction that also moves us away from enemy when low HP
        # or just pick the alternating direction
        away_dot1 = p1x * (-nx) + p1y * (-ny)
        away_dot2 = p2x * (-nx) + p2y * (-ny)

        if my_hp_pct < 0.35:
            # Prefer moving away from enemy while dodging
            if away_dot1 >= away_dot2:
                dx, dy = p1x, p1y
            else:
                dx, dy = p2x, p2y
        else:
            # Alternate direction to be unpredictable
            if self._dodge_sign > 0:
                dx, dy = p1x, p1y
            else:
                dx, dy = p2x, p2y
            self._dodge_sign *= -1

        return my_x + dx * dodge_dist, my_y + dy * dodge_dist

    # ====================================================================
    # PRIORITY 0: DODGE projectiles within 600 units - ALWAYS takes priority
    # ====================================================================
    if closest_proj is not None and closest_proj_dist < 600:
        # Use E (Arcane Shift) for very close projectiles when low HP
        if e_ready and closest_proj_dist < 200 and my_hp_pct < 0.35:
            dodge_x, dodge_y = get_dodge_move(closest_proj, 475)
            return cast_spell(2, dodge_y, dodge_x)

        dodge_x, dodge_y = get_dodge_move(closest_proj, 400)
        return move_to(dodge_y, dodge_x)

    # ====================================================================
    # PRIORITY 1: Retreat when critically low HP
    # ====================================================================
    if my_hp_pct < 0.15 and my_hp_pct < enemy_hp_pct:
        # Zigzag retreat toward base (away from enemy)
        t = game_time * 0.01
        zigzag = math.sin(t * 7.0) * 350
        retreat_x = my_x - nx * 500 + perp_x * zigzag
        retreat_y = my_y - ny * 500 + perp_y * zigzag

        if e_ready and enemy_dist < 800:
            return cast_spell(2, retreat_y, retreat_x)
        return move_to(retreat_y, retreat_x)

    # ====================================================================
    # PRIORITY 2: R for execute on low HP enemy
    # ====================================================================
    if r_ready and enemy_hp_pct < 0.2 and enemy_dist < 2500 and my_mp_pct > 0.1:
        self._last_action_was_spell = True
        return cast_spell(3, enemy_y, enemy_x)

    # ====================================================================
    # PRIORITY 3: Alternate between CASTING and MOVING every tick
    # This ensures the bot NEVER stands still (the critical flaw before)
    # ====================================================================
    should_cast = not self._last_action_was_spell

    if should_cast:
        # Try to cast an offensive spell
        if q_ready and enemy_dist < 1050 and my_mp_pct > 0.05:
            # Lead prediction: aim slightly ahead of enemy
            travel_time = enemy_dist / 2000.0
            # Simple lead - aim at enemy position (already reasonably good for Ezreal Q)
            aim_x = enemy_x
            aim_y = enemy_y
            self._last_action_was_spell = True
            return cast_spell(0, aim_y, aim_x)

        if w_ready and enemy_dist < 900 and my_mp_pct > 0.15:
            aim_x = enemy_x
            aim_y = enemy_y
            self._last_action_was_spell = True
            return cast_spell(1, aim_y, aim_x)

    # ====================================================================
    # PRIORITY 4: ALWAYS MOVE - strafe unpredictably at optimal range
    # ====================================================================
    self._last_action_was_spell = False

    # Optimal range: ~800 (within Q range but hard for enemy to hit)
    optimal_range = 800
    range_correction = (enemy_dist - optimal_range) * 0.4

    # Rapid lateral movement pattern - sharp direction changes
    t = game_time * 0.01
    # Primary oscillation with abrupt changes
    phase_fast = math.sin(t * 6.0)
    phase_jitter = math.sin(t * 17.0)

    if phase_fast > 0.2:
        lateral = 400
    elif phase_fast < -0.2:
        lateral = -400
    else:
        # Quick transition zone - use fast jitter
        lateral = 350 * (1 if phase_jitter > 0 else -1)

    # Add high-frequency jitter for micro-unpredictability
    lateral += phase_jitter * 80

    move_x = my_x + nx * range_correction + perp_x * lateral
    move_y = my_y + ny * range_correction + perp_y * lateral

    return move_to(move_y, move_x)