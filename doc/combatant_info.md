## COMBATANT_INFO

This logging feature was added on patch 7.0.3

&nbsp;

New Logging Feature: COMBATANT_INFO | 2016-01-13 00:00 | ![Blizzard Entertainment](https://static.wikia.nocookie.net/wowpedia/images/2/20/Blizz.gif/revision/latest?cb=20171007185539) **[Celestalon](/wiki/Celestalon)**

Whenever an ENCOUNTER_START event occurs, a new “COMBATANT_INFO” log line will also be printed for each player in the instance. The current data structure for COMBATANT_INFO is as follows, but is subject to change based on feedback and technical needs:

```lua
COMBATANT_INFO, playerGUID, Strength, Agility, Stamina, Intelligence, Dodge, Parry, Block, CritMelee, CritRanged, CritSpell, Speed, Lifesteal, HasteMelee, HasteRanged, HasteSpell, Avoidance, Mastery, VersatilityDamageDone, VersatilityHealingDone, VersatilityDamageTaken, Armor, CurrentSpecID, [(Class Talent 1, ...)], (PvP Talent 1, ...), [Artifact Trait ID 1, Trait Effective Level 1, ...], [(Equipped Item ID 1, Equipped Item iLvL 1, (Permanent Enchant ID, Temp Enchant ID, On Use Spell Enchant ID), (Bonus List ID 1, ...), (Gem ID 1, Gem iLvL 1, ...))], ...,[Interesting Aura Caster GUID 1, Interesting Aura Spell ID 1, ...]
```

Some clarifications about a few of those elements:

- **Stats** – Those are the current stat values at the time of the log line. Secondary stats are in terms of the Rating amount, not a %.
- **Armor** – This is the Armor amount before multipliers (such as Bear Form).
- **Talents** – A list of the selected talents. Today’s build will print this ID as a TalentID, a record type that is not dataminable. This will be fixed in a future build to be the SpellID of the talent.
- **Artifact Traits** – This will be a list of the selected traits for the character’s current specialization’s artifact (even if it’s not equipped). The Artifact Trait ID is an ID to a new record type to 7.0, which should be dataminable already. Trait Effective Level is the number of points placed in that talent. Note that some Relics will allow this to go beyond the max.
- **Equipment** – This is a list of all equipped gear on the character. The first ID is the standard Item ID of the item, followed by its ilvl. After that is a list of enchants on the item, one of each of the 3 possible enchantment types (using the ItemEnchantment ID).
- **Interesting Auras** – This is a list of interesting auras (buffs/debuffs) that we have manually flagged to be included in this log line. We’ll welcome feedback about what should be included here but currently plan for set bonuses, well fed, flasks, combat potions, Vantus runes, and player buffs. Nothing has been flagged for this yet, so you won’t see anything here in the current build.

On a character without any Shadowlands-specific powers.

```
4/22 05:27:15.478  COMBATANT_INFO,Player-3299-004E8630,1,132,184,906,653,0,0,0,257,257,257,11,0,188,188,188,0,118,90,90,90,120,257,(193155,64129,238136,200199,321377,193157,265202),(0,235587,215982,328530),[0,0,[],[],[]],[(173845,90,(),(1479,4786,6502),()),(158075,140,(),(4932,4933,6316),()),(157971,105,(),(1514,4786,6506),()),(3427,1,(),(),()),(157994,105,(),(1514,4786,6504),()),(173341,90,(0,0,4223),(6707),()),(174237,100,(),(4822,6516,6513,1487,4786),()),(173322,90,(),(6707),()),(158037,99,(),(4803,4802,42,6516,6515,1513,4786),()),(183675,110,(),(1482,4786),()),(173344,98,(),(6706),()),(174469,100,(),(4822,6516,6513,1487,4786),()),(173349,98,(),(6706),()),(175719,104,(),(6707,6901),()),(169223,133,(),(6276,1472),()),(165628,115,(),(5844,1527,4786),()),(0,0,(),(),()),(0,0,(),(),())],[Player-3299-004E8630,295365,Player-3299-004E8630,298268,Player-3299-004E8630,296320],1,0,0,0
```

&nbsp;

| Param                   | Example | Description                       |
| ----------------------- | ------- | --------------------------------- |
| VersatilityHealingDone  | 90      |                                   |
| VersatilityDamageTaken  | 90      |                                   |
| VersatilityDamageDone   | 90      |                                   |
| Trait Effective Level 1 | 0       |                                   |
| Tier                    | 0       |                                   |
| Strength                | 132     |                                   |
| Stamina                 | 906     |                                   |
| Speed                   | 11      |                                   |
| Season                  | 0       | Possibly only applicable in Arena |
| Rating                  | 0       |                                   |

&nbsp;

### PvP Talents:

| Param        | Example | Description            |
| ------------ | ------- | ---------------------- |
| PvP Talent 4 | 328530) | Divine Ascension       |
| PvP Talent 3 | 215982  | Spirit of the Redeemer |
| PvP Talent 2 | 235587  | Miracle Worker         |
| PvP Talent 1 | (0      |                        |

&nbsp;

### PvP Stats:

| Param                   | Example              | Description |
| ----------------------- | -------------------- | ----------- |
| PlayerGUID              | Player-3299-004E8630 |             |
| Permanent Enchant ID    |                      |             |
| Temp Enchant ID         |                      |             |
| On Use Spell Enchant ID | ()                   |             |
| Parry                   | 0                    |             |
| Mastery                 | 118                  |             |
| Lifesteal               | 0                    |             |

&nbsp;

### Interesting Auras:

| Param        | Example        | Description           |
| ------------ | -------------- | --------------------- |
| Intelligence | 653            |                       |
| Honor Level  | 1              | UnitHonorLevel()      |
| HasteSpell   | 188            |                       |
| HasteRanged  | 188            |                       |
| HasteMelee   | 188            |                       |
| Gem ID 1     | ())            |                       |
| Faction      | 1              | 0: Horde, 1: Alliance |
| Event        | COMBATANT_INFO | Version 18            |

