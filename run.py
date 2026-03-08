# !WINEPREFIX=~/.wine winetricks dxvk

# kill gameserver and lolserver
import datetime
import os
os.system("kill -9 wineserver")

import ast
import time

from pathlib import Path
from typing import Union

from dotenv import load_dotenv
load_dotenv()

import anthropic
import time

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--client", action="store_true")
parser.add_argument("--train", action="store_true")
parser.add_argument("--checkpoint", type=str, default=None)
args = parser.parse_args()

run_client = args.client
TRAIN = args.train

client = anthropic.Anthropic()

def invoke_model(prompt):
    try:
        t = time.time()
        result = ""
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=20_000,
            messages=[
                {"role": "user", "content": prompt}
            ],
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                result += text
        print()  # newline after stream finishes
        print("prompt duration:", time.time() - t, "prompt length:", len(prompt))
        return result
    except Exception as e:
        print("err:", e)
        exit()

class PolicyValidator(ast.NodeVisitor):
    def __init__(self):
        self.has_act_method = False
        self.errors = []

    def visit_FunctionDef(self, node):
        if node.name == 'act':
            self.has_act_method = True
            # Verify act method has correct parameters
            if len(node.args.args) != 2 or \
                node.args.args[0].arg != 'self' or \
                node.args.args[1].arg != 'observation':
                self.errors.append("act method must have parameters (self, observation)")
        self.generic_visit(node)

    # def visit_Import(self, node):
    #     self.errors.append("Import statements are not allowed")
        
    # def visit_ImportFrom(self, node):
    #     self.errors.append("Import statements are not allowed")

    def visit_Call(self, node):
        # Check for dangerous built-ins
        if isinstance(node.func, ast.Name):
            dangerous_functions = {'eval', 'exec', 'open', 'getattr', 'setattr'}
            if node.func.id in dangerous_functions:
                self.errors.append(f"Call to dangerous function {node.func.id} is not allowed")
        self.generic_visit(node)

if not args.checkpoint:
    latest_checkpoint_fname = max(Path("./checkpoints").glob("*.py")).name
else:
    latest_checkpoint_fname = args.checkpoint
INITIAL_POLICY = Path("./checkpoints/" + latest_checkpoint_fname).read_text()

