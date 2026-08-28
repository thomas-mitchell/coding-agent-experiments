# Chapter 27: Performance Optimization

As the game grows — hundreds of entities, large maps, complex AI — performance matters. This chapter covers profiling, numpy vectorization, spatial hashing, and other techniques to keep the game running smoothly.

## Profiling First

Never optimize without measuring. Python's built-in profiler identifies bottlenecks:

```bash
python -m cProfile -o profile.stats main.py
```

```python
import cProfile

def profile_game():
    """Run the game with profiling enabled."""
    cProfile.runctx('main()', globals(), locals(), 'profile_output')
```

Use `snakeviz` or `pstats` to analyze results:
```bash
pip install snakeviz
snakeviz profile_output
```

## Numpy Vectorization

The biggest performance gains come from vectorized numpy operations instead of Python loops:

### Slow (Python loop)
```python
def count_visible_slow(game_map):
    count = 0
    for y in range(game_map.height):
        for x in range(game_map.width):
            if game_map.visible[y, x]:
                count += 1
    return count
```

### Fast (Numpy)
```python
def count_visible_fast(game_map):
    return int(game_map.visible.sum())
```

### Rendering with Numpy

```python
def render_tiles_fast(console, game_map, visible, explored):
    """Render tiles using numpy operations."""
    import numpy as np
    
    # Build color arrays for the entire map at once
    light_fg = game_map.tiles["light_fg"]
    dark_fg = game_map.tiles["dark_fg"]
    light_bg = game_map.tiles["light_bg"]
    dark_bg = game_map.tiles["dark_bg"]
    
    # Choose light or dark colors based on visibility
    fg = np.where(visible, light_fg, np.where(explored, dark_fg, 0))
    bg = np.where(visible, light_bg, np.where(explored, dark_bg, 0))
    
    # Assign to console in one operation
    console.rgb.fg[:console.height, :console.width] = fg[:console.height, :console.width]
    console.rgb.bg[:console.height, :console.width] = bg[:console.height, :console.width]
```

## Spatial Hashing

For collision detection and neighbor queries, spatial hashing is faster than checking every entity:

```python
class SpatialHash:
    def __init__(self, cell_size: int = 10):
        self.cell_size = cell_size
        self.grid: dict[tuple[int, int], list] = {}
    
    def _get_cell(self, x: int, y: int) -> tuple[int, int]:
        return (x // self.cell_size, y // self.cell_size)
    
    def insert(self, entity, x: int, y: int) -> None:
        cell = self._get_cell(x, y)
        if cell not in self.grid:
            self.grid[cell] = []
        self.grid[cell].append(entity)
    
    def query_radius(self, x: int, y: int, radius: int) -> list:
        """Find all entities within radius."""
        results = []
        min_cell = self._get_cell(x - radius, y - radius)
        max_cell = self._get_cell(x + radius, y + radius)
        
        for cx in range(min_cell[0], max_cell[0] + 1):
            for cy in range(min_cell[1], max_cell[1] + 1):
                cell = (cx, cy)
                if cell in self.grid:
                    for entity in self.grid[cell]:
                        results.append(entity)
        return results
    
    def clear(self) -> None:
        self.grid.clear()
```

## FOV Optimization

Only recompute FOV when the player moves:

```python
last_fov_position = None

def maybe_update_fov(game_map, player_pos):
    """Only recompute FOV if player moved."""
    global last_fov_position
    if (player_pos.x, player_pos.y) != last_fov_position:
        game_map.compute_fov(player_pos.x, player_pos.y)
        last_fov_position = (player_pos.x, player_pos.y)
```

## Object Pooling

Reuse entity objects instead of creating/destroying:

```python
class EntityPool:
    def __init__(self, registry):
        self.registry = registry
        self.available = []
    
    def get(self) -> tcod.ecs.Entity:
        if self.available:
            return self.available.pop()
        return self.registry.new_entity()
    
    def release(self, entity) -> None:
        # Clear components and return to pool
        entity.components.clear()
        entity.tags.clear()
        self.available.append(entity)
```

## Avoiding Common Pitfalls

1. **Don't query every frame** — cache results, only update when state changes
2. **Minimize entity creation** — pre-spawn enemies, use pools
3. **Batch numpy operations** — prefer vectorized over loops
4. **Lazy FOV computation** — only when player moves
5. **Limit AI pathfinding** — cache paths, only recompute when target moves

## Exercises

- Profile the game and identify the top 3 bottlenecks
- Implement chunked map loading for very large maps
- Add a performance overlay showing FPS and entity count
- Implement spatial hashing for the item/entity lookup system
