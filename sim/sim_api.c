/*
 * qsim: Quake 3 / Quake Live player movement in a box, for training movement policies fast.
 *
 * Wraps ioquake3's Pmove (bg_pmove.c / bg_slidemove.c) and collision model (cm_*.c) behind a small
 * C API loaded with ctypes (sim/qsim.py). One process = one map + many players stepped in a loop.
 * Not thread-safe (Pmove and CM_Trace use globals): parallelize with processes.
 *
 * GPL-2.0-or-later (ioquake3 code) / GPL-3.0 (this repo).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <setjmp.h>
#include <math.h>
#include "q3/q_shared.h"
#include "q3/qcommon.h"
#include "q3/bg_public.h"

#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif

extern float pm_jumpVelocity, pm_chainJumpVelocity;
extern int pm_autoHop, pm_chainJump, pm_chainJumpMs;

/* ---------------- engine stubs the vendored code expects ---------------- */
static jmp_buf err_jmp;
static int err_set;
static char err_msg[1024];
static const char *map_path;

void QDECL Com_Error(int level, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    Q_vsnprintf(err_msg, sizeof(err_msg), fmt, ap);
    va_end(ap);
    if (err_set) longjmp(err_jmp, 1);
    fprintf(stderr, "qsim fatal: %s\n", err_msg);
    exit(1);
}
void QDECL Com_Printf(const char *fmt, ...) { (void)fmt; }
void QDECL Com_DPrintf(const char *fmt, ...) { (void)fmt; }
void *Hunk_Alloc(int size, ha_pref preference) { (void)preference; return calloc(1, size); }
void *Z_Malloc(int size) { return calloc(1, size); }
void Z_Free(void *ptr) { free(ptr); }
void *Hunk_AllocateTempMemory(int size) { return malloc(size); }
void Hunk_FreeTempMemory(void *buf) { free(buf); }
unsigned Com_BlockChecksum(const void *buffer, int length) { (void)buffer; (void)length; return 0; }
static cvar_t cvars[16];
static int ncvars;
cvar_t *Cvar_Get(const char *name, const char *value, int flags) {
    cvar_t *c = &cvars[ncvars < 15 ? ncvars++ : 15];
    (void)name; (void)flags;
    c->value = (float)atof(value);
    c->integer = atoi(value);
    return c;
}
long FS_ReadFile(const char *qpath, void **buffer) {
    FILE *f = fopen(map_path, "rb");
    long n;
    (void)qpath;
    *buffer = NULL;
    if (!f) return -1;
    fseek(f, 0, SEEK_END);
    n = ftell(f);
    fseek(f, 0, SEEK_SET);
    *buffer = malloc(n);
    if (fread(*buffer, 1, n, f) != (size_t)n) { free(*buffer); *buffer = NULL; n = -1; }
    fclose(f);
    return n;
}
void FS_FreeFile(void *buffer) { free(buffer); }

/* the server snaps velocity to whole units every frame: part of the real physics (and of strafe jumping) */
void trap_SnapVector(float *v) {
    v[0] = (float)floor(v[0] + 0.5f);
    v[1] = (float)floor(v[1] + 0.5f);
    v[2] = (float)floor(v[2] + 0.5f);
}
void BotDrawDebugPolygons(void (*drawPoly)(int color, int numPoints, float *points), int value) {
    (void)drawPoly; (void)value;
}

/* ---------------- world callbacks for Pmove ---------------- */
static void sim_trace(trace_t *results, const vec3_t start, const vec3_t mins, const vec3_t maxs,
                      const vec3_t end, int passEntityNum, int contentMask) {
    (void)passEntityNum;
    CM_BoxTrace(results, start, end, mins, maxs, 0, contentMask, qfalse);
}
static int sim_pointcontents(const vec3_t point, int passEntityNum) {
    (void)passEntityNum;
    return CM_PointContents(point, 0);
}

static void touch_triggers(playerState_t *ps);

/* ---------------- players ---------------- */
static playerState_t *players;
static int nplayers;

API const char *qsim_error(void) { return err_msg; }

API int qsim_load_map(const char *bsp_path) {
    int checksum;
    map_path = bsp_path;
    err_set = 1;
    if (setjmp(err_jmp)) { err_set = 0; return -1; }
    CM_LoadMap("maps/sim.bsp", qfalse, &checksum);
    err_set = 0;
    return 0;
}

API const char *qsim_entity_string(void) { return CM_EntityString(); }

API void qsim_params(float jump_velocity, int auto_hop, int chain_jump, float chain_velocity, int chain_ms) {
    pm_jumpVelocity = jump_velocity;
    pm_autoHop = auto_hop;
    pm_chainJump = chain_jump;
    pm_chainJumpVelocity = chain_velocity;
    pm_chainJumpMs = chain_ms;
}

API int qsim_create(int n) {
    free(players);
    players = calloc(n, sizeof(playerState_t));
    nplayers = players ? n : 0;
    return nplayers;
}

