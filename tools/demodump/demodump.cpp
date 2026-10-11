// demodump: turn a Quake Live demo (.dm_91 / .dm_90 / .dm_73) into a flat binary stream of snapshots,
// for imitation learning. Built on UberDemoTools' custom parsing API (GPL-3.0, github.com/mightycow/uberdemotools).
//
//   demodump <demo> <out.bin> <out.json> [<out.events.json>]
//
// out.json: protocol, config strings 0/1 (server info, system info: map name etc.) and the player config strings.
// out.bin: little-endian float32 records, one per snapshot:
//   [1, serverTimeMs, nPlayers, nMissiles, nItems, nEvents]                        (6 values)
//   player state of the recorded/followed player                                   (PS_N values, see below)
//   per other player entity:  number clientNum pos3 vel3 angles3 weapon eFlags groundEntityNum event eventParm legsAnim torsoAnim powerups
//   per missile:              number weapon trType trTime base3 delta3 otherEntityNum clientNum
//   per item:                 number modelindex pos3 eFlags
//   per event entity:         number eventType eventParm pos3 otherEntityNum otherEntityNum2 clientNum
// Entity types and event numbers are written as UDT's protocol-independent ids where noted in the json.
//
// What out.bin does not hold (B-218, 2026-10-11), and why out.events.json exists:
//   - An event entity's kind. The parser library moves it out of the type field into the event field on the snapshot
//     an event is first seen in, so "eventType" above is 0 there, and on later snapshots it is the kind or 0 depending
//     on which older snapshot the server sent the change from. The rows are left as they are (readers depend on the
//     layout); the kind is in out.events.json.
//   - Events that ride on another entity (a rocket's explosion is the missile's own entity turned into a general one).
//   - Config strings after the start (the level's start time, the scores, the intermission), and all but 0, 1 and the
//     players' even at the start.
//   - The server time exactly: a float32 holds whole numbers only to 16,777,216 ms (4.66 hours of server uptime); above
//     it the times of out.bin are rounded to even numbers, further up to multiples of four (a step of 25 ms reads as
//     24 or 26, never as 25).
// out.bin and out.json are byte for byte the same with and without the fourth argument.
//
// out.events.json (only when the fourth argument is given; plain ASCII, bytes over 127 of a string as \u00XX):
//   "version": 1, "protocol", "snapshots" (as out.json)
//   "entity_types", "event_ids", "config_string_ids", "means_of_death", "item_ids": this protocol's numbers by the
//       library's names (only the names the library knows; an event number without a name is the game's own, e.g.
//       footsteps)
//   "entity_flag_masks": this protocol's eFlags bits by name (Dead, PlayerEvent, Firing, ...)
//   "times": the server time in ms of every snapshot record of out.bin, exact
//   "event_cols": the names of an event row's columns; "events": one row per event, on the snapshot it is first seen in:
//       snap        index of the snapshot record in out.bin        serverTime   its server time, ms
//       source      0: an event entity (a temporary entity made for the event): one row per event, not one per
//                      snapshot it stays in. New is what the library flags as a new event, and an event that is not the
//                      one last seen under its entity number (the flag misses an event whose number another event had
//                      in the last 300 ms: the server does that in the first seconds after a map's restart).
//                   1: an event in the event field of another entity (a player, a missile, an item, a general
//                      entity), by the game client's own rule: the field changed (its two sequence bits count) and is
//                      not zero; an entity out of the snapshots for more than 300 ms starts afresh
//                   2: the followed player's own event, from his player state (he is no entity in his own snapshots),
//                      by the game client's rule: a new place in his list of two events, or a new external event;
//                      nothing on the first snapshot and on the first after a cut to another player. With more than
//                      two of his events between two snapshots the older ones are lost, as they are to a spectator.
//       event       the event's number in this protocol, without the sequence bits (see "event_ids")
//       eType       the entity's type (see "entity_types"); with source 0 always Event
//       eventParm and every other field of the entity's state, by the names of the game's entityState_t (pos_ and
//       apos_: its two trajectories, place and angles; a vector's parts end in _0, _1, _2). With source 2 the
//       columns are filled from the player state as the game fills a player's entity (number and clientNum the
//       followed client, eType a player's, pos_trBase his origin, pos_trDelta his velocity, apos_trBase his view,
//       angles2_1 his movement direction, eFlags, weapon, groundEntityNum, legsAnim, torsoAnim, loopSound, generic1),
//       the rest zero. For
//       an obituary (source 0): otherEntityNum the victim, otherEntityNum2 the killer (a number of 64 or more: the
//                       world), eventParm the means of death (see "means_of_death"; the later versions of the game
//                       have means the library has no name for: 33 is one, which the demo site counts as a rail
//                       kill). A player who leaves the game dies by his own hand with the means TeamSwitch.
//       an impact:      pos_trBase_0..2 the place. MissileHit / MissileMiss / MissileMissMetal with source 1 on a
//                       general entity are a rocket's, grenade's or plasma ball's end (weapon says which); with
//                       source 0 a lightning or rail hit; BulletHitFlesh / BulletHitWall the machine gun's;
//                       RailTrail: pos_trBase its end, origin2 its start, clientNum the shooter
//       a player's event sent as an entity of its own (source 0, eFlags has the PlayerEvent bit): otherEntityNum is
//                       the player, the other fields his state at that moment
//       a pickup:       ItemPickup with source 1 on a player's entity or source 2: eventParm is the item's number
//                       (see "item_ids"; the modelindex of the item's row in out.bin)
//   "gamestates": as out.json's, with every config string that is not empty ("cs": {"<index>": "<string>"})
//   "commands": every server command in the order received: [at_snapshot, time, sequence, name, index, string]
//       at_snapshot  the index of the snapshot record that came in the same message (the game runs the command just
//                    before that snapshot), or of the next one if that message's snapshot is not in out.bin
//       time         that snapshot's server time, or null if the message held none
//       name "cs":   a config string was set: index and its new string (the level's start time, the scores,
//                    the intermission, ... see "config_string_ids")
//       other names: index null; string is the whole command if it holds nothing but numbers (the score tables,
//                    map_restart), else null (chat and prints are not written)
#include "uberdemotools.h"

