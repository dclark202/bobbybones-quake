// ql-bot: per-client usercmd override, so Python can drive a bot's inputs.
#include <Python.h>
#include <string.h>
#include <math.h>

#include "quake_common.h"
#include "botctl.h"

#define BOTCTL_ANGLE2SHORT(x) ((int)((x) * 65536.0f / 360.0f) & 65535)

typedef struct {
    int active;
    int hybrid;           // 1: keep the AI's aim/buttons/weapon, only steer movement
    float move_yaw;       // hybrid: world-space direction to move in
    float move_speed;     // hybrid: 0..1 fraction of full move
    int aim_on;           // hybrid: override aim/weapon whenever the AI decides to shoot
    int allow_fire;       // hybrid: 0 = suppress attack (reaction time), 1 = AI decides, 2 = track + hold fire (LG)
    float aim_pitch, aim_yaw;
    int aim_weapon;
    int buttons;
    int weapon;
    float pitch, yaw;
    signed char forward, right, up;
    int substeps;         // full control: split each command into this many moves (3 = 125 fps human physics)
    int cleared_bot_flag; // we cleared SVF_BOT so the game moves on every command (restored when off)
    float prev_yaw;
    int have_prev_yaw;
} bot_override_t;

#define BOTCTL_SVF_BOT 0x00000008   // Q3/QL: bots' commands are queued and moved once per server frame

static bot_override_t overrides[MAX_CLIENTS];
// Full control with human physics (set_bot_input + set_bot_substeps) is driven by us once per game frame, from
// Botctl_BeforeFrame, right after the plugins' frame handlers have set this frame's input. Until 2026-10-08 the input
// rode on the game AI's own command, which the engine sends once per server loop: one frame late, and not at all in
// the extra game frames a busy server runs to catch up. In those frames the game replayed the bot's last command, so
// he kept his keys down with a frozen view (measured in the sparring games run beside a training: the view unchanged
// in half of the frames on Blood Run and Aerowalk, standing against walls for up to 45 s).
static int self_driving = 0;
static long long think_calls[MAX_CLIENTS];
static int ai_wants_fire[MAX_CLIENTS];
static usercmd_t ran_cmd[MAX_CLIENTS];
// key and button changes seen in every command a client sent (125 a second), counted since he connected:
// forward/back, strafe, jump/crouch, fire presses, other buttons, weapon
static long long key_counts[MAX_CLIENTS][6];
#define BOTCTL_SGN(v) ((v) > 0 ? 1 : ((v) < 0 ? -1 : 0))

SV_ClientThink_ptr SV_ClientThink;