/* place player i at origin with velocity and view yaw (degrees) */
API void qsim_reset(int i, const float *origin, const float *velocity, float yaw) {
    playerState_t *ps = &players[i];
    memset(ps, 0, sizeof(*ps));
    ps->pm_type = PM_NORMAL;
    ps->gravity = 800;
    ps->speed = 320;
    ps->stats[STAT_HEALTH] = 100;
    ps->stats[STAT_MAX_HEALTH] = 100;
    ps->viewheight = DEFAULT_VIEWHEIGHT;
    ps->groundEntityNum = ENTITYNUM_NONE;
    ps->weapon = WP_ROCKET_LAUNCHER;
    ps->weaponstate = WEAPON_READY;
    ps->commandTime = 1000;
    VectorCopy(origin, ps->origin);
    VectorCopy(velocity, ps->velocity);
    ps->viewangles[YAW] = yaw;
}

/* overwrite position/velocity/view of player i but keep its movement flags (ground, jump held, timers):
   used to follow a recording step by step and measure one-step prediction error */
API void qsim_set(int i, const float *origin, const float *velocity, float yaw, int command_time) {
    playerState_t *ps = &players[i];
    VectorCopy(origin, ps->origin);
    VectorCopy(velocity, ps->velocity);
    ps->viewangles[YAW] = yaw;
    ps->commandTime = command_time;
}

/*
 * Step every player by msec with one command each.
 * moves: n x 3 signed bytes (forward, right, up: -127..127); angles: n x 2 floats (pitch, yaw, degrees).
 */
API void qsim_step(int n, const signed char *moves, const float *angles, int msec) {
    int i;
    pmove_t pm;
    for (i = 0; i < n && i < nplayers; i++) {
        playerState_t *ps = &players[i];
        memset(&pm, 0, sizeof(pm));
        pm.ps = ps;
        pm.cmd.serverTime = ps->commandTime + msec;
        pm.cmd.forwardmove = moves[i * 3 + 0];
        pm.cmd.rightmove = moves[i * 3 + 1];
        pm.cmd.upmove = moves[i * 3 + 2];
        pm.cmd.angles[PITCH] = ANGLE2SHORT(angles[i * 2 + 0]) - ps->delta_angles[PITCH];
        pm.cmd.angles[YAW] = ANGLE2SHORT(angles[i * 2 + 1]) - ps->delta_angles[YAW];
        pm.cmd.weapon = WP_ROCKET_LAUNCHER;
        pm.tracemask = MASK_PLAYERSOLID;
        pm.trace = sim_trace;
        pm.pointcontents = sim_pointcontents;
        pm.noFootsteps = qtrue;
        Pmove(&pm);
        touch_triggers(ps);                                   /* the game touches triggers after the move */
    }
}

/* ---------------- map triggers: jump pads and teleporters (game code, not Pmove) ---------------- */
#define MAX_SIM_TRIGGERS 64
typedef struct { clipHandle_t model; int type; vec3_t a; float angle; } sim_trigger_t;   /* type 0 push, 1 teleport */
static sim_trigger_t triggers[MAX_SIM_TRIGGERS];
static int ntriggers;

/* add a trigger: inline model number (from "*N"), type 0 = jump pad aimed at target xyz,
   type 1 = teleporter to destination xyz facing angle. Mirrors Q3's AimAtTarget / TeleportPlayer. */
API int qsim_add_trigger(int model_num, int type, const float *target, float angle) {
    sim_trigger_t *t;
    if (ntriggers >= MAX_SIM_TRIGGERS) return -1;
    t = &triggers[ntriggers];
    t->model = CM_InlineModel(model_num);
    t->type = type;
    t->angle = angle;
    if (type == 0) {
        vec3_t mins, maxs, origin;
        float height, gravity = 800.0f, time, dist;
        CM_ModelBounds(t->model, mins, maxs);
        VectorAdd(mins, maxs, origin);
        VectorScale(origin, 0.5f, origin);
        height = target[2] - mins[2];
        time = (float)sqrt(height / (0.5f * gravity));
        if (!time) return -1;
        VectorSubtract(target, origin, t->a);
        t->a[2] = 0;
        dist = VectorNormalize(t->a);
        VectorScale(t->a, dist / time, t->a);
        t->a[2] = time * gravity;
    } else {
        VectorCopy(target, t->a);
    }
    return ntriggers++;
}

API void qsim_clear_triggers(void) { ntriggers = 0; }

/* bounds of an inline model (trigger brush): out = mins xyz, maxs xyz */
API void qsim_model_bounds(int model_num, float *out) {
    vec3_t mins, maxs;
    CM_ModelBounds(CM_InlineModel(model_num), mins, maxs);
    VectorCopy(mins, out);
    VectorCopy(maxs, out + 3);
}

