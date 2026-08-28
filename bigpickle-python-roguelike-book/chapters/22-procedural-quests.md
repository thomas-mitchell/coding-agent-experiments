# Chapter 22: Procedural Quests

Quests give players objectives beyond survival. Instead of simply descending deeper, players have goals to accomplish — slaying specific enemies, retrieving artifacts, or exploring uncharted territory. Procedurally generated quests ensure variety across playthroughs.

## Quest Design

Good roguelike quests are:

- **Brief**: completable in 1-3 floors
- **Varied**: different types keep gameplay fresh
- **Optional**: players can ignore them without being blocked
- **Rewarding**: XP, items, or equipment as incentives

We implement three quest types: kill, fetch, and explore.

## The Quest Component

```python
@attrs.define
class Quest:
    quest_type: str = ""       # "kill", "fetch", "explore"
    target: str = ""           # enemy name, item name, or "rooms"
    target_count: int = 1      # how many needed
    current_count: int = 0     # progress so far
    reward_xp: int = 0
    reward_item: str = ""      # name of reward item (optional)
    description: str = ""
    completed: bool = False
    dungeon_level: int = 0     # which floor this quest is for


@attrs.define
class QuestLog:
    active_quests: list = attrs.Factory(list)
    completed_quests: list = attrs.Factory(list)
    max_quests: int = 5
```

## The Quest Generator

Quests are generated procedurally based on the current dungeon level:

```python
import random

def generate_quests(dungeon_level: int, registry: tcod.ecs.Registry) -> list[Quest]:
    """Generate quests appropriate for the current dungeon level."""
    quests = []
    
    # Kill quest
    enemy_types = ["Kobold", "Goblin", "Orc", "Troll", "Skeleton"]
    target = random.choice(enemy_types[:min(dungeon_level + 2, len(enemy_types))])
    count = random.randint(2 + dungeon_level, 4 + dungeon_level)
    quests.append(Quest(
        quest_type="kill",
        target=target,
        target_count=count,
        reward_xp=count * 15,
        description=f"Kill {count} {target}s",
        dungeon_level=dungeon_level,
    ))
    
    # Fetch quest (only on floor 2+)
    if dungeon_level >= 2:
        items = ["Ancient Scroll", "Mystic Gem", "Lost Amulet"]
        quest = Quest(
            quest_type="fetch",
            target=random.choice(items),
            target_count=1,
            reward_xp=50 + dungeon_level * 20,
            description=f"Find the {random.choice(items)}",
            dungeon_level=dungeon_level,
        )
        quests.append(quest)
    
    return quests
```

## Kill Quests

Kill quests track how many enemies of a specific type the player has defeated. The combat system checks quest progress after each kill:

```python
def check_kill_quest(player: tcod.ecs.Entity, enemy_name: str) -> None:
    """Check if a kill contributes to any active quest."""
    quest_log = player.components[QuestLog]
    
    for quest in quest_log.active_quests:
        if quest.quest_type == "kill" and quest.target == enemy_name and not quest.completed:
            quest.current_count += 1
            if quest.current_count >= quest.target_count:
                quest.completed = True
                quest_log.completed_quests.append(quest)
                # Award XP
                award_xp(player, quest.reward_xp)
```

## Fetch Quests

Fetch quests require the player to find a specific item. Progress is checked when items are picked up:

```python
def check_fetch_quest(player: tcod.ecs.Entity, item_name: str) -> None:
    """Check if picking up an item completes a fetch quest."""
    quest_log = player.components[QuestLog]
    
    for quest in quest_log.active_quests:
        if quest.quest_type == "fetch" and quest.target == item_name and not quest.completed:
            quest.current_count += 1
            quest.completed = True
            quest_log.completed_quests.append(quest)
            award_xp(player, quest.reward_xp)
```

## Explore Quests

Explore quests require the player to visit a certain percentage of rooms on a floor. Progress is tracked by the game map's `explored` array:

```python
def check_explore_quest(player: tcod.ecs.Entity, game_map: GameMap) -> None:
    """Check explore quest progress."""
    quest_log = player.components[QuestLog]
    
    for quest in quest_log.active_quests:
        if quest.quest_type == "explore" and not quest.completed:
            explored_pct = game_map.explored.sum() / (game_map.width * game_map.height)
            if explored_pct >= 0.7:  # 70% explored
                quest.completed = True
                quest_log.completed_quests.append(quest)
                award_xp(player, quest.reward_xp)
```

## The Quest Log UI

Press `q` to open the quest log:

```
┌─────────────────────────────────────┐
│          QUEST LOG                  │
│                                     │
│  ACTIVE:                            │
│  > Kill 5 Orcs        [3/5] ███..  │
│  > Find the Mystic Gem [0/1] ....   │
│                                     │
│  COMPLETED:                         │
│  ✓ Kill 3 Kobolds     (+45 XP)     │
│                                     │
│  Press ESC to close.                │
└─────────────────────────────────────┘
```

Progress bars show completion at a glance. Completed quests are grayed out.

## Quest Notifications

When a quest is completed, display a prominent notification:

```python
def notify_quest_complete(message_log: MessageLog, quest: Quest) -> None:
    """Display quest completion notification."""
    message_log.add(f"QUEST COMPLETE: {quest.description}!", (255, 215, 0))
    message_log.add(f"Reward: {quest.reward_xp} XP", (127, 127, 255))
```

## Exercises

- Add timed quests (complete before turn limit)
- Create escort quests (protect an NPC)
- Implement chained quests (quest B unlocks after quest A)
- Add difficulty modifiers to quest rewards
- Create quest-giving NPCs