OBSERVATION_SCHEMA = """
The observation data represents a League of Legends game state. Let me explain the key parts:

1. Time Format (T{seconds}):
   Shows game time in seconds
   
2. Champion State (ME/ENY):
   - Health/Mana as percentages
   - Position as (y, x) coordinates
   - Level and gold
   - Kills/Deaths
   
3. Ability Status (QWER):
   - Cooldowns in seconds
   - 0 means ability is ready
   
4. Projectiles (PROJ):
   - Each [owner,dx,dy,speed,name]
   - dx/dy shows direction relative to player
   - Negative dx means projectile moving left
   - Negative dy means projectile moving down
   
5. Available Actions (ACT):
   - List of currently possible actions
   - move: Can move
   - auto: Can auto attack
   - q/w/e/r: Can cast abilities

For example:
T12262|ME80,100,(9553,9271),L1,G35,K0D0|Q0W0E0R0|ENY50,80,(333,36),L1|PROJ[1234,-100,50,2000,EzQ]|ACT[move,q]

This shows:
- 12262 seconds into game
- I'm at 80% HP, full mana, position (9553,9271)
- Level 1, 35 gold, no kills/deaths
- All abilities ready (0 cooldown)
- Enemy at 50% HP, 80% mana, 333 units right and 36 units up
- One enemy projectile moving left and slightly up

This format preserves all tactical information while being much more compact than raw JSON.
"""
# OBSERVATION_SCHEMA = """
# {
#   "type": "object",
#   "properties": {
#     "observation": {
#       "type": "object",
#       "properties": {
#         "game_time": {
#           "type": "number",
#           "description": "Current game time"
#         },
#         "champ_units": {
#           "type": "array",
#           "items": {
#             "type": "object",
#             "properties": {
#               "user_id": {
#                 "type": "integer",
#                 "description": "User ID of the champion"
#               },
#               "net_id": {
#                 "type": "integer",
#                 "description": "Network ID of the champion"
#               },
#               "position": {
#                 "type": "object",
#                 "properties": {
#                   "X": { "type": "number" },
#                   "Y": { "type": "number" }
#                 }
#               },
#               "facing_angle": { "type": "number" },
#               "max_hp": { "type": "number" },
#               "current_hp": { "type": "number" },
#               "hp_regen": { "type": "number" },
#               "max_mp": { "type": "number" },
#               "current_mp": { "type": "number" },
#               "mp_regen": { "type": "number" },
#               "attack_damage": { "type": "number" },
#               "attack_speed": { "type": "number" },
#               "alive": { "type": "number" },
#               "level": { "type": "integer" },
#               "armor": { "type": "number" },
#               "mr": { "type": "number" },
#               "current_gold": { "type": "number" },
#               "death_count": { "type": "integer" },
#               "kill_count": { "type": "integer" },
#               "move_speed": { "type": "number" },
#               "current_xp": { "type": "number" },
#               "my_team": { "type": "number" },
#               "neutal": { "type": "number" },
#               "dx_to_me": { "type": "number" },
#               "dy_to_me": { "type": "number" },
#               "distance_to_me": { "type": "number" },
#               "q_cooldown": { "type": "number" },
#               "q_level": { "type": "integer" },
#               "w_cooldown": { "type": "number" },
#               "w_level": { "type": "integer" },
#               "e_cooldown": { "type": "number" },
#               "e_level": { "type": "integer" },
#               "r_cooldown": { "type": "number" },
#               "r_level": { "type": "integer" },
#               "sum_1_cooldown": { "type": "number" },
#               "sum_2_cooldown": { "type": "number" }
#             }
#           }
#         },
#         "projectiles": {
#           "type": "array",
#           "items": {
#             "type": "object",
#             "properties": {
#               "position": {
#                 "type": "object",
#                 "properties": {
#                   "X": { "type": "number" },
#                   "Y": { "type": "number" }
#                 }
#               },
#               "my_team": { "type": "number" },
#               "neutral": { "type": "number" },
#               "dx_to_me": { "type": "number" },
#               "dy_to_me": { "type": "number" },
#               "distance_to_me": { "type": "number" },
#               "speed": { "type": "number" },
#               "owner_id": { "type": "integer" },
#               "projectile_name": { "type": "string" },
#               "has_collided": { "type": "boolean" },
#               "hit_net_ids": {
#                 "type": "array",
#                 "items": { "type": "integer" }
#               }
#             }
#           }
#         }
#     }
#   },
#   "required": ["observation"]
# }
# """

ACTION_SPEC = """
<spell_options>
SPELL_OPTIONS = (
    ("Q", 0),
    ("W", 1),
    ("E", 2),
    ("R", 3),
    ("Sum1", 4),
    ("Sum2", 5)
)
</spell_options>
<action_ids>
0 - no_op
1 - move
2 - spell
</action_ids>
<arg_type>
Point - (y, x) (Range between 0 and 16000 inclusive)
</arg_type>
<action_args>
no_op - None
move  - Point (y, x)
spell - Spell Option, Point
</action_args>

<example>
<action_name>spell</action_name>
<action_id>2</action_id>
<action_args>
[[0],[0, 8000]]
</action_args>
</example>
"""

