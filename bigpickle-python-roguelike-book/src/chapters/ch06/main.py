"""Chapter 6: Basic Components - demonstrating the component library."""
from __future__ import annotations

import tcod
import tcod.ecs
import tcod.event

from components import (
    Position, Renderable, Name, Description, Fighter, XP, AI, AIKind, Item, Inventory,
)

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

TILESET = tcod.tileset.load_truetype_font(
    "data/fonts/dejavu10x10.ttf", tile_width=16, tile_height=16
)


def main() -> None:
    registry = tcod.ecs.Registry()

    # Create player
    player = registry.new_entity()
    player.components[Position] = Position(x=40, y=25)
    player.components[Renderable] = Renderable(char="@", fg=(255, 255, 255))
    player.components[Name] = Name(name="Player")
    player.components[Fighter] = Fighter(hp=30, max_hp=30, power=5, defense=2)
    player.components[XP] = XP(current=0, level=1, xp_to_next=100)
    player.components[Inventory] = Inventory(capacity=10)
    player.tags.add("player")

    # Create an enemy
    enemy = registry.new_entity()
    enemy.components[Position] = Position(x=20, y=15)
    enemy.components[Renderable] = Renderable(char="k", fg=(255, 0, 0))
    enemy.components[Name] = Name(name="Kobold")
    enemy.components[Fighter] = Fighter(hp=8, max_hp=8, power=3, defense=0)
    enemy.components[AI] = AI(kind=AIKind.HOSTILE)
    enemy.tags.add("enemy")
    enemy.tags.add("blocks_movement")

    # Create an item
    item = registry.new_entity()
    item.components[Position] = Position(x=30, y=20)
    item.components[Renderable] = Renderable(char="!", fg=(0, 255, 0))
    item.components[Name] = Name(name="Health Potion")
    item.components[Item] = Item(name="Health Potion", description="Restores 10 HP")
    item.tags.add("item")

    console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="C")

    with tcod.context.new(
        console=console,
        tileset=TILESET,
        title="Chapter 6: Components",
    ) as context:
        while True:
            console.clear()
            
            # Draw all entities with Position and Renderable
            for entity, pos, rend in registry.Q[Position, Renderable]:
                if 0 <= pos.x < SCREEN_WIDTH and 0 <= pos.y < SCREEN_HEIGHT:
                    console.print(x=pos.x, y=pos.y, string=rend.char, fg=rend.fg)

            # Show entity count
            console.print(x=1, y=0, string=f"Entities: {len(list(registry.Q[Position]))}", fg=(128, 128, 128))

            context.present(console)

            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    raise SystemExit()


if __name__ == "__main__":
    main()
