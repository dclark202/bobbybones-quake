#ifndef BOTCTL_H
#define BOTCTL_H

#include <Python.h>
#include "quake_common.h"

extern SV_ClientThink_ptr SV_ClientThink;
void __cdecl My_SV_ClientThink(client_t* cl, usercmd_t* cmd);

void Botctl_AfterFrame(void);

PyObject* PyMinqlx_SetBotInput(PyObject* self, PyObject* args);
PyObject* PyMinqlx_ClearBotInput(PyObject* self, PyObject* args);
PyObject* PyMinqlx_ViewAngles(PyObject* self, PyObject* args);
PyObject* PyMinqlx_SetView(PyObject* self, PyObject* args);
PyObject* PyMinqlx_LastUsercmd(PyObject* self, PyObject* args);
PyObject* PyMinqlx_RanUsercmd(PyObject* self, PyObject* args);
PyObject* PyMinqlx_KeyCounts(PyObject* self, PyObject* args);
PyObject* PyMinqlx_SetBotSubsteps(PyObject* self, PyObject* args);
PyObject* PyMinqlx_ItemStates(PyObject* self, PyObject* args);
PyObject* PyMinqlx_Missiles(PyObject* self, PyObject* args);
PyObject* PyMinqlx_SetBotMove(PyObject* self, PyObject* args);
PyObject* PyMinqlx_SetBotAim(PyObject* self, PyObject* args);
PyObject* PyMinqlx_AiWantsFire(PyObject* self, PyObject* args);

#endif