&nbsp;

### Equipped Items:

| Param                | Example                                              | Description                     |
| -------------------- | ---------------------------------------------------- | ------------------------------- |
| Equipped Item iLvL 1 | 90                                                   |                                 |
| Equipped Item ID 1   | [(173845                                             | Vile Manipulator's Hood         |
| Equipped Item 18     | (0,0,(),(),())]                                      |                                 |
| Equipped Item 17     | (0,0,(),(),())                                       |                                 |
| Equipped Item 16     | (165628,115,(),(5844,1527,4786),())                  | Sentinel's Branch               |
| Equipped Item 15     | (169223,133,(),(6276,1472),())                       | Ashjra'kamas, Shroud of Resolve |
| Equipped Item 14     | (175719,104,(),(6707,6901),())                       | Agthia's Void-Tinged Speartip   |
| Equipped Item 13     | (173349,98,(),(6706),())                             | Misfiring Centurion Controller  |
| Equipped Item 12     | (174469,100,(),(4822,6516,6513,1487,4786),())        | Band of Insidious Ruminations   |
| Equipped Item 11     | (173344,98,(),(6706),())                             | Band of Chronicled Deeds        |
| Equipped Item 10     | (183675,110,(),(1482,4786),())                       | Cold Sweat Mitts                |
| Equipped Item 9      | (158037,99,(),(4803,4802,42,6516,6515,1513,4786),()) | Squallshaper Cuffs              |
| Equipped Item 8      | (173322,90,(),(6707),())                             | Sandals of Soul's Clarity       |
| Equipped Item 7      | (174237,100,(),(4822,6516,6513,1487,4786)            | Breeches of Faithful Execution  |
| Equipped Item 6      | (173341,90,(0,0,4223),(6707),())                     | Cord of Uncertain Devotion      |
| Equipped Item 5      | (157994,105,(),(1514,4786,6504),())                  | Sirensong Garments              |
| Equipped Item 4      | (3427,1,(),(),())                                    | Stylish Black Shirt             |
| Equipped Item 3      | (157971,105,(),(1514,4786,6506),())                  | Sirensong Amice                 |
| Equipped Item 2      | (158075,140,(),(4932,4933,6316),())                  | Heart of Azeroth                |
| Dodge                | 0                                                    |                                 |
| CurrentSpecID        | 257                                                  | Holy                            |
| CritSpell            | 257                                                  |                                 |
| CritRanged           | 257                                                  |                                 |

&nbsp;

### Class Talents:

| Param          | Example | Description          |
| -------------- | ------- | -------------------- |
| Class Talent 7 | 265202) | Holy Word: Salvation |
| Class Talent 6 | 193157  | Benediction          |
| Class Talent 5 | 321377  | Prayer Circle        |
| Class Talent 4 | 200199  | Censure              |
| Class Talent 3 | 238136  | Cosmic Ripple        |
| Class Talent 2 | 64129   | Body and Soul        |
| Class Talent 1 | (193155 | Enlightenment        |

&nbsp;

### Character Stats:

| Param              | Example                      | Description           |
| ------------------ | ---------------------------- | --------------------- |
| Bonus List ID 3    | 6502)                        |                       |
| Bonus List ID 2    | 4786                         |                       |
| Bonus List ID 1    | (1479                        |                       |
| Block              | 0                            |                       |
| Avoidance          | 0                            |                       |
| Aura Spell ID 1    | 295365                       | Ancient Flame         |
| Aura Caster GUID 1 | [Player-3299-004E8630        |                       |
| Aura 3             | Player-3299-004E8630,296320] | Strive for Perfection |
| Aura 2             | Player-3299-004E8630,298268  | Lucid Dreams          |

&nbsp;

### Artifact Traits:

| Param               | Example | Description |
| ------------------- | ------- | ----------- |
| Artifact Trait ID 4 | []]     |             |
| Artifact Trait ID 3 | []      |             |
| Artifact Trait ID 2 | []      |             |
| Artifact Trait ID 1 | [0      |             |
| Armor               | 120     |             |
| Agility             | 184     |             |

&nbsp;

```
[18,1,[(343203,335,1),(348511,1432,1),(333759,995,1),(295965,56,1),(315288,357,1),(313833,264,1),(333505,1002,1),(295068,49,1)],[(1379),(1380),(1381),(1408),(1410),(1414),(1416),(1418)],[(233,200),(231,213),(244,213),(230,213)]]
```

| Param            | Example         | Description                                                                    |
| ---------------- | --------------- | ------------------------------------------------------------------------------ |
| Soulbind ID      | [18             | [Forgelite Prime Mikanikos](https://www.wowhead.com/spell=343203/ringing-doom) |
| Covenant ID      | 1               | [Kyrian](https://www.wowhead.com/spell=343203/ringing-doom)                    |
| Anima Powers     |                 |                                                                                |
| Anima Spell ID 1 | [(343203        | [Ringing Doom](https://www.wowhead.com/spell=343203/ringing-doom)              |
| Maw Power ID 1   | 335             | GetMawPowerLinkBySpellID()                                                     |
| Count 1          | 1)              |                                                                                |
| Anima Power 2    | (348511,1432,1) | Bloodgorged Leech                                                              |
| Anima Power 3    | (333759,995,1)  | Leather Apron                                                                  |
| Anima Power 4    | (295965,56,1)   | Curious Miasma                                                                 |
| Anima Power 5    | (315288,357,1)  | Frostbite Wand                                                                 |
| Anima Power 6    | (313833,264,1)  | Shadowblade's Gift                                                             |
| Anima Power 7    | (333505,1002,1) | Rupturing Spike                                                                |
| Anima Power 8    | (295068,49,1)]  | Abundance of Phantasma                                                         |
| Soulbind Traits  |                 |                                                                                |
| Soulbind Trait 1 | [(1379)         | Finesse Conduit                                                                |
| Soulbind Trait 2 | (1380)          | Endurance Conduit                                                              |
| Soulbind Trait 3 | (1381)          | Potency Conduit                                                                |
| Soulbind Trait 4 | (1408)          | Forgelite Filter                                                               |
| Soulbind Trait 5 | (1410)          | Hammer of Genesis                                                              |
| Soulbind Trait 6 | (1414)          | Endurance Conduit                                                              |
| Soulbind Trait 7 | (1416)          | Regenerating Materials                                                         |
| Soulbind Trait 8 | (1418)]         | Forgelite Prime's Expertise                                                    |
| Conduit Spells   |                 |                                                                                |
| Conduit ID 1     | [(233           | [Quick Decisions](https://www.wowhead.com/spell=341531/quick-decisions)        |
| Conduit Level 1  | 200)            |                                                                                |
| Conduit 2        | (231,213)       | [Recuperator](https://www.wowhead.com/spell=341312/recuperator)                |
| Conduit 3        | (244,213)       | [Count the Odds](https://www.wowhead.com/spell=341546/count-the-odds)          |
| Conduit 4        | (230,213)]]     | [Nimble Fingers](https://www.wowhead.com/spell=341311/nimble-fingers)          |