SPEED = "<priority value='LIFE AND DEATH' Crucially, limit your thinking to under 1000 words. We want fast iteration.</priority>"
TRAINING_PROMPT = lambda current_policy, data: f"""
You are T1 Faker, the best league of legends player in the world.

You are observing the behaviour of an autonomous League of Legends scripting bot.
The bot is currently acting on a hand-crafted python based policy.
You will be provided the observations, actions and calculated reward for each timestep in game.

You must improve the policy of the agent based on its gathered experience playing the game.
You must determine instances where either its reward dropped immediately, or it performed
an action later down the line which caused its reward to drop (getting hit by an enemy projectile,
dying, etc.)

{SPEED}

<reward-shaping>
def calc_reward(self, last_obs, obs):
  # Returns the cumulative reward for an observation.

  reward = 0

  # Winning (+5) Zero-Sum
  winning_weighting = 5.0
  if self._state == environment.StepType.LAST: # Last observation for episode
      if obs["me_unit"].kill_count > obs["enemy_unit"].kill_count:
          winning_reward = winning_weighting
      elif obs["me_unit"].kill_count < last_obs["enemy_unit"].kill_count:
          winning_reward = -winning_weighting
      else:
          winning_reward = 0
      reward += winning_reward
      print("Winning Reward:",
        winning_reward,
        obs["me_unit"].kill_count,
        obs["enemy_unit"].kill_count)

  # Death (-1)
  death_weighting = -1
  death_reward = 0
  if obs["me_unit"].death_count > last_obs["me_unit"].death_count:
      death_reward += death_weighting
  if obs["enemy_unit"].death_count > last_obs["enemy_unit"].death_count:
      death_reward += -death_weighting
  if obs["me_unit"].death_count == last_obs["me_unit"].death_count and \
          obs["enemy_unit"].death_count == last_obs["enemy_unit"].death_count:
      death_reward = 0
  reward += death_reward
  # print("Death Reward:", death_reward)

  # XP Gained (+0.002) Zero-Sum
  xp_weighting = 0.002
  me_xp_diff = obs["me_unit"].current_xp - last_obs["me_unit"].current_xp
  me_xp_reward = me_xp_diff * xp_weighting
  enemy_xp_diff = obs["enemy_unit"].current_xp - last_obs["enemy_unit"].current_xp
  enemy_xp_reward = -(enemy_xp_diff * xp_weighting)
  xp_reward = me_xp_reward + enemy_xp_reward # Zero-Sum
  reward += xp_reward
  # print("XP Reward:", xp_reward)
  
  # Gold Gained (+0.006) Zero-Sum
  gold_weighting = 0.006
  me_gold_diff = obs["me_unit"].current_gold - last_obs["me_unit"].current_gold
  me_gold_reward = me_gold_diff * gold_weighting
  enemy_gold_diff = obs["enemy_unit"].current_gold - last_obs["enemy_unit"].current_gold
  enemy_gold_reward = -(enemy_gold_diff * gold_weighting)
  gold_reward = me_gold_reward + enemy_gold_reward
  reward += gold_reward
  # print("Gold Reward:", gold_reward)

  # Health Changed (+2) Zero-Sum
  hp_weighting = 2.0
  def hp_change_to_reward(x): return (x + 1 - (1 - x)**4) / 2
  me_cur_hp_diff  = obs["me_unit"].current_hp / obs["me_unit"].max_hp
  me_last_hp_diff = last_obs["me_unit"].current_hp / last_obs["me_unit"].max_hp
  me_hp_diff = me_cur_hp_diff - me_last_hp_diff
  me_hp_reward = hp_change_to_reward(me_hp_diff) * hp_weighting

  enemy_cur_hp_diff  = obs["enemy_unit"].current_hp / obs["enemy_unit"].max_hp
  enemy_last_hp_diff = last_obs["enemy_unit"].current_hp / last_obs["enemy_unit"].max_hp
  enemy_hp_diff = enemy_cur_hp_diff - enemy_last_hp_diff
  enemy_hp_reward = -(hp_change_to_reward(enemy_hp_diff) * hp_weighting)

  hp_reward = me_hp_reward + enemy_hp_reward
  reward += hp_reward
  # print("HP Reward:", hp_reward)

  # Mana Changed (+0.75)
  mp_weighting = 0.75
  me_cur_mp_diff  = obs["me_unit"].current_mp / obs["me_unit"].max_mp
  me_last_mp_diff = last_obs["me_unit"].current_mp / last_obs["me_unit"].max_mp
  me_mp_diff = me_cur_mp_diff - me_last_mp_diff
  me_mp_reward = me_mp_diff * mp_weighting

  enemy_cur_mp_diff  = obs["enemy_unit"].current_mp / obs["enemy_unit"].max_mp
  enemy_last_mp_diff = last_obs["enemy_unit"].current_mp / last_obs["enemy_unit"].max_mp
  enemy_mp_diff = enemy_cur_mp_diff - enemy_last_mp_diff
  enemy_mp_reward = -(enemy_mp_diff * mp_weighting)

  mp_reward = me_mp_reward + enemy_mp_reward
  reward += mp_reward
  # print("MP Reward:", mp_reward)

  # Killed Hero (+1, -0.6)
  kill_weighting = +1
  kill_reward = 0
  if obs["me_unit"].kill_count > last_obs["me_unit"].kill_count:
      kill_diff = obs["me_unit"].kill_count - last_obs["me_unit"].kill_count
      kill_reward += kill_diff * kill_weighting
  if obs["enemy_unit"].kill_count > last_obs["enemy_unit"].kill_count:
      kill_diff = obs["enemy_unit"].kill_count - last_obs["enemy_unit"].kill_count
      kill_reward += -(kill_diff * kill_weighting)
  if obs["me_unit"].kill_count == last_obs["me_unit"].kill_count and \
          obs["enemy_unit"].kill_count == last_obs["enemy_unit"].kill_count:
      kill_reward = 0
  reward += kill_reward
  # print("Kill Reward:", kill_reward)

  # Lane Assignment (-0.15 * seconds out of assigned lane)
  pass # Empty for now, not primary concern
  
  # print("Reward:", reward, end = "\n\n")
  return reward
</reward-shaping>

<observation-spec>
{OBSERVATION_SCHEMA}
</observation-spec>

<action-spec>
{ACTION_SPEC}
</action-spec>

<current-policy>
{current_policy}
</current-policy>

<experience>
{data}
</experience>

<example>
<thinking>
During this episode, I constantly lost reward as I was hit by skillshots frequently due to being poor at dodging them.
Therefore, I'm now going to try wiggling my character model rapidly moving back and forth before comitting to
a skillshot, to make it harder for the enemy Ezreal to land a skillshot on me.
<thinking>
<policy>

def act(self, obs):
    import math # YOU MUST IMPORT THIS MODULE EVERY SINGLE TIME. DO NOT IMOPRT ANY OTHER MODULES
    
    # Get our champion and enemy champion info
    my_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 1)
    enemy_champ = next(unit for unit in observation["champ_units"] if unit["my_team"] == 0)
    nearby_projectiles = [p for p in observation["projectiles"] 
                         if p["my_team"] == 0 and p["distance_to_me"] < 800]

    # High priority: Dodge enemy skillshots (prevents HP loss which has high negative reward)
    if nearby_projectiles:
        proj = nearby_projectiles[0]
        # Calculate perpendicular dodge direction
        dodge_x = proj["dy_to_me"]
        dodge_y = -proj["dx_to_me"]
        magnitude = (dodge_x**2 + dodge_y**2)**0.5
        if magnitude > 0:
            dodge_x = (dodge_x/magnitude * 200) + my_champ["position"]["X"]
            dodge_y = (dodge_y/magnitude * 200) + my_champ["position"]["Y"]
            return (1, [dodge_y, dodge_x])

    # Offensive opportunities (for kill rewards and HP damage)
    if enemy_champ["distance_to_me"] < 600:
        # Check if we have HP advantage
        my_hp_percent = my_champ["current_hp"] / my_champ["max_hp"]
        enemy_hp_percent = enemy_champ["current_hp"] / enemy_champ["max_hp"]
        
        if my_hp_percent > enemy_hp_percent + 0.2:  # We have significant HP advantage
            # Cast Q if available and in range
            if my_champ["q_cooldown"] == 0:
                return (2, [[0], [enemy_champ["position"]["Y"], enemy_champ["position"]["X"]]])
        else:
            # Maintain safe distance if we don't have HP advantage
            retreat_x = my_champ["position"]["X"] - enemy_champ["dx_to_me"]
            retreat_y = my_champ["position"]["Y"] - enemy_champ["dy_to_me"]
            return (1, [retreat_y, retreat_x])

    # Resource management (MP has moderate reward weight)
    if my_champ["current_mp"] / my_champ["max_mp"] < 0.3:
        # Play conservatively when low on mana
        safe_x = my_champ["position"]["X"] + (enemy_champ["dx_to_me"] * -1.5)
        safe_y = my_champ["position"]["Y"] + (enemy_champ["dy_to_me"] * -1.5)
        return (1, [safe_y, safe_x])

    # Default behavior: Maintain optimal trading range
    optimal_range = 500  # Adjust based on champion
    if enemy_champ["distance_to_me"] > optimal_range:
        # Move closer
        approach_x = my_champ["position"]["X"] + enemy_champ["dx_to_me"] * 0.5
        approach_y = my_champ["position"]["Y"] + enemy_champ["dy_to_me"] * 0.5
        return (1, [approach_y, approach_x])
    else:
        # Orbit around enemy while in range
        orbit_angle = math.atan2(enemy_champ["dy_to_me"], enemy_champ["dx_to_me"])
        orbit_x = enemy_champ["position"]["X"] + math.cos(orbit_angle + math.pi/4) * optimal_range
        orbit_y = enemy_champ["position"]["Y"] + math.sin(orbit_angle + math.pi/4) * optimal_range
        return (1, [orbit_y, orbit_x])
</policy>
</example>

<task>
You must now return the new policy based on <example></example>.
Simply infill and complete the tags below.
DO NOT PROVIDE ANY PREAMBLE OR IRRELEVANT TEXT, FILL IN THE TEMPLATE AS REQUIRED.
</task>

<thinking>"""

