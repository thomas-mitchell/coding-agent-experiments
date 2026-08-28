"""
Entity and EntityManager handling dynamic component attachment and queries.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Type, TypeVar, Iterator

T = TypeVar("T")


@dataclass
class Entity:
    """Unique identity token representing a game object, actor, or item."""
    id: int
    name: str
    tags: set[str] = field(default_factory=set)


class EntityManager:
    """
    Central storage and querying engine for entities and their components.
    """
    def __init__(self) -> None:
        self._next_id: int = 1
        self._entities: dict[int, Entity] = {}
        self._components: dict[Type[Any], dict[int, Any]] = {}

    def create_entity(self, name: str, tags: set[str] | None = None) -> Entity:
        entity_id = self._next_id
        self._next_id += 1
        entity = Entity(id=entity_id, name=name, tags=tags or set())
        self._entities[entity_id] = entity
        return entity

    def destroy_entity(self, entity_id: int) -> None:
        if entity_id in self._entities:
            del self._entities[entity_id]
            for comp_dict in self._components.values():
                comp_dict.pop(entity_id, None)

    def get_entity(self, entity_id: int) -> Entity | None:
        return self._entities.get(entity_id)

    def add_component(self, entity_id: int, component: Any) -> None:
        comp_type = type(component)
        if comp_type not in self._components:
            self._components[comp_type] = {}
        self._components[comp_type][entity_id] = component

    def get_component(self, entity_id: int, comp_type: Type[T]) -> T | None:
        return self._components.get(comp_type, {}).get(entity_id)

    def has_component(self, entity_id: int, comp_type: Type[Any]) -> bool:
        return entity_id in self._components.get(comp_type, {})

    def remove_component(self, entity_id: int, comp_type: Type[Any]) -> None:
        if comp_type in self._components:
            self._components[comp_type].pop(entity_id, None)

    def query(self, *comp_types: Type[Any]) -> Iterator[tuple[Entity, tuple[Any, ...]]]:
        """
        Queries all entities possessing every component type in comp_types.
        """
        if not comp_types:
            return

        # Find smallest component set to iterate over
        sorted_types = sorted(comp_types, key=lambda t: len(self._components.get(t, {})))
        primary_type = sorted_types[0]
        primary_dict = self._components.get(primary_type, {})

        for entity_id, primary_comp in primary_dict.items():
            entity = self._entities.get(entity_id)
            if not entity:
                continue

            matches = True
            other_comps: list[Any] = []
            for t in comp_types:
                comp = self._components.get(t, {}).get(entity_id)
                if comp is None:
                    matches = False
                    break
                other_comps.append(comp)

            if matches:
                yield entity, tuple(other_comps)
