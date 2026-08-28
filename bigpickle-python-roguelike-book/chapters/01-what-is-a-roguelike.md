# Chapter 1: What Is a Roguelike?

Before we write a single line of code, we need to understand what we are building.
The word "roguelike" gets used loosely these days---applied to everything from
match-3 puzzle games to action RPGs with random elements. To build a roguelike, we
need a sharper definition. We need to understand the genre's history, its design
principles, and the specific kind of game this book will teach you to make.

This chapter is a short course in roguelike design. It will not make you an expert in
the genre's history, but it will give you the context you need to make good design
decisions as you build your game. The choices you make about combat, generation, and
player interaction are all downstream of the question: what kind of game am I making?

## A Brief History

The roguelike genre began with a single game: **Rogue**, written in 1980 by Michael
Toy, Glenn Wichman, and Ken Arnold. Rogue ran on Unix terminals and displayed its
dungeon using ASCII characters. The player controlled an `@` symbol navigating a maze
of rooms connected by corridors, fighting monsters represented by letters of the
alphabet, collecting items denoted by punctuation marks.

What made Rogue remarkable was not its graphics---it had none. It was the procedural
generation. Every time you started a new game, the dungeon was different. The levels
were generated algorithmically, the items were randomized, and the monsters were placed
with controlled randomness. This meant that strategy and knowledge mattered more than
memorization. You could not learn the dungeon layout; you had to learn the *principles*
of survival.

Rogue ran on PDP-11 and VAX systems, and it spread through Unix installations at
universities and research labs. It was distributed as source code, which meant that
players could modify it, create variants, and share their own versions. This open,
collaborative culture would define the genre for decades.

Rogue was followed by a wave of games that built on its ideas, each adding something
new while preserving the core experience of exploring a dangerous, randomized dungeon
where death was permanent.

### Moria (1985)

**Moria**, written by Robert Alan Koeneke and Jim Butler at the University of Oklahoma,
took Rogue's formula and added two ideas that would become genre staples: a persistent
world structure (a single large dungeon rather than randomly generated levels) and
character progression through experience and leveling. In Rogue, the player did not
grow stronger over time. In Moria, killing monsters earned experience points that
could be spent on stat increases, allowing the player to tackle deeper, more dangerous
levels.

Moria also introduced a Tolkien-inspired setting, moving away from Rogue's generic
fantasy. The player descended into the mines of Moria to fight the Balrog, giving the
game a narrative framework that gave purpose to the descent. This was a small change
with large implications: it showed that roguelikes could have settings and stories,
not just mechanics.

### Angband (1990)

**Angband**, created by Ben Harrison, evolved from Moria. It kept the persistent world
idea but returned to Rogue's approach of random level generation, combining the best
of both predecessors. Angband introduced the concept of a "town" level where players
could buy and sell equipment between dungeon dives, creating a gameplay loop that
alternated between risk (venturing into the dungeon) and safety (returning to town to
rest and resupply).

Angband expanded the item system dramatically, with dozens of item types, magical
enchantments, and an identification mechanic. Items could be cursed, blessed, or
enchanted, and the player had to identify them before knowing their true properties.
This created a layer of uncertainty and resource management that went beyond what
previous games had offered.

Most importantly, Angband's source code was freely available. This spawned dozens of
variants---MAngband, ToME, ZAngband, and many more---each building on Angband's
architecture while adding their own features. The Angband variant tradition
demonstrated that roguelikes could be platforms, not just products.

### NetHack (1987)

**NetHack**, started by Mike Stephenson in 1987, took a different approach from Angband.
Where Angband focused on depth of items and monsters, NetHack focused on
**interactions**. In NetHack, nearly everything in the game could interact with
everything else in unexpected ways. You could dip items in fountains, polymorph yourself
into different creatures, wish for specific items using a magical lamp, and combine game
mechanics in ways the developers never explicitly intended.

NetHack rewarded experimentation and knowledge above all else. It was the kind of game
where reading a book of spells could turn you invisible, but reading it while confused
could make you ill. The game was full of these interactions, and discovering them was
part of the fun. NetHack demonstrated that roguelikes could have extraordinary depth
through the combination of simple systems.

NetHack remains one of the most complex and replayable roguelikes ever made. Its
development continued for over 30 years, with the last major release (3.6.6) appearing
in 2020. The game's motto, "Hack, slash, and cast spells in the Dungeons of Doom," 
belies the depth of its systems.

### ADOM (1994)