#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>
#include <vector>

#define PS_N (1 + 1 + 3 + 3 + 3 + 3 + 3 + 9 + 16 + 16 + 16 + 16 + 2 + 2 + 3 + 4 + 2)

#define EVENTS_VERSION 1
#define MAX_ENTITY_NUMBERS 1024			// MAX_GENTITIES
#define EVENT_SEQUENCE_BITS 0x300		// EV_EVENT_BIT1 | EV_EVENT_BIT2
#define EVENT_WINDOW_MS 300				// EVENT_VALID_MSEC
#define CONFIG_STRING_COUNT 2048		// the library's MAX_CONFIGSTRINGS

static void Callback(s32, const char*) {}

static void JsonString(FILE* f, const char* s)
{
	fputc('"', f);
	for(; s && *s; ++s)
	{
		const unsigned char c = (unsigned char)*s;
		if(c == '"' || c == '\\') { fputc('\\', f); fputc(c, f); }
		else if(c < 32) fprintf(f, "\\u%04x", c);
		else fputc(c, f);
	}
	fputc('"', f);
}

static void W(std::vector<float>& o, double v) { o.push_back((float)v); }
static void W3(std::vector<float>& o, const float* v) { o.push_back(v[0]); o.push_back(v[1]); o.push_back(v[2]); }

// ---- out.events.json -------------------------------------------------------------------------------------------------

struct NamedId { const char* Name; s32 Id; };
#define NAMED_ITEM(Enum) { #Enum, (s32)udtEntityType::Enum },
static const NamedId EntityTypeNames[] = { UDT_ENTITY_TYPE_LIST(NAMED_ITEM) };
#undef NAMED_ITEM
#define NAMED_ITEM(Enum) { #Enum, (s32)udtEntityEvent::Enum },
static const NamedId EntityEventNames[] = { UDT_ENTITY_EVENT_LIST(NAMED_ITEM) };
#undef NAMED_ITEM
#define NAMED_ITEM(Enum) { #Enum, (s32)udtConfigStringIndex::Enum },
static const NamedId ConfigStringNames[] = { UDT_CONFIG_STRING_LIST(NAMED_ITEM) };
#undef NAMED_ITEM
#define NAMED_ITEM(Enum) { #Enum, (s32)udtEntityFlag::Enum },
static const NamedId EntityFlagNames[] = { UDT_ENTITY_STATE_FLAG_LIST(NAMED_ITEM) };
#undef NAMED_ITEM
#define NAMED_ITEM(Enum, Desc, KillType, Bit) { #Enum, (s32)udtMeanOfDeath::Enum },
static const NamedId MeanOfDeathNames[] = { UDT_MEAN_OF_DEATH_LIST(NAMED_ITEM) };
#undef NAMED_ITEM
// (the library has no list of its item names: these are the members of udtItem)
#define ITEM_NAME_LIST(N) \
	N(AmmoBFG) N(AmmoBelt) N(AmmoBullets) N(AmmoCells) N(AmmoGrenades) N(AmmoHMG) N(AmmoLightning) N(AmmoMines) N(AmmoNails) \
	N(AmmoPack) N(AmmoRockets) N(AmmoShells) N(AmmoSlugs) N(HoldableInvulnerability) N(HoldableKamikaze) N(HoldableMedkit) \
	N(HoldablePortal) N(HoldableTeleporter) N(ItemAmmoRegen) N(ItemArmorBody) N(ItemArmorCombat) N(ItemArmorJacket) \
	N(ItemArmorShard) N(ItemBackpack) N(ItemBlueCube) N(ItemDoubler) N(ItemEnviro) N(ItemFlight) N(ItemGuard) N(ItemHaste) \
	N(ItemHealth) N(ItemHealthLarge) N(ItemHealthMega) N(ItemHealthSmall) N(ItemInvis) N(ItemKeyGold) N(ItemKeyMaster) \
	N(ItemKeySilver) N(ItemQuad) N(ItemRedCube) N(ItemRegen) N(ItemScout) N(ItemSpawnArmor) N(FlagBlue) N(FlagNeutral) N(FlagRed) \
	N(WeaponBFG) N(WeaponChaingun) N(WeaponGauntlet) N(WeaponGrapplingHook) N(WeaponGrenadeLauncher) N(WeaponHMG) \
	N(WeaponLightningGun) N(WeaponMachinegun) N(WeaponNailgun) N(WeaponPlasmaGun) N(WeaponProxLauncher) N(WeaponRailgun) \
	N(WeaponRocketLauncher) N(WeaponShotgun)
