# UnitFlag

&nbsp;
Unit flags contain information for a unit in the combat log. They are returned from COMBAT_LOG_EVENT sourceFlags and destFlags params.

A unit can only be one type from each of the following four categories:

- Type: The way the unit is currently being controlled.
- Controller: Who currently controls this unit - an NPC or a player.
- Reaction: The unit's reaction, relative to you - hostile, friendly or neutral.
- Affiliation: If the unit belongs to you (your character, pet, mind controlled) or is in your party or raid, or neither.
  &nbsp;

## Constants

&nbsp;

| Constant                              | Bit field  | Description                                                               |
| ------------------------------------- | ---------- | ------------------------------------------------------------------------- |
| **Affiliation**                       |            |                                                                           |
| COMBATLOG_OBJECT_AFFILIATION_MINE     | 0x00000001 |                                                                           |
| COMBATLOG_OBJECT_AFFILIATION_PARTY    | 0x00000002 |                                                                           |
| COMBATLOG_OBJECT_AFFILIATION_RAID     | 0x00000004 |                                                                           |
| COMBATLOG_OBJECT_AFFILIATION_OUTSIDER | 0x00000008 |                                                                           |
| COMBATLOG_OBJECT_AFFILIATION_MASK     | 0x0000000F |                                                                           |
| **Reaction**                          |            |                                                                           |
| COMBATLOG_OBJECT_REACTION_FRIENDLY    | 0x00000001 |                                                                           |
| COMBATLOG_OBJECT_REACTION_NEUTRAL     | 0x00000002 |                                                                           |
| COMBATLOG_OBJECT_REACTION_HOSTILE     | 0x00000004 |                                                                           |
| COMBATLOG_OBJECT_REACTION_MASK        | 0x0000000F |                                                                           |
| **Controller**                        |            |                                                                           |
| COMBATLOG_OBJECT_CONTROL_PLAYER       | 0x00000001 |                                                                           |
| COMBATLOG_OBJECT_CONTROL_NPC          | 0x00000002 |                                                                           |
| COMBATLOG_OBJECT_CONTROL_MASK         | 0x00000003 |                                                                           |
| **Type**                              |            |                                                                           |
| COMBATLOG_OBJECT_TYPE_PLAYER          | 0x00000004 | Units directly controlled by players.                                     |
| COMBATLOG_OBJECT_TYPE_NPC             | 0x00000008 | Units controlled by the server.                                           |
| COMBATLOG_OBJECT_TYPE_PET             | 0x00000010 | Pets are units controlled by a player or NPC, including via mind control. |
| COMBATLOG_OBJECT_TYPE_GUARDIAN        | 0x00000020 | Units that are not controlled but automatically defend their master.      |
| COMBATLOG_OBJECT_TYPE_OBJECT          | 0x00000040 | Objects are everything else, such as traps and totems.                    |
| COMBATLOG_OBJECT_TYPE_MASK            | 0x000000FC |                                                                           |
| **Special cases (non-exclusive)**     |            |                                                                           |
| COMBATLOG_OBJECT_TARGET               | 0x00000100 |                                                                           |
| COMBATLOG_OBJECT_FOCUS                | 0x00000200 |                                                                           |
| COMBATLOG_OBJECT_MAINTANK             | 0x00000400 |                                                                           |
| COMBATLOG_OBJECT_MAINASSIST           | 0x00000800 |                                                                           |
| COMBATLOG_OBJECT_NONE                 | 0x00001000 | Whether the unit does not exist.                                          |
| COMBATLOG_OBJECT_SPECIAL_MASK         | 0x0000F000 |                                                                           |

# Example

- A player who is dueling you is 0x0548 (A hostile outsider player controlled by a player)
- A player who was mind controlled by another player that attacks you is 0x1148 (A hostile outsider pet controlled by a player)
  > Since 0x1148 can also be an enemy player's pet you need to check the unit GUID to know if it's an enemy pet or a player character.
- A player who was charmed by an NPC is 0x1248 (A hostile outsider pet controlled by an NPC)
- Checks if the unit is friendly.

```lua
if bit.band(unitFlag, COMBATLOG_OBJECT_REACTION_FRIENDLY) > 0 then
	print("unit is friendly")
end
```

- Prints unit flag information for the dest unit on combat log events.

```lua
local flags = {
	[COMBATLOG_OBJECT_AFFILIATION_MASK] = {
		[COMBATLOG_OBJECT_AFFILIATION_MINE] = "Affiliation: Mine",
		[COMBATLOG_OBJECT_AFFILIATION_PARTY] = "Affiliation: Party",
		[COMBATLOG_OBJECT_AFFILIATION_RAID] = "Affiliation: Raid",
		[COMBATLOG_OBJECT_AFFILIATION_OUTSIDER] = "Affiliation: Outsider",
	},
	[COMBATLOG_OBJECT_REACTION_MASK] = {
		[COMBATLOG_OBJECT_REACTION_FRIENDLY] = "Reaction: Friendly",
		[COMBATLOG_OBJECT_REACTION_NEUTRAL] = "Reaction: Neutral",
		[COMBATLOG_OBJECT_REACTION_HOSTILE] = "Reaction: Hostile",
	},
	[COMBATLOG_OBJECT_CONTROL_MASK] = {
		[COMBATLOG_OBJECT_CONTROL_PLAYER] = "Control: Player",
		[COMBATLOG_OBJECT_CONTROL_NPC] = "Control: NPC",
	},
	[COMBATLOG_OBJECT_TYPE_MASK] = {
		[COMBATLOG_OBJECT_TYPE_PLAYER] = "Type: Player",
		[COMBATLOG_OBJECT_TYPE_NPC] = "Type: NPC",
		[COMBATLOG_OBJECT_TYPE_PET] = "Type: Pet",
		[COMBATLOG_OBJECT_TYPE_GUARDIAN] = "Type: Guardian",
		[COMBATLOG_OBJECT_TYPE_OBJECT] = "Type: Object",
	},
}
local order = {"TYPE", "CONTROL", "REACTION", "AFFILIATION"}

local f = CreateFrame("Frame")
f:RegisterEvent("COMBAT_LOG_EVENT_UNFILTERED")
f:SetScript("OnEvent", function(self, event)
	self:COMBAT_LOG_EVENT_UNFILTERED(CombatLogGetCurrentEventInfo())
end)

function f:COMBAT_LOG_EVENT_UNFILTERED(...)
	local timestamp, subevent, _, sourceGUID, sourceName, sourceFlags, sourceRaidFlags, destGUID, destName, destFlags, destRaidFlags = ...
	if destName then
		local t = {}
		table.insert(t, subevent)
		table.insert(t, destName)
		table.insert(t, format("0x%X", destFlags))
		for _, v in pairs(order) do
			local mask = _G["COMBATLOG_OBJECT_"..v.."_MASK"]
			local bitfield = bit.band(destFlags, mask)
			local info = flags[mask][bitfield]
			table.insert(t, (info:gsub(": (%a+)", ": |cff71d5ff%1|r"))) -- add some coloring
		end
		print(table.concat(t, ", "))
	end
end
```