**ADOM** (Ancient Domains Of Mystery), created by Thomas Biskup, combined roguelike
gameplay with a persistent overworld and a storyline. The game featured a persistent
world map with towns, dungeons, and wilderness areas. The player's actions affected the
world: corrupting dungeons would spread corruption across the map, and completing quests
would unlock new areas and story elements.

ADOM introduced corruption---a mechanic where using powerful magic gradually mutated
the player character, creating meaningful risk-reward tradeoffs. The more powerful the
magic you used, the more corrupt you became, and corruption could eventually destroy
your character. This was one of the first implementations of a mechanic that balanced
player power against long-term consequences.

ADOM demonstrated that roguelikes could tell stories without sacrificing procedural
generation or permadeath. The story was not delivered through cutscenes or dialogue
trees, but through the player's actions and their consequences on the game world.

### DCSS (2006)

**Dungeon Crawl Stone Soup** (DCSS) represents the modern evolution of the traditional
roguelike. It was designed from the ground up to minimize "unsatisfying" gameplay---
grinding, tedious inventory management, and luck-based outcomes. DCSS streamlined many
of the genre's traditional mechanics while preserving its core appeal: tactical,
turn-based combat in a procedurally generated dungeon.

DCSS made several controversial design decisions that reflected a philosophy of
"interesting choices over grind." It removed food (hunger) as a mechanic, reasoning
that it added tedious resource management without interesting decisions. It simplified
character creation by removing class selection in favor of background selection. It
made skill training automatic, removing the need for players to micromanage stat
allocations.

DCSS is widely considered the most "balanced" traditional roguelike and is a good
reference point for the design decisions we will make in this book. It demonstrates
that the genre can evolve and modernize without losing its identity.

## The Berlin Interpretation

In 2008, a group of roguelike developers gathered at the International Roguelike
Development Conference in Berlin. They produced what is now called the **Berlin
Interpretation**---a list of factors that define the traditional roguelike genre. The
interpretation was not intended as a gatekeeping exercise. It was an attempt to
articulate what distinguished roguelikes from other games that borrowed surface-level
elements like procedural generation or permadeath.

The Berlin Interpretation identified nine **high-value factors**:

1. **Random environment generation** -- The game world is generated procedurally, not
   hand-designed. The player must adapt to each new environment rather than memorizing
   layouts. This is the most fundamental roguelike trait. Without procedural generation,
   the game is a different genre.

2. **Permadeath** -- When the player character dies, the game is over. There are no
   save points, no respawns, no undo. Every decision carries permanent weight. Some
   games implement "soft permadeath" with scoring systems or unlockables, but the core
   roguelike experience demands that a death ends that particular run completely.

3. **Turn-based** -- The game proceeds in discrete turns. The player takes an action,
   then the world responds. There is no real-time pressure; every decision can be
   considered at leisure. This is what makes tactical combat possible---the player has
   time to assess the situation and plan their move.

4. **Grid-based movement** -- The game world is a grid. Characters occupy discrete
   tiles and move between them one at a time. Position is meaningful and tactical.
   The grid constrains movement in ways that create interesting spatial puzzles.

5. **Non-modality** -- The player is free to pursue multiple strategies simultaneously.
   There is no locked class system, no single correct path through the game. The player
   can switch between melee, ranged, and magic as the situation demands, rather than
   being locked into a single playstyle.

6. **Complexity** -- The game has many interacting systems. Monsters have varied
   behaviors, items have multiple uses, and the player must manage several concerns
   at once. Complexity creates depth, and depth creates replayability.

7. **Resource management** -- Food, light, ammunition, health, mana. The player must make
   tradeoffs about what to carry, what to use, and when to retreat. Resources create
   scarcity, and scarcity creates meaningful decisions.

8. **Hack-and-slash** -- The game features combat as a primary activity. The player
   fights many monsters, not just a few carefully placed bosses. The dungeon is full
   of threats, and the player must manage their engagement with each one.

9. **Exploration and discovery** -- The dungeon is unknown at the start. The player
   uncovers the map, discovers secrets, and learns the rules of the world through
   play. The fog of war is both a visual effect and a game mechanic.

The interpretation also listed several **low-value factors** that are common but not
essential: single-player focus, monsters treated similarly to the player (meaning
monsters follow the same rules as the player), tactical challenge, special dungeon
features, identified vs. unidentified items, and the player being the only one who can
use items.

The Berlin Interpretation is not a law. It is a description of what the genre looked
like in 2008. Many excellent roguelikes violate one or more of these factors. DCSS
removed food, which some consider a resource management factor. Some roguelikes offer
optional persistent unlocks. The Berlin Interpretation is useful as a design guide, not
as a rigid specification.

## Roguelike vs. Roguelite