void __cdecl My_SV_ClientThink(client_t* cl, usercmd_t* cmd) {
    int id = cl - svs->clients;
    if (id >= 0 && id < MAX_CLIENTS) {
        think_calls[id]++;
        bot_override_t* o = &overrides[id];
        // Only touch fully connected, in-game clients: during map changes the game
        // state behind g_entities is torn down and must not be read.
        if (o->active && cl->state == CS_ACTIVE && cl->gentity && g_entities && g_entities[id].client) {
            int* delta = g_entities[id].client->ps.delta_angles;
            if (!o->hybrid && o->substeps > 1 && !self_driving)
                return;                 // the game AI's command for a bot we drive ourselves: not run (see self_driving)
            if (o->hybrid) {
                ai_wants_fire[id] = cmd->buttons & 1;
                // The AI decides *when* to shoot: it traces for line of sight before pressing
                // attack. When it does, we swap in our own (exact) aim and weapon.
                if (o->aim_on) {
                    if (o->aim_weapon > 0)
                        cmd->weapon = (byte)o->aim_weapon;
                    if (o->allow_fire == 2) {
                        // continuous tracking weapon: we own the crosshair every frame and hold fire
                        cmd->angles[0] = (BOTCTL_ANGLE2SHORT(o->aim_pitch) - delta[0]) & 65535;
                        cmd->angles[1] = (BOTCTL_ANGLE2SHORT(o->aim_yaw) - delta[1]) & 65535;
                        cmd->buttons |= 1;
                    } else if (cmd->buttons & 1) {
                        cmd->angles[0] = (BOTCTL_ANGLE2SHORT(o->aim_pitch) - delta[0]) & 65535;
                        cmd->angles[1] = (BOTCTL_ANGLE2SHORT(o->aim_yaw) - delta[1]) & 65535;
                        if (!o->allow_fire)
                            cmd->buttons &= ~1;
                    }
                }
                // convert our world move direction into forward/right relative to the final view yaw
                float ai_yaw = (float)((cmd->angles[1] + delta[1]) & 65535) * (360.0f / 65536.0f);
                float rel = (o->move_yaw - ai_yaw) * (3.14159265f / 180.0f);
                if (o->move_speed >= 0) {          // < 0: leave the AI's own movement alone
                    cmd->forwardmove = (signed char)(127.0f * o->move_speed * cosf(rel));
                    cmd->rightmove = (signed char)(-127.0f * o->move_speed * sinf(rel));
                    cmd->upmove = o->up;
                }
                goto done;
            }
            cmd->forwardmove = o->forward;
            cmd->rightmove = o->right;
            cmd->upmove = o->up;
            cmd->buttons = o->buttons;
            if (o->weapon > 0)
                cmd->weapon = (byte)o->weapon;
            cmd->angles[0] = (BOTCTL_ANGLE2SHORT(o->pitch) - delta[0]) & 65535;
            cmd->angles[1] = (BOTCTL_ANGLE2SHORT(o->yaw) - delta[1]) & 65535;
            cmd->angles[2] = (0 - delta[2]) & 65535;
            if (o->substeps > 1) {
                // Human physics: a 125 fps player sends a command every ~8 ms and each one is moved on its own.
                // The game only moves bots once per frame, so drop the bot flag while we drive and feed the
                // frame's 25 ms as substeps commands, turning the view a share of the way on each.
                gentity_t* ent = &g_entities[id];
                if (ent->r.svFlags & BOTCTL_SVF_BOT) {
                    ent->r.svFlags &= ~BOTCTL_SVF_BOT;
                    o->cleared_bot_flag = 1;
                }
                int t0 = ent->client->ps.commandTime, t1 = cmd->serverTime, span = t1 - t0;
                if (span >= 2 * o->substeps && span <= 100) {
                    float y0 = o->have_prev_yaw ? o->prev_yaw : o->yaw;
                    float dy = fmodf(o->yaw - y0 + 540.0f, 360.0f) - 180.0f;
                    for (int k = 1; k < o->substeps; k++) {
                        usercmd_t sub = *cmd;
                        sub.serverTime = t0 + span * k / o->substeps;
                        float yk = y0 + dy * (float)(sub.serverTime - t0) / (float)span;
                        sub.angles[1] = (BOTCTL_ANGLE2SHORT(yk) - ent->client->ps.delta_angles[1]) & 65535;
                        SV_ClientThink(cl, &sub);
                    }
                }
                o->prev_yaw = o->yaw;
                o->have_prev_yaw = 1;
            }
        }
    }
done:
    if (id >= 0 && id < MAX_CLIENTS)
        {
            usercmd_t* o = &ran_cmd[id];
            key_counts[id][0] += BOTCTL_SGN(cmd->forwardmove) != BOTCTL_SGN(o->forwardmove);
            key_counts[id][1] += BOTCTL_SGN(cmd->rightmove) != BOTCTL_SGN(o->rightmove);
            key_counts[id][2] += BOTCTL_SGN(cmd->upmove) != BOTCTL_SGN(o->upmove);
            key_counts[id][3] += (cmd->buttons & 1) && !(o->buttons & 1);
            key_counts[id][4] += ((cmd->buttons ^ o->buttons) & ~1) != 0;
            key_counts[id][5] += cmd->weapon != o->weapon;
        }
        ran_cmd[id] = *cmd;            // the exact command this think runs (cl->lastUsercmd is stale for bots)
    SV_ClientThink(cl, cmd);
}

// Called right after the game has run its frame. The bot flag is only dropped while the game moves the
// player; it must be back before the server sends snapshots, or the server tries to send network messages
// to a bot (crash: "netchan queue is not properly initialized" once a message needs fragments).
void Botctl_AfterFrame(void) {
    if (!g_entities)
        return;
    for (int id = 0; id < MAX_CLIENTS; id++) {
        if (overrides[id].cleared_bot_flag && overrides[id].substeps && g_entities[id].inuse && g_entities[id].client)
            g_entities[id].r.svFlags |= BOTCTL_SVF_BOT;
    }
}