#define NAMED_ITEM(Enum) { #Enum, (s32)udtItem::Enum },
static const NamedId ItemNames[] = { ITEM_NAME_LIST(NAMED_ITEM) };
#undef NAMED_ITEM

// (pos and apos are the entity's two trajectories: place and angles; a vector's parts end in _0, _1, _2)
static const char* const EventCols =
	"\"snap\", \"serverTime\", \"source\", \"number\", \"eType\", \"eFlags\", \"event\", \"eventParm\", "
	"\"pos_trType\", \"pos_trTime\", \"pos_trDuration\", \"pos_trBase_0\", \"pos_trBase_1\", \"pos_trBase_2\", "
	"\"pos_trDelta_0\", \"pos_trDelta_1\", \"pos_trDelta_2\", "
	"\"apos_trType\", \"apos_trTime\", \"apos_trDuration\", \"apos_trBase_0\", \"apos_trBase_1\", \"apos_trBase_2\", "
	"\"apos_trDelta_0\", \"apos_trDelta_1\", \"apos_trDelta_2\", "
	"\"time\", \"time2\", \"origin_0\", \"origin_1\", \"origin_2\", \"origin2_0\", \"origin2_1\", \"origin2_2\", "
	"\"angles_0\", \"angles_1\", \"angles_2\", \"angles2_0\", \"angles2_1\", \"angles2_2\", "
	"\"otherEntityNum\", \"otherEntityNum2\", \"groundEntityNum\", \"constantLight\", \"loopSound\", \"modelindex\", \"modelindex2\", "
	"\"clientNum\", \"frame\", \"solid\", \"powerups\", \"weapon\", \"legsAnim\", \"torsoAnim\", \"generic1\"";

static void AInt(std::string& o, long long v)
{
	char b[32];
	sprintf(b, "%lld", v);
	o += b;
}

static void ANum(std::string& o, double v)
{
	if(!(v == v) || v > 3.0e38 || v < -3.0e38) { o += "null"; return; }		// not a number, or not finite
	char b[40];
	sprintf(b, "%.9g", v);
	o += b;
}

static void AStr(std::string& o, const char* s)
{
	o += '"';
	for(; s && *s; ++s)
	{
		const unsigned char c = (unsigned char)*s;
		if(c == '"' || c == '\\') { o += '\\'; o += (char)c; }
		else if(c < 32 || c > 126) { char b[8]; sprintf(b, "\\u%04x", c); o += b; }
		else o += (char)c;
	}
	o += '"';
}

static void AVec(std::string& o, const float* v)
{
	ANum(o, v[0]); o += ", "; ANum(o, v[1]); o += ", "; ANum(o, v[2]);
}

static void ATrajectory(std::string& o, const idTrajectoryBase& t)
{
	AInt(o, (int)t.trType); o += ", "; AInt(o, t.trTime); o += ", "; AInt(o, t.trDuration); o += ", ";
	AVec(o, t.trBase); o += ", "; AVec(o, t.trDelta);
}