Since roughly 2009, the term "roguelike" has been applied to a much broader category of
games. The catalyst was **Spelunky** (2008/2009), which combined procedural level
generation and permadeath with real-time platforming action. Spelunky was not a
traditional roguelike by any reasonable definition---it was a platformer with roguelike
elements. But its success led developers and players to use "roguelike" as shorthand for
"any game with procedural generation and permadeath."

This usage spawned the term **roguelite** to describe games that borrow roguelike
elements without adhering to the genre's traditional structure. Roguelites typically
feature:

- **Real-time (or semi-real-time) combat** instead of turn-based. The player reacts
  to enemies in real time, relying on reflexes rather than tactical planning.
- **Persistent progression between runs**. Unlockable characters, upgrades, meta-currencies,
  and permanent stat increases give the player a sense of progress even when individual
  runs end in death.
- **Simplified item and inventory systems**. Instead of dozens of item types with complex
  interactions, roguelites tend toward simpler, more immediately understandable power-ups.
- **Action-oriented gameplay** rather than tactical decision-making. The moment-to-moment
  experience prioritizes excitement and flow over careful planning.

Examples of roguelites include *Hades*, *Dead Cells*, *The Binding of Isaac*, and
*Slay the Spire*. These are excellent games with massive audiences and critical acclaim.
They are not roguelikes.

The distinction matters for our project because it determines fundamental design
decisions. A roguelite optimizes for moment-to-moment action and between-run
progression. A traditional roguelike optimizes for within-run decision-making and
tactical depth. A roguelite can afford to be simple in its moment-to-moment gameplay
because the meta-progression keeps players engaged. A traditional roguelike must make
every single turn interesting, because there is nothing else---no persistent upgrades, no
unlockable content, no meta-currency. The game itself must be compelling enough to
justify starting over from scratch, over and over again.

**This book builds a traditional roguelike.** Turn-based, grid-based, no meta-progression.
When we use the word "roguelike" throughout this book, we mean this specifically. If you
are looking for a book on building roguelites, this is not it---but the architectural
patterns we cover (ECS, procedural generation, event-driven systems) apply to roguelites
as well.

## Core Design Pillars

Every game rests on a set of design pillars---core principles that guide every decision.
Our roguelike rests on five pillars. These are not arbitrary. They are the properties
that, taken together, create the experience of playing a roguelike.

### Procedural Generation

The dungeon is generated anew each time the player starts a game. This is not a cosmetic
feature. It is foundational. Procedural generation forces the player to rely on
adaptation and general knowledge rather than memorization. It ensures that the same
strategy cannot be applied every run. It makes exploration meaningful, because the player
does not know what lies ahead.

We will implement multiple generation algorithms---rooms and corridors, cellular automata
caves, and weighted region placement---and combine them to create varied, interesting
dungeons. The challenge is not just making levels that look good. It is making levels
that *play* well: levels that present interesting tactical choices, that balance risk
and reward, and that feel like coherent spaces rather than random noise.

Procedural generation also solves a practical problem for the game developer: it
provides infinite content from a finite amount of code. A hand-designed dungeon is
played once and solved. A procedurally generated dungeon is different every time,
which means the game's replayability is essentially unlimited.

### Permadeath

When the player dies, the game is over. No loading a previous save. No respawning at the
last checkpoint. The character is gone, and the player must start a new game with a new
dungeon.

Permadeath is the feature that gives every decision weight. If you can always reload,
then a risky fight is a calculation of expected value against reload time. If you can
never reload, then a risky fight is a genuine gamble with your entire run. Permadeath
transforms every encounter from a puzzle to be optimized into a story to be survived.

This does not mean permadeath should be punishing for its own sake. A well-designed
roguelike gives the player the information and tools to make informed decisions. The
player should die because they made a mistake or took a calculated risk that did not pay
off---not because the game was unfair or opaque. The difference between "this game is
unfair" and "I should have been more careful" is the difference between a bad roguelike
and a good one.

### Turn-Based Gameplay

The game proceeds in discrete turns. The player takes an action (move, attack, use an
item, cast a spell, wait). Then every other entity in the game takes its action. Then
the player acts again.

Turn-based gameplay is the engine of tactical depth. It gives the player time to think.
It makes positioning meaningful. It allows for complex interactions between entities
that would be chaotic or unreadable in real time. It is also much simpler to implement
than real-time systems, which is a practical benefit for a book about building games.

The turn-based structure also makes the game accessible. There is no hand-eye coordination
requirement. No reaction time test. A roguelike can be played by anyone who can think
and make decisions, regardless of their physical abilities or gaming experience.

### Tactical Combat

