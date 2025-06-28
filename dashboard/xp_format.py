def parse_xp_content(content):
    try:
        _, xp, level = content.split(":")
        return int(xp), int(level)
    except:
        return 0, 0

def make_xp_content(user_id, xp, level):
    return f"{user_id}:{xp}:{level}"

def calculate_level(xp):
    level = 0
    while xp >= (level + 1) ** 2 * 100:
        level += 1
    return level
