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
    enemy_target_x = my_x + (enemy_dx)
    enemy_target_y = my_y + (enemy_dy)
    enemy_champ_x = enemy_champ["position"]["X"]
    enemy_champ_y = enemy_champ["position"]["Y"]

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

    # R for execute or when enemy is low
    mult = 4
    mult = 1000 / mult
    if int(observation["game_time"]/mult) % 2 == 0:
        return (1, [enemy_champ_x, enemy_champ_y])
    else:
        # return (1, [enemy_champ_x, enemy_champ_y])
        return (2, [[0], [enemy_champ_x, enemy_champ_y]])