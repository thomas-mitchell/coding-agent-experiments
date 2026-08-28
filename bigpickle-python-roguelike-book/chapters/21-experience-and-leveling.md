# Chapter 21: Experience and Leveling

Experience and leveling systems provide long-term motivation in a roguelike. When players see their character grow stronger through meaningful choices, every battle becomes more than survival — it becomes investment.

## Experience as Progression

In most roguelikes, defeating enemies awards experience points (XP). Accumulating enough XP triggers a level-up, granting permanent stat increases. This creates a satisfying loop: explore, fight, grow stronger, face harder challenges.

The key design principle is that XP should feel *earned*. Easy kills give less XP. Tough enemies give more. This rewards skillful play and risk-taking.

## The XP Component

We extend our existing `XP` component to track progression:

```python
@attrs.define
class XP:
    current: int = 0
    level: int = 1
    xp_to_next: int = 100
    xp_value: int = 0  # XP awarded when this entity is killed
```

The `xp_value` field is set on enemies. When an enemy dies, its `xp_value` is awarded to the player.

## Earning XP

When an enemy is defeated, the player gains XP:

```python
def award_xp(player: tcod.ecs.Entity, amount: int, message_log: MessageLog) -> None:
    """Award XP to the player."""
    xp = player.components[XP]
    xp.current += amount
    message_log.add(f"You gain {amount} XP.", (127, 127, 255))
    
    # Check for level up
    while xp.current >= xp.xp_to_next:
        level_up(player, message_log)
```

Enemy XP values scale with difficulty:

| Enemy    | XP Value |
|----------|----------|
| Kobold   | 10       |
| Goblin   | 8        |
| Skeleton | 20       |
| Orc      | 25       |
| Troll    | 50       |

## Leveling Up

When the player accumulates enough XP, they level up. The threshold increases each level:

```python
def xp_to_next_level(level: int) -> int:
    """Calculate XP needed for next level."""
    return 100 + (level - 1) * 50
```

On level up, the player chooses a stat increase:

```python
def level_up(player: tcod.ecs.Entity, message_log: MessageLog) -> None:
    """Handle a level up event."""
    xp = player.components[XP]
    fighter = player.components[Fighter]
    
    xp.current -= xp.xp_to_next
    xp.level += 1
    xp.xp_to_next = xp_to_next_level(xp.level)
    
    # Grant choice (handled by input handler)
    message_log.add(f"You reached level {xp.level}! Choose a stat increase.", (255, 255, 0))
```

## Stat Growth

The player chooses one of three options on level up:

1. **+2 Max HP** — increases survivability
2. **+1 Power** — increases damage output
3. **+1 Defense** — reduces incoming damage

```python
def apply_level_up_choice(player: tcod.ecs.Entity, choice: str) -> None:
    """Apply the player's level-up choice."""
    fighter = player.components[Fighter]
    
    if choice == "hp":
        fighter.max_hp += 2
        fighter.hp += 2
    elif choice == "power":
        fighter.power += 1
    elif choice == "defense":
        fighter.defense += 1
```

This choice-based system creates meaningful decisions. A fragile but powerful build focuses on power. A tank build prioritizes HP and defense.

## The Level-Up UI

When the player levels up, the game pauses and presents the choice:

```
┌─────────────────────────────────┐
│      LEVEL UP! (Level 5)        │
│                                 │
│  1. +2 Max HP  (30 → 32)       │
│  2. +1 Power   (8 → 9)         │
│  3. +1 Defense (4 → 5)         │
│                                 │
│  Press 1, 2, or 3 to choose.   │
└─────────────────────────────────┘
```

The input handler enters a `LEVEL_UP` state where only number keys 1-3 are processed.

## XP Bar in the HUD

The experience bar shows progress toward the next level:

```python
def render_xp_bar(console, x, y, width, xp: XP) -> None:
    """Render an XP bar."""
    ratio = xp.current / xp.xp_to_next
    filled = int(width * ratio)
    
    console.print(x=x, y=y, string="[" + "=" * filled + "." * (width - filled) + "]", fg=(127, 127, 255))
```

## Exercises

- Implement a prestige system (reset level for permanent bonuses)
- Add skill trees instead of flat stat increases
- Create XP penalties for dying (keep half XP on death)
- Add bonus XP for combo kills (multiple kills without resting)
- Implement a highest-level leaderboard