import json

class Policy():
  _policy = ""
  _policy_validator = PolicyValidator()
  _act_function = None
  
  def __init__(self):
     self.update_policy(INITIAL_POLICY)
     
  def update_policy(self, policy_code: str):
    # Store the validated policy
    self._policy = policy_code
    
    # Create namespace for execution
    namespace = {}
    exec(policy_code, namespace)
    
    # Store the act function
    self._act_function = namespace['act']

  def compress_observation(self, obs: dict) -> str:
    print(">>> OBS 'ERE:", obs)
    # obs = obs.observation
    # Get my unit and enemy unit
    me = next(u for u in obs["champ_units"] if u["my_team"] == 1.0)
    enemy = next(u for u in obs["champ_units"] if u["my_team"] == 0.0)
    
    # Main state sections
    time_str = f"T{int(obs['game_time'])}"
    
    # My state (hp%, mp%, pos, level, gold, KD)
    me_str = (f"ME{int(me['current_hp']/me['max_hp']*100)},"
              f"{int(me['current_mp']/me['max_mp']*100)},"
              f"({int(me['position']['X'])},{int(me['position']['Y'])}),"
              f"L{me['level']},G{int(me['current_gold'])},"
              f"K{me['kill_count']}D{me['death_count']}")
    
    # Cooldowns
    cd_str = f"Q{int(me['q_cooldown'])}W{int(me['w_cooldown'])}E{int(me['e_cooldown'])}R{int(me['r_cooldown'])}"
    
    # Enemy state (hp%, mp%, relative pos, level)
    enemy_str = (f"ENY{int(enemy['current_hp']/enemy['max_hp']*100)},"
                 f"{int(enemy['current_mp']/enemy['max_mp']*100)},"
                 f"({int(enemy['dx_to_me'])},{int(enemy['dy_to_me'])}),"
                 f"L{enemy['level']}")
    
    # Projectiles
    proj_str = "PROJ" + "".join([
        f"[{p['owner_id']},{int(p['dx_to_me'])},{int(p['dy_to_me'])},{int(p['speed'])},{p['projectile_name']}]"
        for p in obs["projectiles"]
    ])
    
    # Available actions
    actions = [k[4:] for k, v in obs["available_actions"].items() if v and k.startswith("can_")]
    act_str = f"ACT[{','.join(actions)}]"
    
    return "|".join([time_str, me_str, cd_str, enemy_str, proj_str, act_str])

  def train(self, data: Union[str, list, dict]):
    # Handle different input types
    if isinstance(data, str):
        # If it's a JSON string, parse it
        json_data = json.loads(data)
    elif isinstance(data, list):
        # If it's already a list, use directly
        json_data = data
    elif isinstance(data, dict):
        # If it's a single observation
        json_data = [data]
    else:
        raise TypeError(f"Expected str, list or dict, got {type(data)}")
    # json_data = json.loads(data)  # Parse JSON if it's a string
    
    # If it's a list of observations, compress each one
    # if isinstance(json_data, list):
    #     compressed_data = "\n".join(self.compress_observation(obs) for obs in json_data)
    # else:
    #     compressed_data = self.compress_observation(json_data)

    # Convert observations to compressed format
    compressed_data = "\n".join(
        self.compress_observation(obs["obs"]["observation"] if "obs" in obs else obs)
        for obs in json_data
    )

    print("\n=== SENDING TO MODEL ===")
    print("Compressed Data Sample:", compressed_data.split('\n')[:2])  # First 2 observations
    
    prompt = TRAINING_PROMPT(self._policy, compressed_data)
    print("\nPrompt Length:", len(prompt))
    print("Prompt Preview:", prompt[:500], "...\n")  # First 500 chars
    
    res = invoke_model(prompt)
    print("\n=== MODEL RESPONSE ===")
    print("Raw Response:", res)
    print("Response Length:", len(res) if res else "None")
    
    if not res:
        print("ERROR: No response from model")
        return

    # print(">>> TRAINING DATA SIZE:", len(compressed_data))
    # res = invoke_model(TRAINING_PROMPT(self._policy, compressed_data))

    # print(">>> TRAINING RUN OUTPUT:", res)

    # Extract code between <policy> tags using string manipulation or regex
    try:
        # Find the content between <policy> and </policy> tags
        policy_start = res.find('<policy>') + len('<policy>')
        policy_end = res.find('</policy>')
        policy_code = res[policy_start:policy_end].strip()

        thinking_end = res.find('</thinking>')
        thinking_code = res[0:thinking_end].strip()

        if policy_start >= 0 and policy_end >= 0:
          try:
            tree = ast.parse(policy_code)
            validator = PolicyValidator()
            validator.visit(tree)
            
            if not validator.has_act_method:
                raise ValueError("Policy must contain act(self, observation) method")
            
            if validator.errors:
                raise ValueError(f"Policy validation failed: {'; '.join(validator.errors)}")
                
            self.update_policy(policy_code)

            model_checkpoint_fname = f"./checkpoints/{datetime.datetime.now().isoformat()}.py"
            thinking_checkpoint_fname = f"./checkpoints/{datetime.datetime.now().isoformat()}_thinking.txt"
            prompt_checkpoint_fname = f"./checkpoints/{datetime.datetime.now().isoformat()}_prompt.txt"
            with open(model_checkpoint_fname, "w+") as f: f.write(policy_code)
            with open(thinking_checkpoint_fname, "w+") as f: f.write(thinking_code)
            with open(prompt_checkpoint_fname, "w+") as f: f.write(prompt)

          except SyntaxError as e:
            raise ValueError(f"Policy contains invalid Python syntax: {e}")
    except Exception as e:
        print(f"Error extracting policy: {e}")
        return
  def act(self, obs):
    if self._act_function is None:
      raise ValueError("No policy has been trained yet")
    
    # Call the stored act function with self and observation
    return self._act_function(self, obs)

