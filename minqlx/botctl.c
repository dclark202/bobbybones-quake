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
} bot_override_t;

static bot_override_t overrides[MAX_CLIENTS];
static long long think_calls[MAX_CLIENTS];
static int ai_wants_fire[MAX_CLIENTS];

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
                cmd->forwardmove = (signed char)(127.0f * o->move_speed * cosf(rel));
                cmd->rightmove = (signed char)(-127.0f * o->move_speed * sinf(rel));
                cmd->upmove = o->up;
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
        }
    }
done:
    SV_ClientThink(cl, cmd);
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
    o->move_speed = speed < 0 ? 0 : speed > 1 ? 1 : speed;
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