static void touch_triggers(playerState_t *ps) {
    static const vec3_t pmins = {-15, -15, -24}, pmaxs = {15, 15, 32};
    int j;
    trace_t tr;
    for (j = 0; j < ntriggers; j++) {
        sim_trigger_t *t = &triggers[j];
        CM_BoxTrace(&tr, ps->origin, ps->origin, pmins, pmaxs, t->model, -1, qfalse);
        if (!tr.startsolid) continue;
        if (t->type == 0) {
            VectorCopy(t->a, ps->velocity);
            ps->groundEntityNum = ENTITYNUM_NONE;
        } else {
            vec3_t ang = {0, 0, 0}, fwd;
            VectorCopy(t->a, ps->origin);
            ps->origin[2] += 1;
            ang[YAW] = t->angle;
            AngleVectors(ang, fwd, NULL, NULL);
            VectorScale(fwd, 400, ps->velocity);
            ps->pm_time = 160;
            ps->pm_flags |= PMF_TIME_KNOCKBACK;
            ps->eFlags ^= EF_TELEPORT_BIT;
            ps->groundEntityNum = ENTITYNUM_NONE;
            ps->viewangles[YAW] = t->angle;                   /* view snaps to the exit angle */
        }
        break;
    }
}

/* out: n x 8 floats: origin xyz, velocity xyz, on ground (0/1), view yaw */
API void qsim_get(int n, float *out) {
    int i;
    for (i = 0; i < n && i < nplayers; i++) {
        playerState_t *ps = &players[i];
        float *o = out + i * 8;
        VectorCopy(ps->origin, o);
        VectorCopy(ps->velocity, o + 3);
        o[6] = ps->groundEntityNum != ENTITYNUM_NONE ? 1.0f : 0.0f;
        o[7] = ps->viewangles[YAW];
    }
}

/*
 * Wall/floor sensing: for each of n origins cast k rays (unit dirs, k x 3) up to maxdist.
 * out: n x k fractions (1 = nothing hit). A small box keeps rays from slipping through brush seams.
 */
API void qsim_rays(int n, const float *origins, int k, const float *dirs, float maxdist, float *out) {
    static const vec3_t mins = {-1, -1, -1}, maxs = {1, 1, 1};
    int i, j;
    trace_t tr;
    for (i = 0; i < n; i++) {
        const float *o = origins + i * 3;
        for (j = 0; j < k; j++) {
            vec3_t end;
            VectorMA(o, maxdist, dirs + j * 3, end);
            CM_BoxTrace(&tr, o, end, mins, maxs, 0, MASK_PLAYERSOLID, qfalse);
            out[i * k + j] = tr.fraction;
        }
    }
}

/* like qsim_rays but each origin has its own k directions (n x k x 3), e.g. rays turning with the view */
API void qsim_rays_each(int n, const float *origins, int k, const float *dirs, float maxdist, float *out) {
    static const vec3_t mins = {-1, -1, -1}, maxs = {1, 1, 1};
    int i, j;
    trace_t tr;
    for (i = 0; i < n; i++) {
        const float *o = origins + i * 3;
        for (j = 0; j < k; j++) {
            vec3_t end;
            VectorMA(o, maxdist, dirs + (i * k + j) * 3, end);
            CM_BoxTrace(&tr, o, end, mins, maxs, 0, MASK_PLAYERSOLID, qfalse);
            out[i * k + j] = tr.fraction;
        }
    }
}

/* box trace: out = fraction, endpos xyz, plane normal xyz, startsolid, allsolid (9 floats) */
API void qsim_trace(const float *start, const float *end, const float *mins, const float *maxs, float *out) {
    trace_t tr;
    CM_BoxTrace(&tr, start, end, mins, maxs, 0, MASK_PLAYERSOLID, qfalse);
    out[0] = tr.fraction;
    VectorCopy(tr.endpos, out + 1);
    VectorCopy(tr.plane.normal, out + 4);
    out[7] = (float)tr.startsolid;
    out[8] = (float)tr.allsolid;
}

/* bounds of the world model: out = mins xyz, maxs xyz */
API void qsim_world_bounds(float *out) {
    vec3_t mins, maxs;
    CM_ModelBounds(CM_InlineModel(0), mins, maxs);
    VectorCopy(mins, out);
    VectorCopy(maxs, out + 3);
}

/* damage knockback (Q3 G_Damage): add kick to player i's velocity and lock friction briefly */
API void qsim_knockback(int i, const float *kick, int knockback) {
    playerState_t *ps = &players[i];
    VectorAdd(ps->velocity, kick, ps->velocity);
    if (!ps->pm_time) {
        int t = knockback * 2;
        if (t < 50) t = 50;
        if (t > 200) t = 200;
        ps->pm_time = t;
        ps->pm_flags |= PMF_TIME_KNOCKBACK;
    }
}

/* visibility cluster of the leaf containing a point: -1 = outside the playable map (void / inside walls) */
API int qsim_cluster(const float *point) { return CM_LeafCluster(CM_PointLeafnum(point)); }

/* contents at a point (e.g. CONTENTS_LAVA, CONTENTS_SLIME, CONTENTS_TRIGGER for hurt/void checks) */
API int qsim_contents(const float *point) { return CM_PointContents(point, 0); }