# !WINEPREFIX=~/.wine winetricks dxvk

from pylol.env import lol_env
from pylol.env import run_loop
from pylol.agents import base_agent, random_agent, scripted_agent
from pylol.lib import actions

# Settings
feature_map_size = 16000
feature_move_range = 8
player_list = "Ezreal.BLUE,Ezreal.PURPLE" # Comma-separated list of `Player.Team`
map = "Old Summoners Rift" # ["New Summoners Rift", "Howling Abyss"]
max_steps = 1000 # 100 steps / 4 obs_per_sec := 25 seconds
max_episodes = 3 # When set to 0, ignores this variable
host = "127.0.1.1"
config_path = "./config_dirs.txt"
obs_sec = 4
max_steps_per_episode = 100 # 100 steps := 25 secs
# run_client = False
# TRAIN = True

def constrain_movement(x, y, me):
  """
  p1start: controller.player_teleport(1, 6900.0, 6900.0)
  p2start: controller.player_teleport(2, 7100.0, 7100.0)
  """
  my_x = me["position"]["X"]
  my_y = me["position"]["Y"]
  enemy_champ_x_delta_og = (x - my_x) # 1 - 2
  enemy_champ_y_delta_og = (y - my_y) # 1 - 2

  enemy_champ_x_delta = max(-400, enemy_champ_x_delta_og)
  enemy_champ_x_delta = min(+400, enemy_champ_x_delta)
  enemy_champ_x_delta = round(enemy_champ_x_delta / 100)
  enemy_champ_x_delta += 4

  enemy_champ_y_delta = max(-400, enemy_champ_y_delta_og)
  enemy_champ_y_delta = min(+400, enemy_champ_y_delta)
  enemy_champ_y_delta = round(enemy_champ_y_delta / 100)
  enemy_champ_y_delta += 4

  new_x = my_x + ((enemy_champ_x_delta-4)*100)
  new_y = my_y + ((enemy_champ_y_delta_og-4)*100)

  # if new_x < 6900-1000 or new_x > 7100+1000:
  #    enemy_champ_x_delta = 4
  # if new_y < 6900-1000 or new_y > 7100+1000:
  #    enemy_champ_y_delta = 4

  out = [enemy_champ_x_delta, enemy_champ_y_delta]
  print("MOVE:", out, new_x, new_y, my_x, my_y)
  return out

