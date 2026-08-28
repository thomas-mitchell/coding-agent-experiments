# Systemic Depths: Designing & Architecting Emergent Traditional Roguelikes

A practitioner-focused guide and companion codebase exploring the mathematics, systems architecture, and design patterns required to build rich, combinatorial, emergent traditional roguelikes.

---

## 📖 Book Structure

The complete book text is organized in the `book/` directory:

- **[Preface](book/preface.md)**: Audience, scope, prerequisites, and the systemic philosophy.
- **Part I: Philosophy, Foundations & Architecture of Emergence**
  - [Chapter 1: The Anatomy of Emergence in Roguelikes](book/part1_foundations/ch01_anatomy_of_emergence.md)
  - [Chapter 2: Architectural Patterns for Interconnected Systems](book/part1_foundations/ch02_architecture_interconnected_systems.md)
- **Part II: The Reactive World - Space, Materials & Physics**
  - [Chapter 3: Spatial Models, Layered Topologies & Vision](book/part2_reactive_world/ch03_spatial_models_vision.md)
  - [Chapter 4: Material Systems & Cellular Automata](book/part2_reactive_world/ch04_material_systems_cellular_automata.md)
  - [Chapter 5: Verbs, Affordances & The Interaction Matrix](book/part2_reactive_world/ch05_verbs_affordances_interaction_matrix.md)
- **Part III: Entities, Items, Status & Magic**
  - [Chapter 6: Dynamic Entity Composition & Reactive Status Effects](book/part3_entities_items_magic/ch06_dynamic_entities_status_effects.md)
  - [Chapter 7: Emergent Item Systems, Alchemy & Deduction](book/part3_entities_items_magic/ch07_emergent_items_alchemy.md)
  - [Chapter 8: Magic, Projectiles & Spatial Mechanics](book/part3_entities_items_magic/ch08_magic_projectiles_spatial.md)
- **Part IV: Intelligence, Perception & Ecology**
  - [Chapter 9: The Living Dungeon: AI & Ecosystems](book/part4_intelligence_ecology/ch09_living_dungeon_ai_ecology.md)
  - [Chapter 10: Information, Perception & Player Agency](book/part4_intelligence_ecology/ch10_information_perception_agency.md)
- **Part V: Procedural Generation for Systemic Play**
  - [Chapter 11: Level Generation with Tactical Affordances](book/part5_procgen_systemic/ch11_level_gen_tactical_affordances.md)
  - [Chapter 12: Procedural Encounters, Synergies & Bounded Chaos](book/part5_procgen_systemic/ch12_procedural_encounters_bounded_chaos.md)
- **Part VI: Architecture, Balance, Testing & Production**
  - [Chapter 13: Determinism, State Serialization & Replays](book/part6_architecture_production/ch13_determinism_testing.md)
  - [Chapter 14: Balancing Emergent Systems](book/part6_architecture_production/ch14_balancing_emergent_systems.md)
  - [Chapter 15: Reference Engine Deep Dive & Extension Guide](book/part6_architecture_production/ch15_reference_engine_walkthrough.md)

---

## 🚀 Running the Companion Code

### Running Unit Tests
```bash
# Run all unit and integration tests
python -m unittest discover -s tests -v
```

### Running the Interactive / Simulation Demo
```bash
python examples/play_demo.py
```

### Compiling the Book to PDF
```bash
# Compile all 15 chapters and preface into a publication-quality PDF
python scripts/build_pdf.py

# Specify a custom output path
python scripts/build_pdf.py --output "dist/My_Roguelike_Book.pdf"
```