// Called once per game frame, after the plugins' frame handlers and before the game moves anything: every bot under
// full control gets this frame's command now (split into its substeps), with the frame's own time.
void Botctl_BeforeFrame(int time) {
    if (!g_entities || !svs || !svs->clients || !sv_maxclients)
        return;
    for (int id = 0; id < MAX_CLIENTS && id < sv_maxclients->integer; id++) {
        bot_override_t* o = &overrides[id];
        if (!o->active || o->hybrid || o->substeps <= 1)
            continue;
        client_t* cl = &svs->clients[id];
        if (cl->state != CS_ACTIVE || !cl->gentity || !g_entities[id].inuse || !g_entities[id].client)
            continue;
        usercmd_t cmd;
        memset(&cmd, 0, sizeof(cmd));
        cmd.serverTime = time;
        self_driving = 1;
        My_SV_ClientThink(cl, &cmd);
        self_driving = 0;
    }
}

static int valid_client(int id) {
    if (id < 0 || id >= sv_maxclients->integer) {
        PyErr_Format(PyExc_ValueError, "client_id must be a number from 0 to %d.", sv_maxclients->integer - 1);
        return 0;
    }
    return 1;
}

// set_bot_input(client_id, forward, right, up, buttons, weapon, pitch, yaw)
PyObject* PyMinqlx_SetBotInput(PyObject* self, PyObject* args) {
    int id, fwd, right, up, buttons, weapon;
    float pitch, yaw;
    if (!PyArg_ParseTuple(args, "iiiiiiff:set_bot_input", &id, &fwd, &right, &up, &buttons, &weapon, &pitch, &yaw))
        return NULL;
    if (!valid_client(id))
        return NULL;
    bot_override_t* o = &overrides[id];
    o->forward = (signed char)(fwd > 127 ? 127 : fwd < -127 ? -127 : fwd);
    o->right = (signed char)(right > 127 ? 127 : right < -127 ? -127 : right);
    o->up = (signed char)(up > 127 ? 127 : up < -127 ? -127 : up);
    o->buttons = buttons;
    o->weapon = weapon;
    o->pitch = pitch;
    o->yaw = yaw;
    o->hybrid = 0;
    o->active = 1;
    Py_RETURN_NONE;
}

// set_bot_substeps(client_id, n): with full control (set_bot_input), move the bot n times per server frame
// like a human client at ~n*40 fps (3 = 125 fps). 0 or 1 turns it off and gives the bot flag back.
PyObject* PyMinqlx_SetBotSubsteps(PyObject* self, PyObject* args) {
    int id, n;
    if (!PyArg_ParseTuple(args, "ii:set_bot_substeps", &id, &n))
        return NULL;
    if (!valid_client(id))
        return NULL;
    bot_override_t* o = &overrides[id];
    o->substeps = n > 1 ? (n > 8 ? 8 : n) : 0;
    o->have_prev_yaw = 0;
    if (!o->substeps && o->cleared_bot_flag && g_entities) {
        g_entities[id].r.svFlags |= BOTCTL_SVF_BOT;
        o->cleared_bot_flag = 0;
    }
    Py_RETURN_NONE;
}

// set_bot_move(client_id, move_yaw, up): hybrid control - AI aims and shoots, we steer
PyObject* PyMinqlx_SetBotMove(PyObject* self, PyObject* args) {
    int id, up;
    float move_yaw, speed = 1.0f;
    if (!PyArg_ParseTuple(args, "ifi|f:set_bot_move", &id, &move_yaw, &up, &speed))
        return NULL;
    if (!valid_client(id))
        return NULL;
    bot_override_t* o = &overrides[id];
    o->move_yaw = move_yaw;
    o->move_speed = speed < 0 ? -1.0f : speed > 1 ? 1 : speed;
    o->up = (signed char)(up > 127 ? 127 : up < -127 ? -127 : up);
    o->hybrid = 1;
    o->active = 1;
    Py_RETURN_NONE;
}

PyObject* PyMinqlx_ClearBotInput(PyObject* self, PyObject* args) {
    int id;
    if (!PyArg_ParseTuple(args, "i:clear_bot_input", &id))
        return NULL;
    if (!valid_client(id))
        return NULL;
    overrides[id].active = 0;
    if (overrides[id].cleared_bot_flag && g_entities && g_entities[id].client)
        g_entities[id].r.svFlags |= BOTCTL_SVF_BOT;
    overrides[id].cleared_bot_flag = 0;
    overrides[id].substeps = 0;
    Py_RETURN_NONE;
}