Combat in a roguelike is not about reflexes or build optimization. It is about
positioning, resource management, and adaptation. The player must consider:

- Where am I relative to the enemy? Can I retreat if the fight goes badly?
- What terrain advantages or disadvantages exist? Is there a doorway I can use to
  fight one enemy at a time?
- What resources (health, mana, items) do I have? Is this fight worth the cost?
- What do I know about this enemy's abilities? Is it resistant to my weapons?
- Is this fight worth having, or should I retreat and find a more favorable engagement?

A single turn can be the difference between victory and death. A well-designed combat
encounter presents the player with several viable approaches, each with different risk
profiles. The player's job is to assess the situation and choose the best option they
can.

Tactical combat also means that the player's skills improve over time. A new player
might rush into every fight. An experienced player knows when to fight, when to flee,
and when to use the environment to their advantage. The game teaches through
consequences, and the player learns through experience.

### Exploration and Discovery

The dungeon is unknown at the start. The player reveals it tile by tile, room by room.
Exploration is rewarded with loot, information, and new tactical options.

This pillar interacts with every other pillar. Procedural generation ensures that each
new level is a fresh discovery. Permadeath ensures that exploration carries risk---you
might find something wonderful, or you might walk into a room full of enemies you cannot
handle. Turn-based gameplay ensures that the moment of discovery is a moment of
decision: do you press forward or retreat?

The field of view system is the technical implementation of this pillar. We will build a
shadowcasting algorithm that limits the player's vision and creates a fog of war over
unexplored areas. This is not just a visual effect. It is a game mechanic that shapes
how the player moves, fights, and makes decisions.

Exploration also creates stories. The player who ventures into an unknown room and finds
a powerful weapon has a story. The player who opens a door and is immediately attacked
by three enemies has a story. These stories are what make roguelikes memorable, and they
are all products of the exploration pillar.

## What Makes a Great Roguelike

The five pillars above describe the *structure* of a roguelike. But structure alone does
not make a game great. A game with procedural generation, permadeath, and turn-based
combat can still be boring. Here is what separates good roguelikes from forgettable ones.

### Emergent Gameplay

The best roguelike moments are not scripted. They emerge from the interaction of simple
systems. A fire spell ignites a pool of oil, which burns a door, which alerts a group of
enemies, who stumble into the fire and die. The player did not trigger a cutscene. They
cast a spell, and the game's systems produced an outcome that was unexpected but
logical.

Emergent gameplay is the reward for building clean, interacting systems. When each
system (combat, items, terrain, AI) behaves independently but predictably, their
combinations produce possibilities that no designer could have anticipated. This is why
roguelikes are infinitely replayable: the system space is too large for any single
playthrough to explore.

As a developer, your job is not to script every possible outcome. It is to build systems
that interact in interesting ways and let the player discover those interactions through
play. This is a fundamentally different approach from scripted game design, and it
requires thinking about your game as a set of rules rather than a set of events.

### Meaningful Choices

Every decision the player makes should matter. "Do I fight this enemy or avoid it?" "Do
I use my healing potion now or save it?" "Do I go left (toward danger, but also toward
potential loot) or right (toward safety, but also toward stagnation)?"

The key to meaningful choices is that the player must not always know the right answer.
If one option is obviously superior, there is no choice. The game must present situations
where the best path is unclear, where the player must weigh incomplete information
against potential consequences.

This is where procedural generation and permadeath earn their keep. Because the dungeon
is different each time, the player cannot look up the optimal strategy. Because death is
permanent, the cost of a bad choice is high. Together, these forces make every decision
feel real.

Meaningful choices also require information. A choice between "attack with sword" and
"attack with axe" is not meaningful if the player has no idea how swords and axes differ.
A choice between "fight the dragon" and "go around the dragon" is meaningful if the
player knows the dragon is dangerous but suspects it guards something valuable. The game
must provide enough information for the player to make informed decisions, while
withholding enough to keep those decisions uncertain.

### Replayability

A roguelike should be worth playing hundreds of times. This is a high bar, and most
games do not meet it. The combination of procedural generation, permadeath, and
meaningful choices creates replayability by ensuring that no two runs are alike. But the
game must also be deep enough to reward repeated engagement. The player should discover
new strategies, new interactions, and new challenges over time, not just see the same
content in a different order.

Replayability also comes from variety in viable strategies. If every successful run
requires the same approach (e.g., always use fire magic), the game is not truly
replayable---it is the same game with different map layouts. A great roguelike supports
multiple viable strategies, and the best strategy depends on what the player finds in
each run. This is what makes each run feel unique: not just the dungeon, but the
player's response to it.

