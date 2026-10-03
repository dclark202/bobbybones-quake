// demodump: turn a Quake Live demo (.dm_91 / .dm_90 / .dm_73) into a flat binary stream of snapshots,
// for imitation learning. Built on UberDemoTools' custom parsing API (GPL-3.0, github.com/mightycow/uberdemotools).
//
//   demodump <demo> <out.bin> <out.json>
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
#include "uberdemotools.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>
#include <vector>

#define PS_N (1 + 1 + 3 + 3 + 3 + 3 + 3 + 9 + 16 + 16 + 16 + 16 + 2 + 2 + 3 + 4 + 2)

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

int main(int argc, char** argv)
{
	if(argc < 4) { printf("demodump <demo> <out.bin> <out.json>\n"); return 1; }
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
	fprintf(js, "{\"protocol\": %u, \"ps_n\": %d, \"et_player\": %d, \"et_item\": %d, \"et_missile\": %d, \"et_event\": %d, \"gamestates\": [",
			protocol, PS_N, etPlayer, etItem, etMissile, etEvent);

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
	udtCuDestroyContext(cu);
	udtShutDownLibrary();
	printf("%d snapshots, %d gamestates\n", snaps, gamestates);
	return 0;
}