// set_view(client_id, pitch, yaw): turn a player's view (as a teleporter does), for humans and bots
PyObject* PyMinqlx_SetView(PyObject* self, PyObject* args) {
    int id;
    float pitch, yaw;
    if (!PyArg_ParseTuple(args, "iff:set_view", &id, &pitch, &yaw))
        return NULL;
    if (!valid_client(id))
        return NULL;
    if (!g_entities || !g_entities[id].client)
        Py_RETURN_NONE;
    playerState_t* ps = &g_entities[id].client->ps;
    ps->delta_angles[0] = BOTCTL_ANGLE2SHORT(pitch) - ran_cmd[id].angles[0];
    ps->delta_angles[1] = BOTCTL_ANGLE2SHORT(yaw) - ran_cmd[id].angles[1];
    ps->delta_angles[2] = 0 - ran_cmd[id].angles[2];
    ps->viewangles[0] = pitch;
    ps->viewangles[1] = yaw;
    ps->viewangles[2] = 0;
    Py_RETURN_NONE;
}

// view_angles(client_id) -> (pitch, yaw, roll)
PyObject* PyMinqlx_ViewAngles(PyObject* self, PyObject* args) {
    int id;
    if (!PyArg_ParseTuple(args, "i:view_angles", &id))
        return NULL;
    if (!valid_client(id))
        return NULL;
    if (!g_entities[id].client)
        Py_RETURN_NONE;
    float* a = g_entities[id].client->ps.viewangles;
    return Py_BuildValue("(fff)", a[0], a[1], a[2]);
}

// last_usercmd(client_id) -> (serverTime, buttons, weapon, forward, right, up, think_calls)
PyObject* PyMinqlx_LastUsercmd(PyObject* self, PyObject* args) {
    int id;
    if (!PyArg_ParseTuple(args, "i:last_usercmd", &id))
        return NULL;
    if (!valid_client(id))
        return NULL;
    usercmd_t* c = &svs->clients[id].lastUsercmd;
    return Py_BuildValue("(iiiiiiL)", c->serverTime, c->buttons, (int)c->weapon,
        (int)c->forwardmove, (int)c->rightmove, (int)c->upmove, think_calls[id]);
}

// ran_usercmd(client_id) -> (serverTime, buttons, weapon, forward, right, up, pitch, yaw): the last command
// SV_ClientThink actually ran for this client (after any bot override), view angles in degrees incl. delta
PyObject* PyMinqlx_RanUsercmd(PyObject* self, PyObject* args) {
    int id;
    if (!PyArg_ParseTuple(args, "i:ran_usercmd", &id))
        return NULL;
    if (!valid_client(id))
        return NULL;
    usercmd_t* c = &ran_cmd[id];
    float pitch = 0, yaw = 0;
    if (g_entities && g_entities[id].client) {
        int* delta = g_entities[id].client->ps.delta_angles;
        pitch = (float)((c->angles[0] + delta[0]) & 65535) * (360.0f / 65536.0f);
        yaw = (float)((c->angles[1] + delta[1]) & 65535) * (360.0f / 65536.0f);
    }
    return Py_BuildValue("(iiiiiiff)", c->serverTime, c->buttons, (int)c->weapon,
        (int)c->forwardmove, (int)c->rightmove, (int)c->upmove, pitch, yaw);
}

// key_counts(client_id) -> (forward/back, strafe, jump/crouch, fire presses, other buttons, weapon): changes counted
// over every command the client sent since he connected
PyObject* PyMinqlx_KeyCounts(PyObject* self, PyObject* args) {
    int id;
    if (!PyArg_ParseTuple(args, "i:key_counts", &id))
        return NULL;
    if (!valid_client(id))
        return NULL;
    long long* k = key_counts[id];
    return Py_BuildValue("(LLLLLL)", k[0], k[1], k[2], k[3], k[4], k[5]);
}