def normalize_to_move_range(x, y, move_range=8):
  # y *= -1
  # Clamp values between -1 and 1 first
  magnitude = (x**2 + y**2)**0.5
  if magnitude > 0:
      x = x/magnitude
      y = y/magnitude
      
  # Scale to move range (0 to 7)
  x = ((x + 1) * (move_range-1))/2  # Maps -1,1 to 0,7
  y = ((y + 1) * (move_range-1))/2
  
  return [[x, y]]

class CustomAgent(base_agent.BaseAgent):
    def __init__(self):
        super().__init__()
        self._time_to_game = time.time()
        self._data = []
        self._policy = Policy()
        self._episode_buffer = 1
        self._episode_idx = 0
        self._time_to_game = time.time()
        self._first_rec = False
        self._done = False

    def step(self, obs):
        super(CustomAgent, self).step(obs)
        if not self._first_rec:
           self._first_rec = True
           print("time to get into game:", time.time() - self._time_to_game)

        # print(">>> RAW OBS:", obs.observation)

        # Collect data
        # Note: You might want to filter this. Sending EVERY frame is too much tokens.
        # Maybe send every 10th frame, or only frames where health changed.
        if not obs.last():
            # Basic sampling to save context window
            # if obs.observation["observation"]["game_time"] % 1.0 < 0.1:
            self._data.append({
                "rew": obs.reward,
                "obs": obs.observation
            })

        if obs.last():
            # Trigger async training at end of episode
            self._episode_idx = (self._episode_idx + 1) % self._episode_buffer
            if self._data and TRAIN and self._episode_idx == 0:
              self._policy.train(self._data)
              self._data = [] # Clear immediately for next game
              self._done = True
              exit()

        else:
            action_id, args = self._policy.act(obs.observation["observation"])
            
            # Normalize movement logic and constrain movement
            if action_id == 1:
                # Ensure args are floats/ints not arrays if your policy returns weird stuff
                me = next(u for u in obs.observation["observation"]["champ_units"] if u["my_team"] == 1.0)
                # args = args[0]
                args = constrain_movement(args[0], args[1], me)
                # if oob:
                #   normalized = [[4, 4]]
                # else:
                # normalized = normalize_to_move_range(args[0], args[1])
                args = [args]
            
            return actions.FunctionCall(action_id, args)
        
# Setup the Game
players = []
agents = []
for player in player_list.split(","):
  c, t = player.split(".")
  players.append(lol_env.Agent(champion=c, team=t))
  # agents.append(base_agent.BaseAgent())
  # agents.append(base_agent.BaseAgent())
  agents.append(CustomAgent())
  agents.append(CustomAgent())
#   agents.append(base_agent.BaseAgent())
  # agents.append(CustomAgent())

try:
  # Run the Game
  with lol_env.LoLEnv(
    host=host,
    map_name=map,
    players=players,
    agent_interface_format=lol_env.parse_agent_interface_format(
      feature_map=feature_map_size,
      feature_move_range=feature_move_range
    ),
    human_observer=run_client,
    cooldowns_enabled=False,
    config_path=config_path,
    multiplier=obs_sec,
    max_steps_per_episode=max_steps_per_episode
  ) as env:
      run_loop.run_loop(agents, env, max_episodes=max_episodes, max_steps=max_steps)
finally:
  pass
  # visualizer.close()