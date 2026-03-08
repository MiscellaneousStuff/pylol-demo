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

    # Gather all enemy projectiles
    enemy_projectiles = [p for p in observation["projectiles"] if p["my_team"] == 0]
    
    # Classify projectiles by urgency (very close = immediate danger)
    urgent_projectiles = [p for p in enemy_projectiles if p["distance_to_me"] < 400]
    nearby_projectiles = [p for p in enemy_projectiles if p["distance_to_me"] < 700]

    # Calculate a safe dodge direction considering ALL nearby projectiles
    def get_dodge_direction(projectiles):
        if not projectiles:
            return None, None
        # Sum up perpendicular dodge vectors from all projectiles, weighted by closeness
        total_dodge_x = 0.0
        total_dodge_y = 0.0
        for p in projectiles:
            pdx = p["dx_to_me"]
            pdy = p["dy_to_me"]
            pdist = max(p["distance_to_me"], 1)
            # Perpendicular to projectile direction (two options)
            perp1_x = pdy
            perp1_y = -pdx
            perp2_x = -pdy
            perp2_y = pdx
            # Weight by inverse distance (closer = more urgent)
            weight = 1.0 / pdist
            # Choose perpendicular that moves away from enemy (safer)
            away_x = my_x - enemy_x
            away_y = my_y - enemy_y
            dot1 = perp1_x * away_x + perp1_y * away_y
            dot2 = perp2_x * away_x + perp2_y * away_y
            if dot1 >= dot2:
                total_dodge_x += perp1_x * weight
                total_dodge_y += perp1_y * weight
            else:
                total_dodge_x += perp2_x * weight
                total_dodge_y += perp2_y * weight
        mag = math.sqrt(total_dodge_x**2 + total_dodge_y**2)
        if mag > 0:
            return total_dodge_x / mag, total_dodge_y / mag
        return None, None

    # Lead target prediction for skillshots
    def lead_target(target_x, target_y, proj_speed=2000):
        # Simple lead based on enemy movement estimation
        # Since we don't have velocity, aim slightly ahead
        return target_y, target_x

    # ===== PRIORITY 1: URGENT DODGE (projectiles < 400 units) =====
    if urgent_projectiles:
        # Use E to dodge if multiple urgent projectiles or very close
        dodge_dx, dodge_dy = get_dodge_direction(urgent_projectiles)
        if dodge_dx is not None:
            dodge_dist = 475
            if e_ready and len(urgent_projectiles) >= 1:
                e_x = my_x + dodge_dx * dodge_dist
                e_y = my_y + dodge_dy * dodge_dist
                return cast_spell(2, e_y, e_x)
            else:
                move_x = my_x + dodge_dx * 400
                move_y = my_y + dodge_dy * 400
                return move_to(move_y, move_x)

    # ===== PRIORITY 2: CAST OFFENSIVE SPELLS (weave damage between dodges) =====
    # R execute on low HP enemy
    if r_ready and enemy_hp_pct < 0.25 and my_mp_pct > 0.1:
        return cast_spell(3, enemy_y, enemy_x)

    # Q poke - this is the bread and butter, MUST fire when ready and in range
    if q_ready and enemy_dist < 1150 and my_mp_pct > 0.08:
        return cast_spell(0, enemy_y, enemy_x)

    # W for extra damage when in range
    if w_ready and enemy_dist < 900 and my_mp_pct > 0.2:
        return cast_spell(1, enemy_y, enemy_x)

    # ===== PRIORITY 3: DODGE NEARBY PROJECTILES (< 700 units) =====
    if nearby_projectiles:
        dodge_dx, dodge_dy = get_dodge_direction(nearby_projectiles)
        if dodge_dx is not None:
            move_x = my_x + dodge_dx * 350
            move_y = my_y + dodge_dy * 350
            return move_to(move_y, move_x)

    # ===== PRIORITY 4: RETREAT IF LOW HP =====
    if my_hp_pct < 0.20 and enemy_hp_pct > my_hp_pct + 0.10:
        # E away if available
        if e_ready:
            retreat_x = my_x + (my_x - enemy_x) * 0.5
            retreat_y = my_y + (my_y - enemy_y) * 0.5
            return cast_spell(2, retreat_y, retreat_x)
        retreat_x = my_x + (my_x - enemy_x) * 0.6
        retreat_y = my_y + (my_y - enemy_y) * 0.6
        return move_to(retreat_y, retreat_x)

    # ===== PRIORITY 5: EXECUTE LOW ENEMY =====
    if enemy_hp_pct < 0.25 and my_hp_pct > 0.10:
        if e_ready and enemy_dist > 600 and enemy_dist < 1500:
            dx = enemy_x - my_x
            dy = enemy_y - my_y
            dist = math.sqrt(dx**2 + dy**2)
            if dist > 0:
                e_x = my_x + (dx / dist) * 475
                e_y = my_y + (dy / dist) * 475
                return cast_spell(2, e_y, e_x)
        return move_to(enemy_y, enemy_x)

    # ===== PRIORITY 6: POSITIONING =====
    optimal_range = 850  # Stay at Q range, not too close

    if enemy_dist > 1200:
        # Too far - approach with juke pattern to avoid being predictable
        dx = enemy_x - my_x
        dy = enemy_y - my_y
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            nx = dx / dist
            ny = dy / dist
            # Zigzag approach - alternate perpendicular offset rapidly
            juke_amplitude = 250
            # Use game_time with higher frequency for rapid zigzag
            juke = juke_amplitude if (int(game_time * 0.004) % 2 == 0) else -juke_amplitude
            perp_x = -ny * juke
            perp_y = nx * juke
            step = min(500, enemy_dist - optimal_range)
            target_x = my_x + nx * step + perp_x
            target_y = my_y + ny * step + perp_y
            return move_to(target_y, target_x)
        return move_to(enemy_y, enemy_x)
    elif enemy_dist < 500:
        # Too close - kite backwards while maintaining angle
        dx = my_x - enemy_x
        dy = my_y - enemy_y
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            nx = dx / dist
            ny = dy / dist
            target_x = my_x + nx * 300
            target_y = my_y + ny * 300
            return move_to(target_y, target_x)
    else:
        # Good range - orbit with rapid direction changes to be unpredictable
        dx = enemy_x - my_x
        dy = enemy_y - my_y
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            nx = dx / dist
            ny = dy / dist
            # Rapid orbit direction changes every ~500ms of game time
            orbit_dir = 1 if (int(game_time * 0.003) % 2 == 0) else -1
            orbit_x = my_x + (-ny * orbit_dir) * 350 + nx * 50
            orbit_y = my_y + (nx * orbit_dir) * 350 + ny * 50
            return move_to(orbit_y, orbit_x)

    return move_to(my_y, my_x)