// item_states() -> (level_time, [(entity_num, classname, x, y, z, available, nextthink), ...])
PyObject* PyMinqlx_ItemStates(PyObject* self, PyObject* args) {
    PyObject* list = PyList_New(0);
    for (int i = 0; i < MAX_GENTITIES; i++) {
        gentity_t* ent = &g_entities[i];
        if (!ent->inuse || ent->s.eType != ET_ITEM || ent->item == NULL)
            continue;
        float* o = ent->s.pos.trBase;
        PyObject* t = Py_BuildValue("(isfffii)", i, ent->classname ? ent->classname : "",
            o[0], o[1], o[2], (ent->s.eFlags & EF_NODRAW) ? 0 : 1, ent->nextthink);
        PyList_Append(list, t);
        Py_DECREF(t);
    }
    PyObject* res = Py_BuildValue("(iO)", level ? level->time : 0, list);
    Py_DECREF(list);
    return res;
}

// spawn_map_item(classname, x, y, z) -> entity number. An item put on the map that behaves like one of the map's own:
// it falls to the floor, and after it is taken it comes back on the game's own timer for its kind. LaunchItem makes a
// *dropped* item (taken once, and gone after 30 s): the dropped flag and its timer are cleared. Used to give a
// free-for-all game the duel layout of a map (owner, 2026-10-09; plugins/powerups.py).
PyObject* PyMinqlx_SpawnMapItem(PyObject* self, PyObject* args) {
    const char* cls;
    float x, y, z;
    if (!PyArg_ParseTuple(args, "sfff:spawn_map_item", &cls, &x, &y, &z))
        return NULL;
    int id = 0;
    for (int i = 1; i < bg_numItems; i++) {
        if (bg_itemlist[i].classname && strcmp(bg_itemlist[i].classname, cls) == 0) {
            id = i;
            break;
        }
    }
    if (!id) {
        PyErr_Format(PyExc_ValueError, "no such item: %s", cls);
        return NULL;
    }
    vec3_t origin = {x, y, z};
    vec3_t velocity = {0, 0, 0};
    gentity_t* ent = LaunchItem(bg_itemlist + id, origin, velocity);
    if (!ent)
        Py_RETURN_NONE;
    ent->flags &= ~FL_DROPPED_ITEM;
    ent->nextthink = 0;
    ent->think = 0;
    return PyLong_FromLong((long)(ent - g_entities));
}

// missiles() -> [(entity_num, owner, weapon, x, y, z, vx, vy, vz), ...] for projectiles in flight
PyObject* PyMinqlx_Missiles(PyObject* self, PyObject* args) {
    PyObject* list = PyList_New(0);
    if (!g_entities)
        return list;
    for (int i = 0; i < MAX_GENTITIES; i++) {
        gentity_t* ent = &g_entities[i];
        if (!ent->inuse || ent->s.eType != ET_MISSILE)
            continue;
        float* o = ent->r.currentOrigin;
        float* v = ent->s.pos.trDelta;
        PyObject* t = Py_BuildValue("(iiiffffff)", i, ent->r.ownerNum, ent->s.weapon, o[0], o[1], o[2], v[0], v[1], v[2]);
        PyList_Append(list, t);
        Py_DECREF(t);
    }
    return list;
}

// set_bot_aim(client_id, pitch, yaw, weapon): hybrid aim override (weapon < 0 turns it off)
PyObject* PyMinqlx_SetBotAim(PyObject* self, PyObject* args) {
    int id, weapon, allow_fire = 1;
    float pitch, yaw;
    if (!PyArg_ParseTuple(args, "iffi|i:set_bot_aim", &id, &pitch, &yaw, &weapon, &allow_fire))
        return NULL;
    if (!valid_client(id))
        return NULL;
    bot_override_t* o = &overrides[id];
    o->aim_on = weapon >= 0;
    o->aim_pitch = pitch;
    o->aim_yaw = yaw;
    o->aim_weapon = weapon;
    o->allow_fire = allow_fire;
    Py_RETURN_NONE;
}

// ai_wants_fire(client_id) -> bool: did the bot AI press attack this frame (it has line of sight)?
PyObject* PyMinqlx_AiWantsFire(PyObject* self, PyObject* args) {
    int id;
    if (!PyArg_ParseTuple(args, "i:ai_wants_fire", &id))
        return NULL;
    if (!valid_client(id))
        return NULL;
    return PyBool_FromLong(ai_wants_fire[id]);
}