// (the type and the event are given apart from the entity: of an event entity the library leaves the kind now in the one
// field, now in the other)
static void AEvent(std::string& o, int& count, int snap, s32 timeMs, int source, int entityType, int eventNumber, const idEntityStateBase* e)
{
	o += count++ ? ",\n[" : "\n[";
	AInt(o, snap); o += ", "; AInt(o, timeMs); o += ", "; AInt(o, source); o += ", "; AInt(o, e->number); o += ", ";
	AInt(o, entityType); o += ", "; AInt(o, e->eFlags); o += ", "; AInt(o, eventNumber); o += ", "; AInt(o, e->eventParm); o += ", ";
	ATrajectory(o, e->pos); o += ", "; ATrajectory(o, e->apos); o += ", ";
	AInt(o, e->time); o += ", "; AInt(o, e->time2); o += ", ";
	AVec(o, e->origin); o += ", "; AVec(o, e->origin2); o += ", "; AVec(o, e->angles); o += ", "; AVec(o, e->angles2); o += ", ";
	AInt(o, e->otherEntityNum); o += ", "; AInt(o, e->otherEntityNum2); o += ", "; AInt(o, e->groundEntityNum); o += ", ";
	AInt(o, e->constantLight); o += ", "; AInt(o, e->loopSound); o += ", "; AInt(o, e->modelindex); o += ", "; AInt(o, e->modelindex2); o += ", ";
	AInt(o, e->clientNum); o += ", "; AInt(o, e->frame); o += ", "; AInt(o, e->solid); o += ", "; AInt(o, e->powerups); o += ", ";
	AInt(o, e->weapon); o += ", "; AInt(o, e->legsAnim); o += ", "; AInt(o, e->torsoAnim); o += ", "; AInt(o, e->generic1);
	o += "]";
}

// an event entity as last seen under an entity number: what tells a new event from the same one seen again
struct EventSeen
{
	s32 Kind, Parm, Other, Other2, Client;
	float Pos[3];
};

static bool SameEvent(const EventSeen& a, const EventSeen& b)
{
	return a.Kind == b.Kind && a.Parm == b.Parm && a.Other == b.Other && a.Other2 == b.Other2 && a.Client == b.Client &&
		a.Pos[0] == b.Pos[0] && a.Pos[1] == b.Pos[1] && a.Pos[2] == b.Pos[2];
}

// a plain decimal number and nothing else (no names, no words: what decides whether a command's text is written)
static bool IsNumber(const char* s)
{
	if(!s) return false;
	if(*s == '+' || *s == '-') ++s;
	int digits = 0;
	for(; *s >= '0' && *s <= '9'; ++s) ++digits;
	if(*s == '.') for(++s; *s >= '0' && *s <= '9'; ++s) ++digits;
	if(!digits) return false;
	if(*s == 'e' || *s == 'E')
	{
		++s;
		if(*s == '+' || *s == '-') ++s;
		if(!(*s >= '0' && *s <= '9')) return false;
		while(*s >= '0' && *s <= '9') ++s;
	}
	return *s == '\0';
}

static void AIdTable(std::string& o, const char* key, const NamedId* names, size_t count, u32 type, u32 protocol, bool asMask)
{
	o += "\""; o += key; o += "\": {";
	bool first = true;
	for(size_t i = 0; i < count; ++i)
	{
		s32 id = -1;
		if(udtGetIdMagicNumber(&id, type, names[i].Id, protocol, (u32)udtMod::None) != (s32)udtErrorCode::None || id < 0) continue;
		if(asMask && id > 30) continue;
		if(!first) o += ", ";
		first = false;
		o += "\""; o += names[i].Name; o += "\": ";
		AInt(o, asMask ? (1LL << id) : (long long)id);
	}
	o += "}";
}

