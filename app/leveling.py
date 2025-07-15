LEVEL_XP_THRESHOLDS = [0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500]  # Example thresholds

LEVEL_REWARDS = {
    1: "A favorite snack or treat",
    2: "A day off from studying",
    3: "A new study tool or resource",
    4: "A fun outing or activity",
    5: "A cruise on a yatch"
    # Add more as needed
}

ATTRIBUTE_NAMES = ["memory", "focus", "comprehension", "speed"]

def get_level_progress(user):
    current_xp = user.xp
    current_level = user.level
    current_level_xp = LEVEL_XP_THRESHOLDS[current_level]
    next_level_xp = get_next_level_xp(current_level)
    progress = (current_xp - current_level_xp) / (next_level_xp - current_level_xp)
    return round(progress * 100, 2)  # percent

MAX_LEVEL = len(LEVEL_XP_THRESHOLDS) - 1

def is_max_level(user) -> bool:
    return user.level >= MAX_LEVEL


def get_next_level_xp(current_level: int) -> int:
    if current_level < len(LEVEL_XP_THRESHOLDS) - 1:
        return LEVEL_XP_THRESHOLDS[current_level + 1]
    # If max level, return a very high number
    return float('inf')

def check_level_up(user) -> bool:
    next_level_xp = get_next_level_xp(user.level)
    if user.xp >= next_level_xp:
        return True
    return False

def level_up(user):
    leveled_up = False
    rewards = []
    while check_level_up(user):
        user.level += 1
        user.skill_points += 5
        reward = LEVEL_REWARDS.get(user.level, "Custom reward")
        rewards.append({"level": user.level, "reward": reward})
        leveled_up = True
    return {
        "leveled_up": leveled_up,
        "new_level": user.level,
        "rewards": rewards if rewards else None
    }

def allocate_skill_points(user, allocations: dict):
    total = sum(allocations.values())
    if total > user.skill_points:
        raise ValueError("Not enough skill points.")

    for attr, points in allocations.items():
        if attr not in ATTRIBUTE_NAMES:
            raise ValueError(f"Invalid attribute: {attr}")
        setattr(user, attr, getattr(user, attr, 0) + points)

    user.skill_points -= total
    return user

def get_level_reward(level: int) -> str:
    return LEVEL_REWARDS.get(level, "Custom reward")