## Design Goals for Our Game

With the genre's history and design principles in mind, here are the specific goals for
the game we will build in this book.

**Goal 1: A complete, playable roguelike.** Not a tech demo. Not a prototype. A game
that a player can start, play through multiple dungeon levels, fight enemies, collect
loot, and reach an ending. It should be fun to play, not just interesting to build.
Completeness means that all the systems work together, that the difficulty curve is
reasonable, and that the player has a clear sense of progression even without meta-game
unlocks.

**Goal 2: Clean, extensible architecture.** The codebase should be organized in a way
that makes it easy to add new features, modify existing ones, and understand what
each part of the code does. We will use ECS and separate game logic from rendering
and input handling. The architecture should be a model, not an obstacle. When you
finish the book, you should be able to add new features without asking "where does this
code go?"

**Goal 3: Multiple generation algorithms.** The dungeon should not use a single
generation method. We will implement at least three distinct algorithms and combine
them to create varied levels. The player should encounter different kinds of spaces
(sewers, caves, vaults) that play differently from one another. Each algorithm should
produce levels that are tactically interesting, not just visually varied.

**Goal 4: Rich combat.** Combat should involve more than walking into enemies and
rolling dice. We will implement field of view, flanking, ranged combat, status effects,
and multiple enemy AI types. The player should have tactical options in every fight.
The combat system should reward clever play and punish careless engagement.

**Goal 5: Moddability.** The game should be easy to extend. We will externalize entity
and item definitions into data files that can be edited without modifying Python code.
The modding API should be simple enough that a player with basic Python knowledge can
add new monsters, items, or dungeon features. This goal also serves as a test of our
architecture: if the game is easy to mod, it is well-designed.

**Goal 6: Polish.** The game should look and feel complete. This means a message log,
a heads-up display, animations for important events, and sensible default settings.
It does not mean professional-quality art or sound---those are beyond the scope of
this book---but it should not look like a terminal program from 1995. The player
should feel like they are playing a game, not running a test harness.

### Design Constraints

Every project has constraints. Ours include:

- **Single player only.** Multiplayer roguelikes exist, but they introduce networking,
  synchronization, and design complexity that would double the size of this book.

- **ASCII and tile modes.** We will support both ASCII rendering (the classic look) and
  tile-based rendering (using a provided sprite sheet). The game logic should be
  identical in both modes; only the presentation layer changes.

- **No real-time elements.** Every action is turn-based. There are no timers, no
  real-time combat, no animated movement between tiles. The player acts, the world
  responds, and the player acts again.

- **Python and tcod only.** We will not use other game engines, frameworks, or
  libraries beyond tcod and the Python standard library. If we need something that tcod
  does not provide, we will build it.

- **No external assets beyond the provided sprite sheet.** The game should be
  buildable from the repository alone. Players should not need to download additional
  assets or configure external tools.

These constraints are intentional. They keep the project focused and ensure that
every reader has the same starting point. You are free to break these constraints in
your own projects, of course---but within this book, they give us a shared foundation.

## Exercises

These exercises are designed to help you think about roguelike design before you start
building. There are no right answers. The goal is to engage with the ideas in this
chapter and start forming your own opinions about what makes a roguelike work.

### Exercise 1: Your Roguelike History

List five roguelikes or roguelites you have played. For each one, identify:

- Does it use procedural generation? What kind?
- Is it turn-based or real-time?
- Does it have permadeath?
- What is the core gameplay loop (the sequence of actions the player repeats most
  often)?

Compare your list. How many of these games are "true" roguelikes by the Berlin
Interpretation? How many are roguelites? What do the differences tell you about your
own preferences as a player?

### Exercise 2: Emergent Moments

Think about a memorable moment from a roguelike or roguelite you have played. Describe
it in detail. What systems interacted to create that moment? Was it scripted, or did it
emerge from the game's mechanics?

If you have never played a roguelike, watch a "roguelike highlights" compilation on
YouTube and describe a moment that caught your attention. Try to identify which of the
game's systems produced that moment.

### Exercise 3: Design Priorities

Imagine you are designing a roguelike. You have a limited amount of development time.
Rank the following features by priority (1 = most important, 8 = least important):

- Procedural level generation
- Permadeath with a score system
- Multiple character classes or roles
- Field of view and fog of war
- Saving and loading
- Status effects (poison, burning, etc.)
- Shops and NPCs
- A tutorial or onboarding system

There is no single correct ranking. Your priorities reflect your values as a designer.
Write down your ranking and a one-sentence justification for each position. This is the
kind of thinking that separates building a game from merely writing code.