int main(int argc, char** argv)
{
	if(argc < 4) { printf("demodump <demo> <out.bin> <out.json> [<out.events.json>]\n"); return 1; }
	FILE* in = fopen(argv[1], "rb");
	if(!in) { fprintf(stderr, "cannot open %s\n", argv[1]); return 1; }
	udtInitLibrary();
	const u32 protocol = udtGetProtocolByFilePath(argv[1]);
	udtCuContext* cu = udtCuCreateContext();
	udtCuSetMessageCallback(cu, &Callback);
	if(!cu || udtCuStartParsing(cu, protocol) != (s32)udtErrorCode::None) { fprintf(stderr, "cannot start parsing\n"); return 1; }
	s32 etPlayer = -1, etItem = -1, etMissile = -1, etEvent = -1, firstPlayerCs = -1;
	udtGetIdMagicNumber(&etPlayer, (u32)udtMagicNumberType::EntityType, (s32)udtEntityType::Player, protocol, (u32)udtMod::None);
	udtGetIdMagicNumber(&etItem, (u32)udtMagicNumberType::EntityType, (s32)udtEntityType::Item, protocol, (u32)udtMod::None);
	udtGetIdMagicNumber(&etMissile, (u32)udtMagicNumberType::EntityType, (s32)udtEntityType::Missile, protocol, (u32)udtMod::None);
	udtGetIdMagicNumber(&etEvent, (u32)udtMagicNumberType::EntityType, (s32)udtEntityType::Event, protocol, (u32)udtMod::None);
	udtGetIdMagicNumber(&firstPlayerCs, (u32)udtMagicNumberType::ConfigStringIndex, (s32)udtConfigStringIndex::FirstPlayer, protocol, (u32)udtMod::None);

	FILE* bin = fopen(argv[2], "wb");
	FILE* js = fopen(argv[3], "w");
	if(!bin || !js) { fprintf(stderr, "cannot open outputs\n"); return 1; }
	FILE* evf = argc >= 5 ? fopen(argv[4], "wb") : NULL;
	if(argc >= 5 && !evf) { fprintf(stderr, "cannot open outputs\n"); return 1; }
	fprintf(js, "{\"protocol\": %u, \"ps_n\": %d, \"et_player\": %d, \"et_item\": %d, \"et_missile\": %d, \"et_event\": %d, \"gamestates\": [",
			protocol, PS_N, etPlayer, etItem, etMissile, etEvent);

	// out.events.json is put together in memory and written at the end
	std::string evRows, evGamestates, evCommands;
	std::vector<s32> evTimes;
	int evCount = 0, evGamestateCount = 0, evCommandCount = 0;
	static s32 ridingEvent[MAX_ENTITY_NUMBERS];			// an entity's event field as last seen (the game client's previousEvent)
	static s32 ridingSnap[MAX_ENTITY_NUMBERS];			// the snapshot record it was last in
	static s32 ridingTime[MAX_ENTITY_NUMBERS];
	for(int i = 0; i < MAX_ENTITY_NUMBERS; ++i) { ridingEvent[i] = 0; ridingSnap[i] = -2; ridingTime[i] = INT_MIN; }
	static EventSeen eventSeen[MAX_ENTITY_NUMBERS];		// the event entity last seen under a number
	memset(eventSeen, 0, sizeof(eventSeen));
	bool ownValid = false;								// the followed player's state as last seen (the game client's "ops")
	s32 ownClient = -1, ownSequence = 0, ownExternal = 0, ownEvents[2] = { 0, 0 };

	static u8 msg[ID_MAX_MSG_LENGTH];
	udtCuMessageInput input;
	udtCuMessageOutput output;
	u32 cont = 0;
	int snaps = 0, gamestates = 0;
	std::vector<float> o;
	for(;;)
	{
		if(fread(&input.MessageSequence, 4, 1, in) != 1 || fread(&input.BufferByteCount, 4, 1, in) != 1) break;
		if(input.MessageSequence == -1 && input.BufferByteCount == u32(-1)) break;
		if(input.BufferByteCount > ID_MAX_MSG_LENGTH) break;
		if(fread(msg, input.BufferByteCount, 1, in) != 1) break;
		input.Buffer = msg;
		if(udtCuParseMessage(cu, &output, &cont, &input) != (s32)udtErrorCode::None || cont == 0) break;
		if(evf)
		{
			const udtCuSnapshotMessage* const sameMessage = output.IsGameState ? NULL : output.GameStateOrSnapshot.Snapshot;
			for(u32 c = 0; c < output.CommandCount && output.Commands; ++c)
			{
				const udtCuCommandMessage& cm = output.Commands[c];
				const char* const name = (cm.TokenCount && cm.CommandTokens && cm.CommandTokens[0]) ? cm.CommandTokens[0] : "";
				evCommands += evCommandCount++ ? ",\n[" : "\n[";
				AInt(evCommands, snaps); evCommands += ", ";
				if(sameMessage) AInt(evCommands, sameMessage->ServerTimeMs); else evCommands += "null";
				evCommands += ", "; AInt(evCommands, cm.CommandSequence); evCommands += ", ";
				if(cm.IsConfigString && cm.TokenCount >= 3 && cm.CommandTokens)
				{
					evCommands += "\"cs\", "; AInt(evCommands, cm.ConfigStringIndex); evCommands += ", ";
					AStr(evCommands, cm.CommandTokens[2]);
				}
				else
				{
					bool numbers = true;
					for(u32 k = 1; k < cm.TokenCount && cm.CommandTokens; ++k) numbers = numbers && IsNumber(cm.CommandTokens[k]);
					AStr(evCommands, name); evCommands += ", null, ";
					if(numbers && cm.TokenCount >= 1 && cm.CommandString) AStr(evCommands, cm.CommandString); else evCommands += "null";
				}
				evCommands += "]";
			}
		}
		if(output.IsGameState)
		{
			const udtCuGamestateMessage* gs = output.GameStateOrSnapshot.GameState;
			if(!gs) continue;
			fprintf(js, "%s{\"at_snapshot\": %d, \"client_num\": %d, \"cs\": {", gamestates++ ? ", " : "", snaps, gs->ClientNumber);
			bool first = true;
			for(int i = 0; i < 2 + 64; ++i)
			{
				const u32 idx = i < 2 ? (u32)i : (u32)(firstPlayerCs + i - 2);
				udtCuConfigString cs;
				if(udtCuGetConfigString(cu, &cs, idx) != (s32)udtErrorCode::None || !cs.ConfigString || !cs.ConfigStringLength) continue;
				fprintf(js, "%s\"%s%d\": ", first ? "" : ", ", i < 2 ? "cs" : "player", i < 2 ? i : i - 2);
				JsonString(js, cs.ConfigString);
				first = false;
			}
			fprintf(js, "}}");
			if(evf)
			{
				evGamestates += evGamestateCount++ ? ",\n{" : "\n{";
				evGamestates += "\"at_snapshot\": "; AInt(evGamestates, snaps);
				evGamestates += ", \"client_num\": "; AInt(evGamestates, gs->ClientNumber);
				evGamestates += ", \"cs\": {";
				bool firstCs = true;
				for(u32 idx = 0; idx < CONFIG_STRING_COUNT; ++idx)
				{
					udtCuConfigString cs;
					if(udtCuGetConfigString(cu, &cs, idx) != (s32)udtErrorCode::None || !cs.ConfigString || !cs.ConfigStringLength) continue;
					evGamestates += firstCs ? "\"" : ", \"";
					firstCs = false;
					AInt(evGamestates, idx); evGamestates += "\": ";
					AStr(evGamestates, cs.ConfigString);
				}
				evGamestates += "}}";
				for(int i = 0; i < MAX_ENTITY_NUMBERS; ++i) { ridingEvent[i] = 0; ridingSnap[i] = -2; ridingTime[i] = INT_MIN; }
				memset(eventSeen, 0, sizeof(eventSeen));
				ownValid = false;
			}
			continue;
		}
		const udtCuSnapshotMessage* s = output.GameStateOrSnapshot.Snapshot;
		if(!s || !s->PlayerState) continue;
		const idPlayerStateBase* ps = s->PlayerState;
		o.clear();
		std::vector<float> pl, mi, it, ev;
		for(u32 i = 0; i < s->EntityCount; ++i)
		{
			const idEntityStateBase* e = s->Entities[i];
			if(!e) continue;
			if(e->eType == etPlayer)
			{
				W(pl, e->number); W(pl, e->clientNum); W3(pl, e->pos.trBase); W3(pl, e->pos.trDelta); W3(pl, e->apos.trBase);
				W(pl, e->weapon); W(pl, e->eFlags); W(pl, e->groundEntityNum); W(pl, e->event); W(pl, e->eventParm);
				W(pl, e->legsAnim); W(pl, e->torsoAnim); W(pl, e->powerups);
			}
			else if(e->eType == etMissile)
			{
				W(mi, e->number); W(mi, e->weapon); W(mi, (int)e->pos.trType); W(mi, e->pos.trTime); W3(mi, e->pos.trBase);
				W3(mi, e->pos.trDelta); W(mi, e->otherEntityNum); W(mi, e->clientNum);
			}
			else if(e->eType == etItem)
			{
				W(it, e->number); W(it, e->modelindex); W3(it, e->pos.trBase); W(it, e->eFlags);
			}
			else if(e->eType >= etEvent)
			{
				W(ev, e->number); W(ev, e->eType - etEvent); W(ev, e->eventParm); W3(ev, e->pos.trBase);
				W(ev, e->otherEntityNum); W(ev, e->otherEntityNum2); W(ev, e->clientNum);
			}
		}
		if(evf)
		{
			const s32 t = s->ServerTimeMs;
			for(u32 i = 0; i < s->EntityCount; ++i)
			{
				const idEntityStateBase* e = s->Entities[i];
				if(!e) continue;
				const s32 n = e->number;
				const bool tracked = n >= 0 && n < MAX_ENTITY_NUMBERS;
				if(e->eType >= etEvent)
				{
					// The library flags an event entity on the snapshot it is first seen in, and has by then moved its kind
					// from the type field into the event field (a kind still in the type field is read from there). Its
					// flag takes any event under a number that had one in the last 300 ms for the same event seen again;
					// in the first seconds after a map's restart the server does give a number to another event that
					// soon, so an event that is not the one last seen under its number is written as well.
					const int kind = e->eType > etEvent ? ((e->eType - etEvent) & ~EVENT_SEQUENCE_BITS) : (e->event & ~EVENT_SEQUENCE_BITS);
					EventSeen now;
					now.Kind = kind; now.Parm = e->eventParm; now.Other = e->otherEntityNum; now.Other2 = e->otherEntityNum2; now.Client = e->clientNum;
					now.Pos[0] = e->pos.trBase[0]; now.Pos[1] = e->pos.trBase[1]; now.Pos[2] = e->pos.trBase[2];
					const bool flagged = s->EntityFlags && (s->EntityFlags[i] & (1 << (int)udtEntityStateFlag::NewEvent));
					if(flagged || (tracked && !SameEvent(now, eventSeen[n]))) AEvent(evRows, evCount, snaps, t, 0, etEvent, kind, e);
					if(tracked) { eventSeen[n] = now; ridingEvent[n] = 0; ridingSnap[n] = -2; ridingTime[n] = INT_MIN; }
					continue;
				}
				if(!tracked) continue;
				// an event in another entity's event field, as the game client finds it (CG_CheckEvents, CG_ResetEntity)
				if(ridingSnap[n] != snaps - 1 && ((long long)ridingTime[n] < (long long)t - EVENT_WINDOW_MS || ridingTime[n] > t)) ridingEvent[n] = 0;
				if(e->event != ridingEvent[n])
				{
					ridingEvent[n] = e->event;
					if((e->event & ~EVENT_SEQUENCE_BITS) != 0) AEvent(evRows, evCount, snaps, t, 1, e->eType, e->event & ~EVENT_SEQUENCE_BITS, e);
				}
				ridingSnap[n] = snaps;
				ridingTime[n] = t;
			}
			// the followed player's own events, as the game client finds them in his player state (CG_CheckPlayerstateEvents;
			// a sequence that went back, at a restart of the map, starts afresh like a cut does)
			if(ownValid && ownClient == ps->clientNum && ps->eventSequence >= ownSequence)
			{
				idEntityStateBase own;
				memset(&own, 0, sizeof(own));
				own.number = ps->clientNum;
				own.eType = etPlayer;
				own.eFlags = ps->eFlags;
				for(int k = 0; k < 3; ++k) { own.pos.trBase[k] = ps->origin[k]; own.pos.trDelta[k] = ps->velocity[k]; own.apos.trBase[k] = ps->viewangles[k]; }
				own.angles2[1] = (f32)ps->movementDir;
				own.groundEntityNum = ps->groundEntityNum;
				own.loopSound = ps->loopSound;
				own.clientNum = ps->clientNum;
				own.weapon = ps->weapon;
				own.legsAnim = ps->legsAnim;
				own.torsoAnim = ps->torsoAnim;
				own.generic1 = ps->generic1;
				if(ps->externalEvent && ps->externalEvent != ownExternal && (ps->externalEvent & ~EVENT_SEQUENCE_BITS) != 0)
				{
					own.event = ps->externalEvent;
					own.eventParm = ps->externalEventParm;
					AEvent(evRows, evCount, snaps, t, 2, etPlayer, ps->externalEvent & ~EVENT_SEQUENCE_BITS, &own);
				}
				for(s32 q = ps->eventSequence - 2; q < ps->eventSequence; ++q)
				{
					if(q < 0) continue;
					const s32 slot = q & 1;
					if(q >= ownSequence || (q > ownSequence - 2 && ps->events[slot] != ownEvents[slot]))
					{
						if((ps->events[slot] & ~EVENT_SEQUENCE_BITS) == 0) continue;
						own.event = ps->events[slot];
						own.eventParm = ps->eventParms[slot];
						AEvent(evRows, evCount, snaps, t, 2, etPlayer, ps->events[slot] & ~EVENT_SEQUENCE_BITS, &own);
					}
				}
			}
			ownValid = true;
			ownClient = ps->clientNum;
			ownSequence = ps->eventSequence;
			ownExternal = ps->externalEvent;
			ownEvents[0] = ps->events[0];
			ownEvents[1] = ps->events[1];
			evTimes.push_back(t);
		}
		W(o, 1); W(o, s->ServerTimeMs); W(o, pl.size() / 19); W(o, mi.size() / 12); W(o, it.size() / 6); W(o, ev.size() / 9);
		W(o, ps->clientNum); W(o, ps->commandTime); W3(o, ps->origin); W3(o, ps->velocity); W3(o, ps->viewangles);
		W(o, ps->delta_angles[0]); W(o, ps->delta_angles[1]); W(o, ps->delta_angles[2]);
		W(o, ps->pm_type); W(o, ps->pm_flags); W(o, ps->pm_time);
		W(o, ps->groundEntityNum); W(o, ps->weapon); W(o, ps->weaponstate); W(o, ps->weaponTime); W(o, ps->viewheight);
		W(o, ps->eFlags); W(o, ps->movementDir); W(o, ps->gravity); W(o, ps->speed);
		for(int i = 0; i < 16; ++i) W(o, ps->stats[i]);
		for(int i = 0; i < 16; ++i) W(o, ps->persistant[i]);
		for(int i = 0; i < 16; ++i) W(o, ps->ammo[i]);
		for(int i = 0; i < 16; ++i) W(o, ps->powerups[i]);
		W(o, ps->events[0]); W(o, ps->events[1]); W(o, ps->eventParms[0]); W(o, ps->eventParms[1]);
		W(o, ps->eventSequence); W(o, ps->externalEvent); W(o, ps->externalEventParm);
		W(o, ps->damageEvent); W(o, ps->damageYaw); W(o, ps->damagePitch); W(o, ps->damageCount);
		W(o, ps->generic1); W(o, ps->jumppad_ent);
		o.insert(o.end(), pl.begin(), pl.end());
		o.insert(o.end(), mi.begin(), mi.end());
		o.insert(o.end(), it.begin(), it.end());
		o.insert(o.end(), ev.begin(), ev.end());
		fwrite(o.data(), sizeof(float), o.size(), bin);
		++snaps;
	}
	fprintf(js, "], \"snapshots\": %d}\n", snaps);
	fclose(js);
	fclose(bin);
	fclose(in);
	if(evf)
	{
		std::string h;
		h += "{\"version\": "; AInt(h, EVENTS_VERSION);
		h += ", \"protocol\": "; AInt(h, protocol);
		h += ", \"snapshots\": "; AInt(h, snaps);
		h += ",\n"; AIdTable(h, "entity_types", EntityTypeNames, sizeof(EntityTypeNames) / sizeof(NamedId), (u32)udtMagicNumberType::EntityType, protocol, false);
		h += ",\n"; AIdTable(h, "event_ids", EntityEventNames, sizeof(EntityEventNames) / sizeof(NamedId), (u32)udtMagicNumberType::EntityEvent, protocol, false);
		h += ",\n"; AIdTable(h, "config_string_ids", ConfigStringNames, sizeof(ConfigStringNames) / sizeof(NamedId), (u32)udtMagicNumberType::ConfigStringIndex, protocol, false);
		h += ",\n"; AIdTable(h, "means_of_death", MeanOfDeathNames, sizeof(MeanOfDeathNames) / sizeof(NamedId), (u32)udtMagicNumberType::MeanOfDeath, protocol, false);
		h += ",\n"; AIdTable(h, "item_ids", ItemNames, sizeof(ItemNames) / sizeof(NamedId), (u32)udtMagicNumberType::Item, protocol, false);
		h += ",\n"; AIdTable(h, "entity_flag_masks", EntityFlagNames, sizeof(EntityFlagNames) / sizeof(NamedId), (u32)udtMagicNumberType::EntityFlag, protocol, true);
		h += ",\n\"event_cols\": ["; h += EventCols; h += "],\n\"events\": [";
		fwrite(h.data(), 1, h.size(), evf);
		fwrite(evRows.data(), 1, evRows.size(), evf);
		h = "],\n\"gamestates\": [";
		fwrite(h.data(), 1, h.size(), evf);
		fwrite(evGamestates.data(), 1, evGamestates.size(), evf);
		h = "],\n\"commands\": [";
		fwrite(h.data(), 1, h.size(), evf);
		fwrite(evCommands.data(), 1, evCommands.size(), evf);
		h = "],\n\"times\": [";
		for(size_t i = 0; i < evTimes.size(); ++i) { if(i) h += ","; AInt(h, evTimes[i]); }
		h += "]}\n";
		fwrite(h.data(), 1, h.size(), evf);
		fclose(evf);
	}
	udtCuDestroyContext(cu);
	udtShutDownLibrary();
	printf("%d snapshots, %d gamestates\n", snaps, gamestates);
	return 0;
}
